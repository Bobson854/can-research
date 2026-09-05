"""CANsub.2 WebSocket RX client."""

from __future__ import annotations

import asyncio
import contextlib
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
WS_CLOSE_TIMEOUT = 2.0
WS_SLOT_RELEASE_DELAY_S = 0.25
WS_CONNECT_ATTEMPTS = 2
EARLY_CLOSE_THRESHOLD_S = 1.0


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


def _release_websocket_slot(
    host: str,
    channel: int,
    *,
    timeout: float,
    verify_tls: bool,
) -> bool:
    """Abort any active WebSocket on the channel (CANsub DELETE /api/can/{channel}/ws)."""
    client = CansubClient(host, timeout=timeout, verify_tls=verify_tls)
    try:
        return client.abort_websocket_connection(channel)
    except (CansubApiError, CansubConnectionError) as exc:
        raise CansubWebSocketError(str(exc)) from exc


def _channel_in_use_message(host: str, channel: int) -> str:
    return (
        f"CAN channel {channel} WebSocket on {host} is in use by another client "
        "(CANsub.2 allows one WebSocket per channel). Close webCAN or other listeners "
        "and retry."
    )


def _is_connection_closed(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    if "connectionclosed" in name:
        return True
    lowered = str(exc).lower()
    return "connection closed" in lowered or "1005" in lowered


async def _graceful_close(
    ws: WebSocketConnection,
    host: str,
    channel: int,
    *,
    timeout: float,
    verify_tls: bool,
) -> None:
    """Close the WebSocket using CANsub's recommended handshake (+ DELETE fallback)."""
    try:
        await asyncio.wait_for(ws.close(code=1000), timeout=WS_CLOSE_TIMEOUT)
    except (TimeoutError, Exception):
        with contextlib.suppress(CansubWebSocketError):
            _release_websocket_slot(host, channel, timeout=timeout, verify_tls=verify_tls)


async def _receive_frames_once(
    host: str,
    channel: int,
    *,
    duration: float,
    max_frames: int | None,
    timeout: float,
    verify_tls: bool,
    on_frame: Callable[[CansubFrame], None] | None,
    connect_fn: ConnectFn,
    stop_check: Callable[[], bool] | None,
) -> CansubRxResult:
    url = websocket_url(host, channel)
    ssl_context = _ssl_context(verify_tls=verify_tls)
    parser = HdlcFrameParser()
    frame_count = 0
    started = time.monotonic()
    deadline = started + duration
    exit_reason = "duration elapsed"

    from websockets.exceptions import ConnectionClosed

    try:
        async with connect_fn(
            url,
            open_timeout=WS_OPEN_TIMEOUT,
            ssl=ssl_context,
            ping_interval=None,
            close_timeout=WS_CLOSE_TIMEOUT,
        ) as ws:
            while True:
                if stop_check is not None and stop_check():
                    exit_reason = "stopped"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except TimeoutError:
                    break
                except ConnectionClosed as exc:
                    elapsed = time.monotonic() - started
                    if frame_count == 0 and elapsed < EARLY_CLOSE_THRESHOLD_S:
                        raise CansubWebSocketError(
                            _channel_in_use_message(host, channel)
                        ) from exc
                    exit_reason = "connection closed"
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
                        await _graceful_close(
                            ws, host, channel, timeout=timeout, verify_tls=verify_tls
                        )
                        return CansubRxResult(
                            host=host,
                            channel=channel,
                            connected=True,
                            duration_s=time.monotonic() - started,
                            frame_count=frame_count,
                            exit_reason=exit_reason,
                        )
            await _graceful_close(
                ws, host, channel, timeout=timeout, verify_tls=verify_tls
            )
    except asyncio.CancelledError:
        exit_reason = "interrupted"
        raise
    except CansubWebSocketError:
        raise
    except TimeoutError as exc:
        msg = f"WebSocket connection to {host} timed out"
        raise CansubWebSocketError(msg) from exc
    except Exception as exc:
        if _is_connection_closed(exc):
            elapsed = time.monotonic() - started
            if frame_count == 0 and elapsed < EARLY_CLOSE_THRESHOLD_S:
                raise CansubWebSocketError(
                    _channel_in_use_message(host, channel)
                ) from exc
            exit_reason = "connection closed"
        else:
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
    stop_check: Callable[[], bool] | None = None,
    release_slot: bool = True,
) -> CansubRxResult:
    """Connect to the CANsub WebSocket and receive frames for a duration."""
    if duration <= 0:
        msg = "Duration must be positive"
        raise CansubWebSocketError(msg)
    if max_frames is not None and max_frames <= 0:
        msg = "max_frames must be positive when set"
        raise CansubWebSocketError(msg)

    _validate_channel(host, channel, timeout=timeout, verify_tls=verify_tls)
    connect_fn = connect or _default_connect

    last_error: CansubWebSocketError | None = None
    attempts = WS_CONNECT_ATTEMPTS if release_slot else 1
    for attempt in range(attempts):
        if release_slot:
            aborted = _release_websocket_slot(
                host, channel, timeout=timeout, verify_tls=verify_tls
            )
            if aborted:
                await asyncio.sleep(WS_SLOT_RELEASE_DELAY_S)
        try:
            return await _receive_frames_once(
                host,
                channel,
                duration=duration,
                max_frames=max_frames,
                timeout=timeout,
                verify_tls=verify_tls,
                on_frame=on_frame,
                connect_fn=connect_fn,
                stop_check=stop_check,
            )
        except CansubWebSocketError as exc:
            if "in use by another client" not in str(exc):
                raise
            last_error = exc
            if attempt + 1 >= attempts:
                raise
    if last_error is not None:
        raise last_error
    msg = f"WebSocket connection to {host} failed"
    raise CansubWebSocketError(msg)


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
    stop_check: Callable[[], bool] | None = None,
    release_slot: bool = True,
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
            stop_check=stop_check,
            release_slot=release_slot,
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
    if _is_connection_closed(exc):
        return f"CANsub.2 WebSocket closed unexpectedly: {text or name}"
    return f"WebSocket connection to {host} failed: {text or name}"
