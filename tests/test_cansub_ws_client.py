"""Tests for CANsub.2 WebSocket RX client."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import pytest

from canresearch.cansub.exceptions import CansubWebSocketError
from canresearch.cansub.ws_client import receive_frames, websocket_url
from canresearch.cansub.ws_protocol import _crc32_ieee8023

SINGLE_FRAME = bytes.fromhex("7E 00 00 00 00 00 00 01 00 01 00 42 2D 3E 52 7E")


def _build_hdlc(payload: bytes) -> bytes:
    crc = _crc32_ieee8023(payload).to_bytes(4, "big")
    return b"\x7e" + payload + crc + b"\x7e"


class FakeWebSocket:
    def __init__(self, messages: list[bytes | Exception]) -> None:
        self._messages = list(messages)

    async def recv(self) -> bytes:
        if not self._messages:
            await asyncio.sleep(3600)
        item = self._messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self, code: int = 1000, reason: str = "") -> None:
        _ = code, reason


def _fake_connect(messages: list[bytes | Exception]):
    @asynccontextmanager
    async def connect(_url: str, **kwargs: Any):
        _ = kwargs
        yield FakeWebSocket(messages)

    return connect


def _mock_channels(monkeypatch: pytest.MonkeyPatch, channels: list[int] | None = None) -> None:
    channels = channels if channels is not None else [1, 2]

    def fake_list(self) -> list[int]:
        return channels

    monkeypatch.setattr("canresearch.cansub.ws_client.CansubClient.list_channels", fake_list)


def _run(coro):
    return asyncio.run(coro)


def test_successful_connection_idle_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)
    result = _run(
        receive_frames(
            "example.test",
            1,
            duration=0.2,
            connect=_fake_connect([]),
        )
    )
    assert result.connected is True
    assert result.frame_count == 0
    assert result.exit_reason == "duration elapsed"


def test_receives_one_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)
    seen: list[int] = []

    def on_frame(frame) -> None:
        seen.append(frame.can_id or 0)

    result = _run(
        receive_frames(
            "example.test",
            1,
            duration=1.0,
            connect=_fake_connect([SINGLE_FRAME]),
            on_frame=on_frame,
        )
    )
    assert result.frame_count == 1
    assert seen == [0x001]


def test_receives_multiple_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)
    multi = bytes.fromhex(
        "7E 00 00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 01 00 02 02 "
        "00 00 00 00 00 00 01 00 03 03 00 00 00 00 00 00 01 00 04 04 D1 2C 1F D9 7E"
    )
    result = _run(
        receive_frames(
            "example.test",
            1,
            duration=1.0,
            connect=_fake_connect([multi]),
        )
    )
    assert result.frame_count == 4


def test_max_frames_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)
    multi = bytes.fromhex(
        "7E 00 00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 01 00 02 02 "
        "00 00 00 00 00 00 01 00 03 03 00 00 00 00 00 00 01 00 04 04 D1 2C 1F D9 7E"
    )
    result = _run(
        receive_frames(
            "example.test",
            1,
            duration=5.0,
            max_frames=2,
            connect=_fake_connect([multi]),
        )
    )
    assert result.frame_count == 2
    assert result.exit_reason == "max frames reached"


def test_malformed_frame_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)
    truncated = bytes.fromhex("00 00 00 00 00 00 01 00 01")
    malformed = _build_hdlc(truncated)
    with pytest.raises(CansubWebSocketError, match="Malformed"):
        _run(
            receive_frames(
                "example.test",
                1,
                duration=1.0,
                connect=_fake_connect([malformed]),
            )
        )


def test_invalid_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch, channels=[1, 2])
    with pytest.raises(CansubWebSocketError, match="channel 9 not found"):
        _run(
            receive_frames(
                "example.test",
                9,
                duration=0.2,
                connect=_fake_connect([]),
            )
        )


def test_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)

    @asynccontextmanager
    async def failing_connect(_url: str, **kwargs: Any):
        _ = kwargs
        raise ConnectionRefusedError("connection refused")
        yield  # pragma: no cover

    with pytest.raises(CansubWebSocketError, match="connection refused"):
        _run(
            receive_frames(
                "example.test",
                1,
                duration=0.2,
                connect=failing_connect,
            )
        )


def test_handshake_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)

    class InvalidStatus(Exception):
        pass

    @asynccontextmanager
    async def handshake_fail(_url: str, **kwargs: Any):
        _ = kwargs
        raise InvalidStatus("InvalidStatus: server rejected WebSocket connection: HTTP 403")
        yield  # pragma: no cover

    with pytest.raises(CansubWebSocketError, match="handshake rejected"):
        _run(
            receive_frames(
                "example.test",
                1,
                duration=0.2,
                connect=handshake_fail,
            )
        )


def test_unexpected_socket_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_channels(monkeypatch)

    class ConnectionClosed(Exception):
        pass

    with pytest.raises(CansubWebSocketError, match="closed unexpectedly|failed"):
        _run(
            receive_frames(
                "example.test",
                1,
                duration=1.0,
                connect=_fake_connect([ConnectionClosed("connection closed")]),
            )
        )


def test_websocket_url() -> None:
    assert websocket_url("device.local", 1) == "wss://device.local/api/can/1/ws"
    assert websocket_url("device.local", 2, port=8443) == "wss://device.local:8443/api/can/2/ws"
