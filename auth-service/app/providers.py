import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from app.config import settings

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class ProviderConfig(BaseModel):
    key: str
    display_name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str = ""
    extra_userinfo_params: dict[str, str] = {}
    user_id_field: str
    email_field: str | None = None
    name_field: str | None = None


def _resolve_env(value: Any) -> Any:
    """Substitutes ${VAR_NAME} in string values with the matching env var."""
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def load_providers(path: str | None = None) -> dict[str, ProviderConfig]:
    config_path = Path(path or settings.providers_config_path)
    if not config_path.exists():
        return {}

    raw = yaml.safe_load(config_path.read_text()) or {}
    registry: dict[str, ProviderConfig] = {}
    for entry in raw.get("providers", []):
        resolved = _resolve_env(entry)
        provider = ProviderConfig(**resolved)
        registry[provider.key] = provider
    return registry


PROVIDERS: dict[str, ProviderConfig] = load_providers()


def get_provider(key: str) -> ProviderConfig | None:
    return PROVIDERS.get(key)


def get_field(data: dict, dotted_path: str | None) -> Any:
    """Reads a value out of a provider's userinfo JSON via a dotted path,
    e.g. "id" or "response.0.id" (VK wraps its payload in a list)."""
    if not dotted_path:
        return None

    current: Any = data
    for part in dotted_path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current
