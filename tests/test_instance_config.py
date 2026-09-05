"""Tests for installation instance configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.config import (
    DEFAULT_DISPLAY_NAME,
    DEFAULT_INSTANCE_KEY,
    AppConfig,
    CansubConfig,
    ConfigError,
    InstanceConfig,
    PathsConfig,
    load_config,
    resolve_data_dir,
    save_config,
    update_instance_config,
    validate_instance_key,
)
from canresearch.storage.database import default_db_path


def test_default_development_instance(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    config = load_config(path)
    assert config.instance.instance_key == DEFAULT_INSTANCE_KEY
    assert config.instance.display_name == DEFAULT_DISPLAY_NAME
    assert config.paths.data_dir == "data"


def test_explicit_instance_configuration(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    update_instance_config(
        instance_key="workshop",
        display_name="CAN Research - Workshop",
        path=path,
    )
    config = load_config(path)
    assert config.instance.instance_key == "workshop"
    assert config.instance.display_name == "CAN Research - Workshop"


@pytest.mark.parametrize(
    "instance_key",
    [
        "workshop",
        "travel",
        "lab-01",
        "instance_2",
        "A1",
    ],
)
def test_valid_instance_keys(instance_key: str) -> None:
    assert validate_instance_key(instance_key) == instance_key


@pytest.mark.parametrize(
    "instance_key",
    [
        "",
        " ",
        "-bad",
        "_bad",
        "bad space",
        "bad/slash",
        "bad.dot",
    ],
)
def test_invalid_instance_keys_rejected(instance_key: str) -> None:
    with pytest.raises(ConfigError, match="instance_key"):
        validate_instance_key(instance_key)


def test_invalid_instance_key_in_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[instance]\ninstance_key = "bad key"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="instance_key"):
        load_config(path)


def test_custom_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.toml"
    custom_data = tmp_path / "workshop-data"
    update_instance_config(data_dir=str(custom_data), path=config_path)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)
    assert resolve_data_dir() == custom_data
    assert default_db_path() == custom_data / "references" / "canresearch.db"


def test_save_round_trip_includes_instance_and_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    save_config(
        AppConfig(
            instance=InstanceConfig(instance_key="travel", display_name="CAN Research - Travel"),
            paths=PathsConfig(data_dir="data"),
            cansub=CansubConfig(host="example.local", timeout=7.5, verify_tls=True),
        ),
        path,
    )
    text = path.read_text(encoding="utf-8")
    assert "[instance]" in text
    assert "[paths]" in text
    config = load_config(path)
    assert config.instance.instance_key == "travel"
    assert config.cansub.host == "example.local"
