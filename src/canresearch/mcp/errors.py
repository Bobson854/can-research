"""Structured MCP tool errors."""

from __future__ import annotations


class McpToolError(Exception):
    """Expected failure surfaced as a structured MCP tool response."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


def limit_out_of_range(limit: int, *, maximum: int) -> McpToolError:
    return McpToolError(
        "limit_out_of_range",
        f"limit must be between 1 and {maximum}, got {limit}",
    )
