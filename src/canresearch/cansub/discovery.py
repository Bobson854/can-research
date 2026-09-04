"""CANsub.2 device discovery over USB and Ethernet."""

from __future__ import annotations

from canresearch.cansub.api import CansubDevice
from canresearch.cansub.client import CansubDeviceInfo, probe_host

__all__ = ["CansubDevice", "CansubDeviceInfo", "discover_devices", "probe_host"]


def discover_devices() -> list[CansubDevice]:
    """Scan for connected CANsub.2 devices."""
    return []
