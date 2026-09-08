"""Local project configuration."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from canresearch.cansub.timing import ChannelTimingExpectation

INSTANCE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

DEFAULT_INSTANCE_KEY = "local"
DEFAULT_DISPLAY_NAME = "CAN Research (local)"
DEFAULT_DATA_DIR = "data"


class ConfigError(Exception):
    """Configuration is missing, invalid, or incomplete."""


@dataclass(slots=True)
class InstanceConfig:
    instance_key: str = DEFAULT_INSTANCE_KEY
    display_name: str = DEFAULT_DISPLAY_NAME


@dataclass(slots=True)
class PathsConfig:
    data_dir: str = DEFAULT_DATA_DIR


@dataclass(slots=True)
class CansubConfig:
    host: str | None = None
    timeout: float = 5.0
    verify_tls: bool = False
    channels: dict[int, ChannelTimingExpectation] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    instance: InstanceConfig
    paths: PathsConfig
    cansub: CansubConfig


def validate_instance_key(instance_key: str) -> str:
    """Return a validated instance key or raise ConfigError."""
    cleaned = instance_key.strip()
    if not cleaned:
        raise ConfigError("instance_key must not be empty")
    if not INSTANCE_KEY_PATTERN.fullmatch(cleaned):
        raise ConfigError(
            "instance_key must start with a letter or digit and contain only "
            "letters, digits, underscores, and hyphens"
        )
    return cleaned


def default_config_path() -> Path:
    """Local config file path (gitignored when under data/)."""
    return Path(DEFAULT_DATA_DIR) / "config.toml"


def example_config_path() -> Path:
    """Committed example config template path."""
    return Path("config.toml.example")


def resolve_data_dir(path: Path | None = None) -> Path:
    """Return the configured data directory for this installation."""
    config = load_config(path)
    return Path(config.paths.data_dir)


def load_config(path: Path | None = None) -> AppConfig:
    """Load application configuration from TOML."""
    config_path = path or default_config_path()
    if not config_path.exists():
        return AppConfig(
            instance=InstanceConfig(),
            paths=PathsConfig(),
            cansub=CansubConfig(),
        )

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"Invalid configuration file {config_path}: {exc}"
        raise ConfigError(msg) from exc

    instance_raw = raw.get("instance", {})
    if instance_raw is None:
        instance_raw = {}
    if not isinstance(instance_raw, dict):
        msg = f"Invalid configuration file {config_path}: [instance] must be a table"
        raise ConfigError(msg)

    paths_raw = raw.get("paths", {})
    if paths_raw is None:
        paths_raw = {}
    if not isinstance(paths_raw, dict):
        msg = f"Invalid configuration file {config_path}: [paths] must be a table"
        raise ConfigError(msg)

    cansub_raw = raw.get("cansub", {})
    if not isinstance(cansub_raw, dict):
        msg = f"Invalid configuration file {config_path}: [cansub] must be a table"
        raise ConfigError(msg)

    return AppConfig(
        instance=_parse_instance_section(instance_raw),
        paths=_parse_paths_section(paths_raw),
        cansub=_parse_cansub_section(cansub_raw),
    )


def _parse_instance_section(raw: dict[str, Any]) -> InstanceConfig:
    instance_key = raw.get("instance_key", DEFAULT_INSTANCE_KEY)
    if not isinstance(instance_key, str):
        raise ConfigError("[instance].instance_key must be a string")

    display_name = raw.get("display_name", DEFAULT_DISPLAY_NAME)
    if not isinstance(display_name, str):
        raise ConfigError("[instance].display_name must be a string")

    cleaned_display_name = display_name.strip()
    if not cleaned_display_name:
        raise ConfigError("[instance].display_name must not be empty")

    return InstanceConfig(
        instance_key=validate_instance_key(instance_key),
        display_name=cleaned_display_name,
    )


def _parse_paths_section(raw: dict[str, Any]) -> PathsConfig:
    data_dir = raw.get("data_dir", DEFAULT_DATA_DIR)
    if not isinstance(data_dir, str):
        raise ConfigError("[paths].data_dir must be a string")
    cleaned = data_dir.strip()
    if not cleaned:
        raise ConfigError("[paths].data_dir must not be empty")
    return PathsConfig(data_dir=cleaned)


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
    channels = _parse_cansub_channels(raw.get("channels"))
    return CansubConfig(
        host=cleaned_host,
        timeout=float(timeout),
        verify_tls=verify_tls,
        channels=channels,
    )


def _parse_cansub_channels(raw: Any) -> dict[int, ChannelTimingExpectation]:
    if not isinstance(raw, dict):
        return {}
    channels: dict[int, ChannelTimingExpectation] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            channel = int(str(key).strip())
        except ValueError:
            raise ConfigError(f"[cansub.channels.{key}] channel key must be an integer") from None
        if channel <= 0:
            raise ConfigError(f"[cansub.channels.{key}] channel must be positive")
        nominal = value.get("nominal_bitrate")
        if nominal is None:
            raise ConfigError(
                f"[cansub.channels.{key}] nominal_bitrate is required when a channel block is present"
            )
        if not isinstance(nominal, int) or nominal <= 0:
            raise ConfigError(f"[cansub.channels.{key}] nominal_bitrate must be a positive integer")
        data = value.get("data_bitrate")
        if data is not None and (not isinstance(data, int) or data <= 0):
            raise ConfigError(f"[cansub.channels.{key}] data_bitrate must be a positive integer")
        timing = _parse_timing_table(value.get("timing"), f"[cansub.channels.{key}].timing")
        timing_data = _parse_timing_table(
            value.get("timing_data"),
            f"[cansub.channels.{key}].timing_data",
        )
        listen_only = value.get("listen_only")
        if listen_only is not None and not isinstance(listen_only, bool):
            raise ConfigError(f"[cansub.channels.{key}] listen_only must be a boolean")
        auto_reset = value.get("auto_reset")
        if auto_reset is not None and not isinstance(auto_reset, bool):
            raise ConfigError(f"[cansub.channels.{key}] auto_reset must be a boolean")
        error_frames = value.get("error_frames")
        if error_frames is not None and not isinstance(error_frames, bool):
            raise ConfigError(f"[cansub.channels.{key}] error_frames must be a boolean")
        channels[channel] = ChannelTimingExpectation(
            channel=channel,
            nominal_bitrate=nominal,
            data_bitrate=data,
            timing=timing,
            timing_data=timing_data,
            listen_only=listen_only,
            auto_reset=auto_reset,
            error_frames=error_frames,
        )
    return channels


def _parse_timing_table(raw: Any, path: str) -> dict[str, int] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a table")
    parsed: dict[str, int] = {}
    for key in ("brp", "seg1", "seg2", "sjw"):
        if key not in raw:
            raise ConfigError(f"{path}.{key} is required when timing is specified")
        value = raw[key]
        if not isinstance(value, int) or value <= 0:
            raise ConfigError(f"{path}.{key} must be a positive integer")
        parsed[key] = value
    return parsed


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Write application configuration to TOML."""
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_render_config(config), encoding="utf-8")
    return config_path


def _render_config(config: AppConfig) -> str:
    lines = [
        "[instance]",
        f'instance_key = {_toml_string(config.instance.instance_key)}',
        f'display_name = {_toml_string(config.instance.display_name)}',
        "",
        "[paths]",
        f"data_dir = {_toml_string(config.paths.data_dir)}",
        "",
        "[cansub]",
    ]
    if config.cansub.host is not None:
        lines.append(f"host = {_toml_string(config.cansub.host)}")
    lines.append(f"timeout = {config.cansub.timeout:g}")
    lines.append(f"verify_tls = {'true' if config.cansub.verify_tls else 'false'}")
    for channel in sorted(config.cansub.channels):
        expectation = config.cansub.channels[channel]
        lines.append("")
        lines.append(f"[cansub.channels.{channel}]")
        lines.append(f"nominal_bitrate = {expectation.nominal_bitrate}")
        if expectation.data_bitrate is not None:
            lines.append(f"data_bitrate = {expectation.data_bitrate}")
        if expectation.timing is not None:
            lines.append(
                "timing = "
                + _render_inline_table(expectation.timing, ("brp", "seg1", "seg2", "sjw"))
            )
        if expectation.timing_data is not None:
            lines.append(
                "timing_data = "
                + _render_inline_table(expectation.timing_data, ("brp", "seg1", "seg2", "sjw"))
            )
        if expectation.listen_only is not None:
            lines.append(
                f"listen_only = {'true' if expectation.listen_only else 'false'}"
            )
        if expectation.auto_reset is not None:
            lines.append(f"auto_reset = {'true' if expectation.auto_reset else 'false'}")
        if expectation.error_frames is not None:
            lines.append(
                f"error_frames = {'true' if expectation.error_frames else 'false'}"
            )
    lines.append("")
    return "\n".join(lines)


def _render_inline_table(values: dict[str, int], keys: tuple[str, ...]) -> str:
    inner = ", ".join(f'{key} = {values[key]}' for key in keys)
    return "{" + inner + "}"


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


def update_instance_config(
    *,
    instance_key: str | None = None,
    display_name: str | None = None,
    data_dir: str | None = None,
    path: Path | None = None,
) -> AppConfig:
    """Update instance/path settings and persist configuration."""
    config = load_config(path)
    if instance_key is not None:
        config.instance.instance_key = validate_instance_key(instance_key)
    if display_name is not None:
        cleaned = display_name.strip()
        if not cleaned:
            raise ConfigError("display_name must not be empty")
        config.instance.display_name = cleaned
    if data_dir is not None:
        cleaned = data_dir.strip()
        if not cleaned:
            raise ConfigError("data_dir must not be empty")
        config.paths.data_dir = cleaned
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
