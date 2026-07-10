import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from app.config import settings

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class ServiceClientConfig(BaseModel):
    client_id: str
    client_secret: str
    display_name: str
    scopes: list[str] = []


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


def load_service_clients(path: str | None = None) -> dict[str, ServiceClientConfig]:
    config_path = Path(path or settings.service_clients_config_path)
    if not config_path.exists():
        return {}

    raw = yaml.safe_load(config_path.read_text()) or {}
    registry: dict[str, ServiceClientConfig] = {}
    for entry in raw.get("service_clients", []):
        resolved = _resolve_env(entry)
        client = ServiceClientConfig(**resolved)
        registry[client.client_id] = client
    return registry


SERVICE_CLIENTS: dict[str, ServiceClientConfig] = load_service_clients()


def get_service_client(client_id: str) -> ServiceClientConfig | None:
    return SERVICE_CLIENTS.get(client_id)
