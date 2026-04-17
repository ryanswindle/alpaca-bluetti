# Bluetti – ASCOM Alpaca Server for Bluetti Solar Generators

A FastAPI-based server, implementing the ASCOM **ISwitchV3** interface.  Communication is
via Bluetooth Low Energy (BLE) using the `bluetti_mqtt` and `bleak` libraries.  The driver
is model-agnostic — `bluetti_mqtt` auto-detects the Bluetti model (AC300, AC200M, AC500,
EP500, EP600, EB3A, etc.) from the BLE device name at connect time.

---

## Switch channel layout

Each Bluetti device exposes 7 ASCOM switch channels:

| Id | Name              | Type          | Writable | Value range  | Field                    |
|----|-------------------|---------------|----------|--------------|--------------------------|
| 0  | AC Output         | Boolean       | ✔        | 0.0 / 1.0   | `ac_output_on`           |
| 1  | DC Output         | Boolean       | ✔        | 0.0 / 1.0   | `dc_output_on`           |
| 2  | Battery Level     | Analog        | ✘        | 0.0 – 100.0 | `total_battery_percent`  |
| 3  | AC Output Power   | Analog (W)    | ✘        | 0.0 – 10000 | `ac_output_power`        |
| 4  | DC Output Power   | Analog (W)    | ✘        | 0.0 – 10000 | `dc_output_power`        |
| 5  | Solar Input Power | Analog (W)    | ✘        | 0.0 – 10000 | `dc_input_power`         |
| 6  | AC Input Power    | Analog (W)    | ✘        | 0.0 – 10000 | `ac_input_power`         |

---

## Implemented ISwitchV3 capabilities as of this driver version

| Property/Method      | Supported |
|----------------------|-----------|
| MaxSwitch            | ✔         |
| CanAsync             | ✘         |
| CanWrite             | ✔         |
| GetSwitch            | ✔         |
| GetSwitchDescription | ✔         |
| GetSwitchName        | ✔         |
| GetSwitchValue       | ✔         |
| MinSwitchValue       | ✔         |
| MaxSwitchValue       | ✔         |
| SetAsync             | ✘         |
| SetAsyncValue        | ✘         |
| SetSwitch            | ✔         |
| SetSwitchName        | ✘         |
| SetSwitchValue       | ✔         |
| StateChangeComplete  | ✘         |
| SwitchStep           | ✔         |

---

## Architecture

| File               | Purpose                                        |
|--------------------|------------------------------------------------|
| `main.py`          | FastAPI app, lifespan, router wiring           |
| `config.py`        | Pydantic config models, YAML loader            |
| `config.yaml`      | User-editable configuration                    |
| `switch.py`        | FastAPI router – ISwitchV3 endpoints           |
| `switch_device.py` | BLE driver (persistent connection, caching)    |
| `management.py`    | `/management` Alpaca management endpoints      |
| `setup.py`         | `/setup` HTML stub pages                       |
| `discovery.py`     | UDP Alpaca discovery responder (port 32227)    |
| `responses.py`     | Pydantic response models                       |
| `exceptions.py`    | ASCOM Alpaca error classes                     |
| `shr.py`           | Shared FastAPI dependencies / helpers          |
| `log.py`           | Loguru config + stdlib intercept handler       |
| `test.py`          | Quick smoke-test script                        |
| `requirements.txt` | Python package dependencies                    |
| `Dockerfile`       | Container build (Linux + BLE)                  |

---

## Configuration

Edit `config.yaml` to match your Bluetti devices.

Each device entry requires the **Bluetooth** MAC address (`ble_mac`).  This is the
BLE adapter MAC, *not* the Wi-Fi MAC.  You can find it by running `bluetoothctl` →
`scan on` on Linux, or via BLE scanner apps on mobile.

Multiple Bluetti devices can be registered by adding further entries under
`devices:` with distinct `device_number` values.

`poll_ttl` (seconds) controls how long polled register data is cached before
the next BLE read.  Lower values give fresher data but increase BLE traffic.

---

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

The server starts on `0.0.0.0:6000` by default (configurable in `config.yaml`).

> **Note:** BLE requires appropriate permissions.  On Linux, either run as root,
> or add your user to the `bluetooth` group and ensure BlueZ is running.

---

## Smoke test

```bash
# Requires Bluetti device(s) in BLE range
python test.py
```

---

## Docker

The container requires access to the host Bluetooth adapter via D-Bus and the
host network (for BLE and Alpaca discovery):

```bash
docker build -t alpaca-bluetti .
docker run -d --name alpaca-bluetti \
    -v ./config.yaml:/alpyca/config.yaml:ro \
    --privileged \
    --net=host \
    -v /var/run/dbus:/var/run/dbus \
    --restart unless-stopped \
    alpaca-bluetti
docker logs -f alpaca-bluetti
```