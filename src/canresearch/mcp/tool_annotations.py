"""MCP ToolAnnotations policy for CAN Research public tools."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from mcp_types import ToolAnnotations


class ToolSemantic(StrEnum):
    """Project-specific MCP tool semantics (not MCP wire enums)."""

    READ = "read"
    WRITE_ORCHESTRATION = "write_orchestration"


MCP_WRITE_ORCHESTRATION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "start_live_capture",
        "stop_live_capture",
        "mark_experiment_event",
    }
)


# Retry semantics for write orchestration tools (local session/event state).
WRITE_ORCHESTRATION_IDEMPOTENT: dict[str, bool] = {
    "start_live_capture": False,
    "stop_live_capture": False,
    "mark_experiment_event": False,
}


class _SemanticBinding(Protocol):
    name: str
    semantic: ToolSemantic


def expected_semantic_for_tool_name(name: str) -> ToolSemantic:
    if name in MCP_WRITE_ORCHESTRATION_TOOL_NAMES:
        return ToolSemantic.WRITE_ORCHESTRATION
    return ToolSemantic.READ


def tool_annotations_for_semantic(
    semantic: ToolSemantic,
    *,
    tool_name: str,
) -> ToolAnnotations:
    if semantic == ToolSemantic.READ:
        return ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=False,
            idempotentHint=True,
        )
    if semantic == ToolSemantic.WRITE_ORCHESTRATION:
        return ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=False,
            idempotentHint=WRITE_ORCHESTRATION_IDEMPOTENT.get(tool_name, False),
        )
    msg = f"Unhandled tool semantic: {semantic}"
    raise ValueError(msg)


def tool_annotations_for_binding(binding: _SemanticBinding) -> ToolAnnotations:
    return tool_annotations_for_semantic(binding.semantic, tool_name=binding.name)


def validate_tool_binding_semantics(bindings: tuple[_SemanticBinding, ...]) -> None:
    """Fail fast when a public tool lacks explicit semantic classification."""
    seen: set[str] = set()
    for binding in bindings:
        if binding.name in seen:
            msg = f"Duplicate MCP tool name: {binding.name}"
            raise ValueError(msg)
        seen.add(binding.name)
        expected = expected_semantic_for_tool_name(binding.name)
        if binding.semantic != expected:
            msg = (
                f"Tool {binding.name!r} semantic {binding.semantic.value} "
                f"does not match policy expectation {expected.value}"
            )
            raise ValueError(msg)

    policy_names = {b.name for b in bindings}
    extra_writes = MCP_WRITE_ORCHESTRATION_TOOL_NAMES - policy_names
    if extra_writes:
        msg = f"Write tool policy names not registered: {sorted(extra_writes)}"
        raise ValueError(msg)
