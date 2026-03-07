import asyncio
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from config import DeviceConfig
from log import get_logger


logger = get_logger()


# ---------------------------------------------------------------
# BLE bridge — runs a dedicated asyncio event loop in a background
# thread.  bluetti_mqtt and bleak are async-only libraries, so
# this bridge is the sole place where asyncio exists.  Every
# public method on SwitchDevice is synchronous; it calls into
# this bridge when a BLE operation is needed.
# ---------------------------------------------------------------
class _BLELoop:
    """Background asyncio event loop for BLE operations."""

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, name: str = "BLE"):
        """Spin up the background thread and wait for the loop to be running."""
        self._thread = threading.Thread(
            target=self._run_forever,
            name=name,
            daemon=True,
        )
        self._thread.start()
        deadline = time.monotonic() + 5
        while self._loop is None or not self._loop.is_running():
            time.sleep(0.05)
            if time.monotonic() > deadline:
                raise RuntimeError("Failed to start BLE event loop")

    def stop(self):
        """Stop the event loop and join the background thread."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None

    def run(self, coro, timeout: float = 30):
        """Submit a coroutine to the background loop, block until done."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("BLE event loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _run_forever(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


@dataclass
class SwitchChannel:
    name: str
    description: str
    field: str
    setter_field: Optional[str]
    writable: bool
    boolean: bool
    min_value: float
    max_value: float
    step: float


# Fixed channel layout exposed by every Bluetti device.
# Fields are from bluetti_mqtt's parsed output; the library
# auto-detects the Bluetti model (AC300, AC200M, EP500, etc.)
# and exposes a common set of register names.
CHANNELS = [
    SwitchChannel("AC Output", "AC output on/off", "ac_output_on", "ac_output_on", True, True, 0.0, 1.0, 1.0),
    SwitchChannel("DC Output", "DC output on/off", "dc_output_on", "dc_output_on", True, True, 0.0, 1.0, 1.0),
    SwitchChannel("Battery Level", "Total battery percentage", "total_battery_percent", None, False, False, 0.0, 100.0, 0.1),
    SwitchChannel("AC Output Power", "AC output power (W)", "ac_output_power", None, False, False, 0.0, 10000.0, 1.0),
    SwitchChannel("DC Output Power", "DC output power (W)", "dc_output_power", None, False, False, 0.0, 10000.0, 1.0),
    SwitchChannel("Solar Input Power", "DC/solar input power (W)", "dc_input_power", None, False, False, 0.0, 10000.0, 1.0),
    SwitchChannel("AC Input Power", "AC input power (W)", "ac_input_power", None, False, False, 0.0, 10000.0, 1.0),
]


# ---------------------------------------------------------------
# Module-level async coroutines — these run on the _BLELoop
# thread and are never called directly from the ASCOM layer.
# ---------------------------------------------------------------
async def _ble_connect(mac: str, timeout: int):
    """BLE scan, model detection, persistent BluetoothClient.

    Returns (bluetti_device, client, client_task).
    """
    from bleak import BleakScanner
    from bluetti_mqtt.bluetooth import BluetoothClient, build_device

    logger.info(f"Scanning for BLE device {mac}...")
    ble_devices = await BleakScanner.discover()
    match = next((d for d in ble_devices if d.address == mac), None)
    if not match:
        raise RuntimeError(f"Bluetti device {mac} not found during BLE scan")
    bluetti_device = build_device(match.address, match.name)
    logger.info(f"Detected model: {type(bluetti_device).__name__}")

    client = BluetoothClient(mac)
    # Pre-set device name from the BLE scan so that
    # BluetoothClient.run() skips _get_name().  The AC300 (and
    # possibly other models) does not expose the standard GAP
    # Device Name characteristic (0x2A00), which causes
    # _get_name() to throw BleakCharacteristicNotFoundError and
    # enter an infinite connect/disconnect retry loop.
    client.name = match.name
    client_task = asyncio.ensure_future(client.run())

    deadline = time.monotonic() + timeout
    while not client.is_ready:
        if time.monotonic() > deadline:
            client_task.cancel()
            raise RuntimeError(
                f"BLE client for {mac} did not become ready within {timeout}s"
            )
        await asyncio.sleep(0.2)

    return bluetti_device, client, client_task


async def _ble_disconnect(client_task):
    """Cancel the persistent BLE client task."""
    if client_task and not client_task.done():
        client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass


async def _ble_poll(bluetti_device, client, timeout: int) -> dict:
    """Poll all logging registers and return parsed data dict."""
    data = {}
    for cmd in bluetti_device.logging_commands:
        resp_future = await client.perform(cmd)
        resp = await asyncio.wait_for(resp_future, timeout=timeout)
        body = cmd.parse_response(resp)
        parsed = bluetti_device.parse(cmd.starting_address, body)
        data.update(parsed)
    return data


async def _ble_set_field(bluetti_device, client, field: str, value, timeout: int):
    """Set a writable register on the Bluetti device."""
    cmd = bluetti_device.build_setter_command(field, value)
    resp_future = await client.perform(cmd)
    await asyncio.wait_for(resp_future, timeout=timeout)


class SwitchDevice:
    """Low-level driver for Bluetti solar generators (BLE)."""

    def __init__(self, device_config: DeviceConfig):
        self._config = device_config

        # Connection state
        self._connected = False
        self._connecting = False
        self._connect_error: Optional[Exception] = None
        self._connect_thread: Optional[threading.Thread] = None

        # BLE internals (owned by the background loop thread)
        self._ble = _BLELoop()
        self._bluetti_device = None
        self._client = None
        self._client_task = None

        # Cached poll data
        self._cached_data: dict = {}
        self._cache_time: float = 0.0
        self._poll_lock = threading.Lock()

    def _connect_worker(self):
        """Background thread: BLE scan → GATT handshake → initial poll."""
        try:
            self._bluetti_device, self._client, self._client_task = (
                self._ble.run(
                    _ble_connect(self._config.ble_mac, self._config.timeout),
                    timeout=self._config.timeout,
                )
            )

            # Initial poll to verify communication
            self._ble.run(
                _ble_poll(
                    self._bluetti_device,
                    self._client,
                    self._config.timeout,
                ),
                timeout=self._config.timeout,
            )

            self._connected = True
            logger.info(f"Connected to Bluetti: {self._config.entity}")
        except Exception as e:
            logger.error(f"Connect error: {e}")
            self._connected = False
            self._connect_error = e
            self._ble.stop()
        finally:
            self._connecting = False

    def _poll_if_stale(self):
        """Re-poll the device if the cache has expired."""
        with self._poll_lock:
            now = time.monotonic()
            if now - self._cache_time >= self._config.poll_ttl:
                self._cached_data = self._ble.run(
                    _ble_poll(
                        self._bluetti_device,
                        self._client,
                        self._config.timeout,
                    ),
                    timeout=self._config.timeout,
                )
                self._cache_time = now

    def _get_field(self, field: str, default=0):
        """Return a cached field value, re-polling if stale."""
        self._poll_if_stale()
        return self._cached_data.get(field, default)

    #######################################
    # ASCOM Methods Common To All Devices #
    #######################################
    def connect(self):
        """Start BLE connection in a background thread."""
        if self._connecting or self._connected:
            return

        # Surface any error from a prior failed attempt
        if self._connect_error is not None:
            err = self._connect_error
            self._connect_error = None
            raise err

        self._connecting = True
        self._connect_error = None

        # Start the BLE event-loop thread
        self._ble.start(name=f"BLE-{self._config.entity}")

        # Kick off the connect worker
        self._connect_thread = threading.Thread(
            target=self._connect_worker,
            name=f"Connect-{self._config.entity}",
            daemon=True,
        )
        self._connect_thread.start()

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, value: bool):
        if value and not self._connected:
            self.connect()
        elif not value and self._connected:
            self.disconnect()

    @property
    def connecting(self) -> bool:
        return self._connecting

    def disconnect(self):
        """Close BLE connection."""
        try:
            self._ble.run(_ble_disconnect(self._client_task), timeout=5)
        except Exception as e:
            logger.warning(f"Error during BLE disconnect: {e}")
        self._ble.stop()
        self._bluetti_device = None
        self._client = None
        self._client_task = None
        self._cached_data = {}
        self._cache_time = 0.0
        self._connected = False
        self._connect_error = None
        logger.info(f"Disconnected from Bluetti: {self._config.entity}")

    ########################
    # ISwitchV3 properties #
    ########################
    @property
    def max_switch(self) -> int:
        return len(CHANNELS)

    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    #####################
    # ISwitchV3 methods #
    #####################
    def can_async(self, switch_id: int) -> bool:
        return False

    def cancel_async(self, switch_id: int):
        pass

    def can_write(self, switch_id: int) -> bool:
        return CHANNELS[switch_id].writable

    def get_switch(self, switch_id: int) -> bool:
        ch = CHANNELS[switch_id]
        if ch.boolean:
            return bool(self._get_field(ch.field, False))
        # For analog channels, return True if value >= midpoint
        val = float(self._get_field(ch.field, 0))
        return val >= (ch.max_value - ch.min_value) / 2.0

    def get_switch_description(self, switch_id: int) -> str:
        return CHANNELS[switch_id].description

    def get_switch_name(self, switch_id: int) -> str:
        return CHANNELS[switch_id].name

    def get_switch_value(self, switch_id: int) -> float:
        ch = CHANNELS[switch_id]
        if ch.boolean:
            return 1.0 if bool(self._get_field(ch.field, False)) else 0.0
        return float(self._get_field(ch.field, 0))

    def max_switch_value(self, switch_id: int) -> float:
        return CHANNELS[switch_id].max_value

    def min_switch_value(self, switch_id: int) -> float:
        return CHANNELS[switch_id].min_value

    def set_switch(self, switch_id: int, state: bool):
        ch = CHANNELS[switch_id]
        self._ble.run(
            _ble_set_field(
                self._bluetti_device,
                self._client,
                ch.setter_field,
                state,
                self._config.timeout,
            ),
            timeout=self._config.timeout,
        )
        # Invalidate cache so next read reflects the change
        self._cache_time = 0.0
        logger.info(
            f"Switch {switch_id} ({ch.name}) set to "
            f"{'ON' if state else 'OFF'}"
        )

    def set_switch_value(self, switch_id: int, value: float):
        ch = CHANNELS[switch_id]
        if ch.boolean:
            self.set_switch(switch_id, value >= 0.5)
        else:
            raise ValueError(
                f"Switch {switch_id} ({ch.name}) does not support "
                f"analog set."
            )

    def switch_step(self, switch_id: int) -> float:
        return CHANNELS[switch_id].step