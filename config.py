import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import yaml
from pydantic import BaseModel, Field


load_dotenv()


def _env_constructor(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> str:
    """Resolve !env TAG to an environment variable value."""
    var_name = loader.construct_scalar(node)
    value = os.environ.get(var_name)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set")
    return value


yaml.SafeLoader.add_constructor("!env", _env_constructor)


def _load_yaml_configs() -> dict:
    """Load config.yaml with optional docker override."""
    base_config = {}
    override_config = {}

    base_path = Path(__file__).parent / "config.yaml"
    if base_path.exists():
        with open(base_path, "r") as f:
            base_config = yaml.safe_load(f) or {}

    docker_path = Path("/alpyca/config.yaml")
    if docker_path.exists():
        with open(docker_path, "r") as f:
            override_config = yaml.safe_load(f) or {}

    def deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    return deep_merge(base_config, override_config)


class DeviceConfig(BaseModel):
    entity: str = Field(default="Bluetti")
    device_number: int = Field(default=0)
    ble_mac: str = Field(default="00:00:00:00:00:00")
    timeout: int = Field(default=30)
    poll_ttl: int = Field(default=5)


class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=6000)


class Config(BaseModel):
    entity: str = Field(default="bluetti")
    server: ServerConfig = Field(default_factory=ServerConfig)
    log_level: str = Field(default="INFO")
    devices: List[DeviceConfig] = Field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        return cls(**_load_yaml_configs())

    def get_device(self, device_number: int) -> Optional[DeviceConfig]:
        for device in self.devices:
            if device.device_number == device_number:
                return device
        return None


config = Config.load()
