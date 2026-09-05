"""CANsub.2 WebSocket RX client."""

from __future__ import annotations

import asyncio
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from canresearch.cansub.client import DEFAULT_PORT, DEFAULT_SCHEME, CansubClient
from canresearch.cansub.exceptions import (
    CansubApiError,
    CansubConnectionError,
    CansubFrameError,
    CansubWebSocketError,
)
from canresearch.cansub.ws_protocol import CansubFrame, HdlcFrameParser

DEFAULT_RX_DURATION = 5.0
WS_OPEN_TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class CansubRxResult:
    """Summary of a read-only WebSocket RX session."""

    host: str
    channel: int
    connected: bool
    duration_s: float
    frame_count: int
    exit_reason: str


class WebSocketConnection(Protocol):
    async def recv(self) -> str | bytes: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


ConnectFn = Callable[..., Any]


def websocket_url(
    host: str,
    channel: int,
    *,
    scheme: str = DEFAULT_SCHEME,
    port: int = DEFAULT_PORT,
) -> str:
    """Build the CANsub.2 WebSocket URL for a channel."""
    ws_scheme = "wss" if scheme == "https" else "ws"
    if (scheme, port) in {("https", 443), ("http", 80)}:
        return f"{ws_scheme}://{host}/api/can/{channel}/ws"
    return f"{ws_scheme}://{host}:{port}/api/can/{channel}/ws"


def _ssl_context(*, verify_tls: bool) -> ssl.SSLContext | None:
    context = ssl.create_default_context()
    if verify_tls:
        return context
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _validate_channel(host: str, channel: int, *, timeout: float, verify_tls: bool) -> None:
    client = CansubClient(host, timeout=timeout, verify_tls=verify_tls)
    try:
        channels = client.list_channels()
    except (CansubApiError, CansubConnectionError) as exc:
        raise CansubWebSocketError(str(exc)) from exc
    if channel not in channels:
        available = ", ".join(map(str, channels))
        msg = f"CAN channel {channel} not found on {host} (available: {available})"
        raise CansubWebSocketError(msg)


async def receive_frames(
    host: str,
    channel: int,
    *,
    duration: float = DEFAULT_RX_DURATION,
    max_frames: int | None = None,
    timeout: float = 5.0,
    verify_tls: bool = False,
    on_frame: Callable[[CansubFrame], None] | None = None,
    connect: ConnectFn | None = None,
) -> CansubRxResult:
    """Connect to the CANsub WebSocket and receive frames for a duration."""
    if duration <= 0:
        msg = "Duration must be positive"
        raise CansubWebSocketError(msg)
    if max_frames is not None and max_frames <= 0:
        msg = "max_frames must be positive when set"
        raise CansubWebSocketError(msg)

    _validate_channel(host, channel, timeout=timeout, verify_tls=verify_tls)

    url = websocket_url(host, channel)
    ssl_context = _ssl_context(verify_tls=verify_tls)
    connect_fn = connect or _default_connect

    parser = HdlcFrameParser()
    frame_count = 0
    started = time.monotonic()
    deadline = started + duration
    exit_reason = "duration elapsed"

    try:
        async with connect_fn(
            url,
            open_timeout=WS_OPEN_TIMEOUT,
            ssl=ssl_context,
            ping_interval=None,
            close_timeout=2.0,
        ) as ws:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except TimeoutError:
                    break
                if not isinstance(message, bytes):
                    msg = "Unexpected text WebSocket message from CANsub.2"
                    raise CansubWebSocketError(msg)
                try:
                    frames = parser.parse_frames(message, channel=channel)
                except CansubFrameError as exc:
                    msg = f"Malformed CANsub.2 frame on channel {channel}: {exc}"
                    raise CansubWebSocketError(msg) from exc
                for frame in frames:
                    frame_count += 1
                    if on_frame is not None:
                        on_frame(frame)
                    if max_frames is not None and frame_count >= max_frames:
                        exit_reason = "max frames reached"
                        return CansubRxResult(
                            host=host,
                            channel=channel,
                            connected=True,
                            duration_s=time.monotonic() - started,
                            frame_count=frame_count,
                            exit_reason=exit_reason,
                        )
    except asyncio.CancelledError:
        exit_reason = "interrupted"
        raise
    except TimeoutError as exc:
        msg = f"WebSocket connection to {host} timed out"
        raise CansubWebSocketError(msg) from exc
    except CansubWebSocketError:
        raise
    except Exception as exc:
        msg = _connection_error_message(host, exc)
        raise CansubWebSocketError(msg) from exc

    return CansubRxResult(
        host=host,
        channel=channel,
        connected=True,
        duration_s=time.monotonic() - started,
        frame_count=frame_count,
        exit_reason=exit_reason,
    )


def _default_connect(url: str, **kwargs: Any) -> Any:
    import websockets

    return websockets.connect(url, **kwargs)


def receive_frames_sync(
    host: str,
    channel: int,
    *,
    duration: float = DEFAULT_RX_DURATION,
    max_frames: int | None = None,
    timeout: float = 5.0,
    verify_tls: bool = False,
    on_frame: Callable[[CansubFrame], None] | None = None,
    connect: ConnectFn | None = None,
) -> CansubRxResult:
    """Synchronous wrapper around receive_frames()."""
    return asyncio.run(
        receive_frames(
            host,
            channel,
            duration=duration,
            max_frames=max_frames,
            timeout=timeout,
            verify_tls=verify_tls,
            on_frame=on_frame,
            connect=connect,
        )
    )


def _connection_error_message(host: str, exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc).strip()
    lowered = text.lower()
    if "invalidstatus" in name.lower() or "invalid status" in lowered:
        return f"WebSocket handshake rejected by CANsub.2 at {host}: {text or name}"
    if "gaierror" in name.lower() or "getaddrinfo" in lowered:
        return f"Unable to resolve CANsub.2 host {host}: {text or name}"
    if "certificate" in lowered or "ssl" in lowered:
        return f"TLS error connecting to CANsub.2 at {host}: {text or name}"
    if "connection refused" in lowered:
        return f"Unable to connect to CANsub.2 at {host}: connection refused"
    if "timeout" in lowered:
        return f"WebSocket connection to {host} timed out"
    if "connection closed" in lowered or "connectionclosed" in name.lower():
        return f"CANsub.2 WebSocket closed unexpectedly: {text or name}"
    return f"WebSocket connection to {host} failed: {text or name}"
