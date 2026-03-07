"""
ASCOM Alpaca Bluetti Switch Server – Main FastAPI Application

Entrypoint that:
  - Creates the FastAPI application
  - Configures logging (loguru + stdlib intercept)
  - Instantiates SwitchDevice instances from config.yaml
  - Starts the Alpaca discovery responder (UDP 32227)
  - Includes management, setup, and switch routers
  - Handles graceful shutdown (disconnects all devices)
"""

from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI

from config import config
from discovery import DiscoveryResponder
import switch
from switch_device import SwitchDevice
from log import get_logger, setup_logging
import management
import setup


setup_logging()
logger = get_logger()

# Device registry: device_number → SwitchDevice
devices: Dict[int, SwitchDevice] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager – startup and shutdown."""
    logger.info(f"Starting {config.entity} on {config.server.host}:{config.server.port}")

    # Instantiate devices from config
    for device_config in config.devices:
        dev = SwitchDevice(device_config)
        devices[device_config.device_number] = dev
        logger.info(f"Registered device: {device_config.entity}")

    # Share devices dict with routers
    switch.set_devices(devices)
    management.set_devices(devices)

    # Start Alpaca discovery responder
    try:
        DiscoveryResponder(config.server.host, config.server.port)
    except Exception as e:
        logger.warning(f"Could not start discovery responder: {e}")

    yield

    # Shutdown: disconnect all devices
    for dev in devices.values():
        if dev.connected:
            try:
                dev.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting {config.entity}: {e}")
    logger.info("Server shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="ASCOM Alpaca Bluetti Switch Server",
    description="ASCOM Alpaca API for Bluetti solar generators over BLE",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(management.router)
app.include_router(setup.router)
app.include_router(switch.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
        access_log=False,
    )
