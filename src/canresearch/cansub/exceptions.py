"""CANsub.2 client errors."""

from __future__ import annotations


class CansubError(Exception):
    """Base error for CANsub.2 operations."""


class CansubConnectionError(CansubError):
    """Host unreachable or HTTP connection failed."""


class CansubApiError(CansubError):
    """CANsub.2 REST API returned an error response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CansubIdentificationError(CansubError):
    """Host responded but did not identify as a CANsub.2 device."""
