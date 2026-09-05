"""Deterministic fake live CAN frame sources for tests."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from canresearch.cansub.ws_protocol import _crc32_ieee8023


def build_hdlc_payload(
    *,
    timestamp_us: int,
    can_id: int,
    data: bytes,
    channel: int = 1,
    extended: bool = True,
) -> bytes:
    """Build one HDLC-framed CANsub WebSocket message for a single frame."""
    flags = 0x01 if extended else 0x00
    dlc = len(data)
    payload = (
        (timestamp_us).to_bytes(8, "big")
        + bytes([channel & 0xFF])
        + bytes([flags])
        + (can_id).to_bytes(4, "big")
        + bytes([dlc])
        + data.ljust(8, b"\x00")[:8]
    )
    crc = _crc32_ieee8023(payload).to_bytes(4, "big")
    return b"\x7e" + payload + crc + b"\x7e"


@dataclass(frozen=True, slots=True)
class ScheduledFrame:
    timestamp_us: int
    can_id: int
    data: bytes
    channel: int = 1
    extended: bool = True


class FakeLiveFrameSource:
    """Emit deterministic CAN frames through the WebSocket connect hook."""

    def __init__(self, frames: list[ScheduledFrame]) -> None:
        self.frames = list(frames)

    def connect(self):
        messages = [
            build_hdlc_payload(
                timestamp_us=frame.timestamp_us,
                can_id=frame.can_id,
                data=frame.data,
                channel=frame.channel,
                extended=frame.extended,
            )
            for frame in self.frames
        ]

        @asynccontextmanager
        async def _connect(_url: str, **kwargs: Any):
            _ = kwargs

            class _WS:
                def __init__(self) -> None:
                    self._index = 0

                async def recv(self) -> bytes:
                    if self._index >= len(messages):
                        await asyncio.sleep(3600)
                    item = messages[self._index]
                    self._index += 1
                    return item

                async def close(self, code: int = 1000, reason: str = "") -> None:
                    _ = code, reason

            yield _WS()

        return _connect
