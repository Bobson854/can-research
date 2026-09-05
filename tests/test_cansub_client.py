"""Tests for CANsub.2 REST client."""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from canresearch.cansub.client import CansubClient
from canresearch.cansub.exceptions import (
    CansubApiError,
    CansubConnectionError,
    CansubIdentificationError,
)


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


def test_probe_success() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen(
            {
                "/api/version": (200, "03.00"),
                "/api/info": (
                    200,
                    {
                        "id": "7413f810",
                        "hw_ver": "01.00",
                        "fw_ver": "02.03.00",
                        "mac": "04916244365e",
                        "usb": "04D8&E487",
                    },
                ),
                "/api/can": (200, [1, 2]),
            }
        ),
    )

    info = client.probe()
    assert info.host == "example.test"
    assert info.api_version == "03.00"
    assert info.device_id == "7413f810"
    assert info.firmware_version == "02.03.00"
    assert info.channels == [1, 2]


def test_probe_timeout() -> None:
    def urlopen(*args: Any, **kwargs: Any) -> None:
        _ = args, kwargs
        raise URLError(TimeoutError("timed out"))

    client = CansubClient("example.test", urlopen=urlopen)
    with pytest.raises(CansubConnectionError, match="timeout"):
        client.probe()


def test_probe_connection_refused() -> None:
    def urlopen(*args: Any, **kwargs: Any) -> None:
        _ = args, kwargs
        raise URLError(ConnectionRefusedError("refused"))

    client = CansubClient("example.test", urlopen=urlopen)
    with pytest.raises(CansubConnectionError, match="connection refused"):
        client.probe()


def test_probe_non_200_version() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen({"/api/version": (500, "error")}),
    )
    with pytest.raises(CansubApiError, match="failed"):
        client.get_api_version()


def test_probe_invalid_version_format() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen({"/api/version": (200, "not-a-version")}),
    )
    with pytest.raises(CansubIdentificationError, match="identification failed"):
        client.get_api_version()


def test_probe_missing_device_id() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen(
            {
                "/api/version": (200, "03.00"),
                "/api/info": (200, {"hw_ver": "01.00"}),
            }
        ),
    )
    with pytest.raises(CansubIdentificationError, match="missing device id"):
        client.probe()


def test_probe_invalid_channel_list() -> None:
    client = CansubClient(
        "example.test",
        urlopen=_mock_urlopen(
            {
                "/api/version": (200, "03.00"),
                "/api/info": (200, {"id": "abcd1234"}),
                "/api/can": (200, {"channels": [1]}),
            }
        ),
    )
    with pytest.raises(CansubIdentificationError, match="channel list"):
        client.probe()


def test_abort_websocket_connection_active() -> None:
    calls: list[str] = []

    def urlopen(request: Any, timeout: float = 5.0, context: Any = None) -> _FakeResponse:
        _ = timeout, context
        calls.append(request.method)
        assert request.method == "DELETE"
        return _FakeResponse(200, b"")

    client = CansubClient("example.test", urlopen=urlopen)
    assert client.abort_websocket_connection(1) is True
    assert calls == ["DELETE"]


def test_abort_websocket_connection_idle() -> None:
    def urlopen(request: Any, timeout: float = 5.0, context: Any = None) -> _FakeResponse:
        _ = timeout, context
        raise HTTPError(request.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b""))

    client = CansubClient("example.test", urlopen=urlopen)
    assert client.abort_websocket_connection(1) is False
