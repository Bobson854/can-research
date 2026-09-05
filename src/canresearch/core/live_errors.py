"""Structured errors for live CANsub research operations."""

from __future__ import annotations


class LiveResearchError(Exception):
    """Expected failure in live research workflows."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}
