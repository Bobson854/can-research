"""CANsub.2 low-level API access (stub)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CansubDevice:
    """Discovered CANsub.2 device."""

    device_id: str
    connection: str  # "usb" or "ethernet"
    address: str
    label: str | None = None


def connect(device_id: str) -> None:
    """Open a connection to a CANsub.2 device."""
    raise NotImplementedError("CANsub.2 connect is not yet implemented")


def disconnect() -> None:
    """Close the active CANsub.2 connection."""
    raise NotImplementedError("CANsub.2 disconnect is not yet implemented")
