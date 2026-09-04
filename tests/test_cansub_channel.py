"""Tests for CANsub channel status client."""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.error import HTTPError

import pytest

from canresearch.cansub.client import CansubClient
from canresearch.cansub.exceptions import CansubApiError, CansubIdentificationError


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _mock_urlopen(responses: dict[str, tuple[int, Any]]) -> Any:
    def urlopen(request: Any, timeout: float = 5.0, context: Any = None) -> _FakeResponse:
        _ = timeout, context
        path = request.full_url.split("example.test", 1)[1]
        if path not in responses:
            msg = f"Unexpected path: {path}"
            raise AssertionError(msg)
        status, payload = responses[path]
        body = json.dumps(payload).encode("utf-8")
        if status >= 400:
            raise HTTPError(request.full_url, status, "error", hdrs=None, fp=io.BytesIO(body))
        return _FakeResponse(status, body)

    return urlopen


STATUS = {
    "state": "stopped",
    "frame_count": 0,
    "frame_rate": 0,
    "bus_load": 0,
    "rx_error_count": 0,
    "tx_error_count": 0,
    "bus_error_count": 0,
}

PHY = {
    "listen_only": False,
    "auto_reset": True,
    "error_frames": False,
    "timing": {"brp": 4, "seg1": 63, "seg2": 16, "sjw": 4},
    "timing_data": {"brp": 4, "seg1": 15, "seg2": 4, "sjw": 4},
}


def test_channel_1_status() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen(
            {
                "/api/can/1": (200, STATUS),
                "/api/can/1/phy": (200, PHY),
            }
        ),
    )
    info = client.get_channel_info(1)
    assert info.channel == 1
    assert info.state == "stopped"
    assert info.frame_count == 0
    assert info.phy == PHY


def test_channel_2_status() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen(
            {
                "/api/can/2": (200, STATUS),
                "/api/can/2/phy": (200, PHY),
            }
        ),
    )
    info = client.get_channel_info(2)
    assert info.channel == 2


def test_channel_not_found() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen({"/api/can/9": (404, {"error": "not found"})}),
    )
    with pytest.raises(CansubApiError, match="not found"):
        client.get_channel_status(9)


def test_channel_malformed_response() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen({"/api/can/1": (200, ["bad"])}),
    )
    with pytest.raises(CansubIdentificationError, match="expected object"):
        client.get_channel_status(1)
