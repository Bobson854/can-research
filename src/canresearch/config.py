"""Local project configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Configuration is missing, invalid, or incomplete."""


@dataclass(slots=True)
class CansubConfig:
    host: str | None = None
    timeout: float = 5.0
    verify_tls: bool = False


@dataclass(slots=True)
class AppConfig:
    cansub: CansubConfig


def default_config_path() -> Path:
    """Local config file path (gitignored when under data/)."""
    return Path("data") / "config.toml"


def example_config_path() -> Path:
    """Committed example config template path."""
    return Path("config.toml.example")


def load_config(path: Path | None = None) -> AppConfig:
    """Load application configuration from TOML."""
    config_path = path or default_config_path()
    if not config_path.exists():
        return AppConfig(cansub=CansubConfig())

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"Invalid configuration file {config_path}: {exc}"
        raise ConfigError(msg) from exc

    cansub_raw = raw.get("cansub", {})
    if not isinstance(cansub_raw, dict):
        msg = f"Invalid configuration file {config_path}: [cansub] must be a table"
        raise ConfigError(msg)

    return AppConfig(cansub=_parse_cansub_section(cansub_raw))


def _parse_cansub_section(raw: dict[str, Any]) -> CansubConfig:
    host = raw.get("host")
    if host is not None and not isinstance(host, str):
        raise ConfigError("[cansub].host must be a string")

    timeout = raw.get("timeout", 5.0)
    if not isinstance(timeout, (int, float)):
        raise ConfigError("[cansub].timeout must be a number")
    if timeout <= 0:
        raise ConfigError("[cansub].timeout must be positive")

    verify_tls = raw.get("verify_tls", False)
    if not isinstance(verify_tls, bool):
        raise ConfigError("[cansub].verify_tls must be a boolean")

    cleaned_host = host.strip() if isinstance(host, str) and host.strip() else None
    return CansubConfig(host=cleaned_host, timeout=float(timeout), verify_tls=verify_tls)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Write application configuration to TOML."""
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_render_config(config), encoding="utf-8")
    return config_path


def _render_config(config: AppConfig) -> str:
    lines = ["[cansub]"]
    if config.cansub.host is not None:
        lines.append(f'host = {_toml_string(config.cansub.host)}')
    lines.append(f"timeout = {config.cansub.timeout:g}")
    lines.append(f"verify_tls = {'true' if config.cansub.verify_tls else 'false'}")
    lines.append("")
    return "\n".join(lines)


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def update_cansub_config(
    *,
    host: str | None = None,
    timeout: float | None = None,
    verify_tls: bool | None = None,
    path: Path | None = None,
) -> AppConfig:
    """Update CANsub settings and persist configuration."""
    config = load_config(path)
    if host is not None:
        cleaned = host.strip()
        config.cansub.host = cleaned or None
    if timeout is not None:
        if timeout <= 0:
            raise ConfigError("timeout must be positive")
        config.cansub.timeout = float(timeout)
    if verify_tls is not None:
        config.cansub.verify_tls = verify_tls
    save_config(config, path)
    return config


def resolve_cansub_host(cli_host: str | None, path: Path | None = None) -> str:
    """Resolve CANsub host using CLI override then configured value."""
    if cli_host and cli_host.strip():
        return cli_host.strip()

    config = load_config(path)
    if config.cansub.host:
        return config.cansub.host

    msg = (
        "No CANsub.2 host configured. Use --host <hostname-or-ip> or run:\n"
        "  canresearch config set-host <hostname-or-ip>"
    )
    raise ConfigError(msg)


def resolve_cansub_settings(
    cli_host: str | None,
    cli_timeout: float | None,
    cli_verify_tls: bool | None,
    path: Path | None = None,
) -> tuple[str, float, bool]:
    """Resolve host, timeout, and TLS verification settings."""
    config = load_config(path)
    host = resolve_cansub_host(cli_host, path)
    timeout = cli_timeout if cli_timeout is not None else config.cansub.timeout
    verify_tls = cli_verify_tls if cli_verify_tls is not None else config.cansub.verify_tls
    if timeout <= 0:
        raise ConfigError("timeout must be positive")
    return host, timeout, verify_tls
