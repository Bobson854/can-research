"""Tests for local configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.config import (
    AppConfig,
    CansubConfig,
    ConfigError,
    load_config,
    resolve_cansub_host,
    resolve_cansub_settings,
    save_config,
    update_cansub_config,
)


def test_default_no_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    config = load_config(path)
    assert config.cansub.host is None
    assert config.cansub.timeout == 5.0
    assert config.cansub.verify_tls is False


def test_set_and_read_host(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    update_cansub_config(host="7413f810-usb.local", path=path)
    config = load_config(path)
    assert config.cansub.host == "7413f810-usb.local"


def test_ip_host_accepted(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    update_cansub_config(host="10.174.12.1", path=path)
    assert load_config(path).cansub.host == "10.174.12.1"


def test_cli_host_overrides_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    update_cansub_config(host="configured.local", path=path)
    host, timeout, verify_tls = resolve_cansub_settings("override.local", None, None, path)
    assert host == "override.local"
    assert timeout == 5.0
    assert verify_tls is False


def test_resolve_host_from_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    update_cansub_config(host="configured.local", path=path)
    assert resolve_cansub_host(None, path) == "configured.local"


def test_missing_host_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    with pytest.raises(ConfigError, match="No CANsub.2 host configured"):
        resolve_cansub_host(None, path)


def test_malformed_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[cansub]\nhost = ", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_config(path)


def test_save_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    save_config(
        AppConfig(cansub=CansubConfig(host="example.local", timeout=7.5, verify_tls=True)),
        path,
    )
    config = load_config(path)
    assert config.cansub.host == "example.local"
    assert config.cansub.timeout == 7.5
    assert config.cansub.verify_tls is True
