"""CANsub.2 low-level API access."""

from __future__ import annotations

from dataclasses import dataclass

from canresearch.cansub.client import CansubClient, CansubDeviceInfo, probe_host
from canresearch.cansub.exceptions import (
    CansubApiError,
    CansubConnectionError,
    CansubError,
    CansubIdentificationError,
)

__all__ = [
    "CansubClient",
    "CansubDevice",
    "CansubDeviceInfo",
    "CansubApiError",
    "CansubConnectionError",
    "CansubError",
    "CansubIdentificationError",
    "connect",
    "disconnect",
    "probe_host",
]


@dataclass(frozen=True, slots=True)
class CansubDevice:
    """Discovered CANsub.2 device."""

    device_id: str
    connection: str  # "usb" or "ethernet"
    address: str
    label: str | None = None


def connect(device_id: str) -> None:
    """Open a connection to a CANsub.2 device."""
    raise NotImplementedError("Persistent CANsub.2 sessions are not yet implemented")


def disconnect() -> None:
    """Close the active CANsub.2 connection."""
    raise NotImplementedError("Persistent CANsub.2 sessions are not yet implemented")
