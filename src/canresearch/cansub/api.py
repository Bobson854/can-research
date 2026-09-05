"""CANsub.2 low-level API access."""

from __future__ import annotations

from dataclasses import dataclass

from canresearch.cansub.client import (
    CansubChannelStatus,
    CansubClient,
    CansubDeviceInfo,
    get_channel_info,
    probe_host,
)
from canresearch.cansub.exceptions import (
    CansubApiError,
    CansubConnectionError,
    CansubError,
    CansubFrameError,
    CansubIdentificationError,
    CansubWebSocketError,
)
from canresearch.cansub.ws_client import receive_frames_sync
from canresearch.cansub.ws_protocol import CansubFrame

__all__ = [
    "CansubChannelStatus",
    "CansubClient",
    "CansubDevice",
    "CansubDeviceInfo",
    "CansubFrame",
    "CansubApiError",
    "CansubConnectionError",
    "CansubError",
    "CansubFrameError",
    "CansubIdentificationError",
    "CansubWebSocketError",
    "connect",
    "disconnect",
    "get_channel_info",
    "probe_host",
    "receive_frames_sync",
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
