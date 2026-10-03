"""Tests for exported MCP ToolAnnotations on the public tool surface."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from canresearch.mcp.server import TOOL_BINDINGS, create_server, list_tool_names
from canresearch.mcp.tool_annotations import (
    MCP_WRITE_ORCHESTRATION_TOOL_NAMES,
    ToolSemantic,
    expected_semantic_for_tool_name,
    validate_tool_binding_semantics,
)


def _annotation_flags(tool: Any) -> dict[str, bool | None]:
    ann = tool.annotations
    assert ann is not None
    return {
        "readOnlyHint": ann.readOnlyHint if hasattr(ann, "readOnlyHint") else ann.read_only_hint,
        "destructiveHint": (
            ann.destructiveHint if hasattr(ann, "destructiveHint") else ann.destructive_hint
        ),
        "openWorldHint": (
            ann.openWorldHint if hasattr(ann, "openWorldHint") else ann.open_world_hint
        ),
        "idempotentHint": (
            ann.idempotentHint if hasattr(ann, "idempotentHint") else ann.idempotent_hint
        ),
    }


def _tools_by_name() -> dict[str, Any]:
    server = create_server()

    async def _list():
        return await server.list_tools()

    tools = asyncio.run(_list())
    return {tool.name: tool for tool in tools}


def test_validate_tool_binding_semantics_covers_all_public_tools() -> None:
    validate_tool_binding_semantics(TOOL_BINDINGS)
    names = list_tool_names()
    assert len(names) == len(TOOL_BINDINGS) == 41
    assert {b.name for b in TOOL_BINDINGS} == set(names)


def test_every_exported_tool_has_non_null_annotations() -> None:
    by_name = _tools_by_name()
    assert set(by_name) == set(list_tool_names())
    for name, tool in by_name.items():
        assert tool.annotations is not None, name


@pytest.mark.parametrize(
    "tool_name",
    [
        "get_instance_info",
        "list_sessions",
        "analyze_session",
        "get_cansub_device_status",
        "observe_live_traffic",
        "compare_experiment_windows",
        "rank_signal_candidates",
    ],
)
def test_read_tools_export_read_only_annotations(tool_name: str) -> None:
    flags = _annotation_flags(_tools_by_name()[tool_name])
    assert flags == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": True,
    }


@pytest.mark.parametrize(
    ("tool_name", "idempotent"),
    [
        ("start_live_capture", False),
        ("stop_live_capture", False),
        ("mark_experiment_event", False),
    ],
)
def test_write_orchestration_tools_export_expected_annotations(
    tool_name: str,
    idempotent: bool,
) -> None:
    flags = _annotation_flags(_tools_by_name()[tool_name])
    assert flags == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": idempotent,
    }


def test_write_policy_matches_binding_semantics() -> None:
    for binding in TOOL_BINDINGS:
        assert binding.semantic == expected_semantic_for_tool_name(binding.name)
    write_names = {
        b.name for b in TOOL_BINDINGS if b.semantic == ToolSemantic.WRITE_ORCHESTRATION
    }
    assert write_names == MCP_WRITE_ORCHESTRATION_TOOL_NAMES
