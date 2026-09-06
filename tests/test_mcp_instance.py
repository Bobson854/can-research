"""Tests for get_instance_info MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch import __version__
from canresearch.config import update_instance_config
from canresearch.mcp.handlers import handle_get_instance_info
from canresearch.mcp.server import (
    LIVE_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
    SIGNAL_RESEARCH_TOOL_NAMES,
    list_tool_names,
)
from canresearch.storage.database import SCHEMA_VERSION


@pytest.fixture
def instance_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / "config.toml"
    update_instance_config(
        instance_key="workshop",
        display_name="CAN Research - Workshop",
        path=config_path,
    )
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)
    return config_path


def test_get_instance_info_registered() -> None:
    assert "get_instance_info" in READ_ONLY_TOOL_NAMES
    assert len(READ_ONLY_TOOL_NAMES) == 28
    assert len(LIVE_TOOL_NAMES) == 7
    assert len(SIGNAL_RESEARCH_TOOL_NAMES) == 6
    assert len(list_tool_names()) == 41


def test_get_instance_info_returns_configured_identity(instance_env: Path) -> None:
    result = handle_get_instance_info()
    assert result["instance_key"] == "workshop"
    assert result["display_name"] == "CAN Research - Workshop"
    assert result["version"] == __version__
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["mcp_tool_count"] == 41
    assert result["capabilities"] == {
        "read_only_tools": 28,
        "live_tools": 7,
        "signal_research_tools": 6,
        "can_tx": False,
        "candidate_confirmation": False,
    }


def test_get_instance_info_does_not_leak_sensitive_values(instance_env: Path) -> None:
    result = handle_get_instance_info()
    serialized = str(result).lower()
    forbidden_fragments = (
        "api_key",
        "token",
        "password",
        "secret",
        "home",
        "users",
        "office",
        "config.toml",
        "references/canresearch.db",
    )
    for fragment in forbidden_fragments:
        assert fragment not in serialized
    assert "host" not in result["cansub"]
    assert "username" not in result
    assert "hostname" not in result


def test_default_instance_info_without_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "missing-config.toml"
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)
    result = handle_get_instance_info()
    assert result["instance_key"] == "local"
    assert result["display_name"] == "CAN Research (local)"
    assert result["cansub"]["host_configured"] is False
    assert result["cansub"]["connection_mode"] == "not_set"
