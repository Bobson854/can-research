"""CANsub.2 REST API client."""

from __future__ import annotations

import json
import re
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from canresearch.cansub.exceptions import (
    CansubApiError,
    CansubConnectionError,
    CansubIdentificationError,
)

API_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")
DEFAULT_TIMEOUT = 5.0
DEFAULT_SCHEME = "https"
DEFAULT_PORT = 443

UrlOpen = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class CansubDeviceInfo:
    """Read-only device information from the CANsub.2 REST API."""

    host: str
    status: str = "reachable"
    api_version: str | None = None
    device_id: str | None = None
    hardware_version: str | None = None
    firmware_version: str | None = None
    mac_address: str | None = None
    usb_id: str | None = None
    channels: list[int] = field(default_factory=list)
    raw_info: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CansubChannelStatus:
    """Read-only CAN channel status from GET /api/can/{channel}."""

    channel: int
    host: str
    state: str | None = None
    frame_count: int | None = None
    frame_rate: int | None = None
    bus_load: int | None = None
    rx_error_count: int | None = None
    tx_error_count: int | None = None
    bus_error_count: int | None = None
    phy: dict[str, Any] | None = None
    raw_status: dict[str, Any] | None = None


class CansubClient:
    """Minimal read-only client for the CANsub.2 HTTPS REST API."""

    def __init__(
        self,
        host: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        scheme: str = DEFAULT_SCHEME,
        port: int = DEFAULT_PORT,
        verify_tls: bool = False,
        urlopen: UrlOpen | None = None,
    ) -> None:
        self.host = host.strip()
        self.timeout = timeout
        self.scheme = scheme
        self.port = port
        self.verify_tls = verify_tls
        self._urlopen = urlopen or urllib.request.urlopen

    def _base_url(self) -> str:
        if (self.scheme, self.port) in {("https", 443), ("http", 80)}:
            return f"{self.scheme}://{self.host}"
        return f"{self.scheme}://{self.host}:{self.port}"

    def _ssl_context(self) -> ssl.SSLContext | None:
        if self.scheme != "https":
            return None
        if self.verify_tls:
            return ssl.create_default_context()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _request(self, path: str) -> tuple[int, bytes]:
        url = f"{self._base_url()}{path}"
        request = urllib.request.Request(url, method="GET")
        try:
            with self._urlopen(
                request, timeout=self.timeout, context=self._ssl_context()
            ) as response:
                status = getattr(response, "status", 200)
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise CansubApiError(
                    f"CANsub.2 resource not found: {path}",
                    status_code=404,
                ) from exc
            raise CansubApiError(
                f"CANsub.2 API request failed ({exc.code}) for {path}",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError):
                msg = f"Unable to connect to CANsub.2 at {self.host}: timeout"
            elif isinstance(reason, ConnectionRefusedError):
                msg = f"Unable to connect to CANsub.2 at {self.host}: connection refused"
            elif isinstance(reason, socket.gaierror):
                msg = f"Unable to resolve CANsub.2 host {self.host}: {reason}"
            else:
                msg = f"Unable to connect to CANsub.2 at {self.host}: {reason}"
            raise CansubConnectionError(msg) from exc
        except TimeoutError as exc:
            raise CansubConnectionError(
                f"Unable to connect to CANsub.2 at {self.host}: timeout"
            ) from exc

        return status, body

    @staticmethod
    def _decode_json(body: bytes) -> Any:
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CansubIdentificationError(
                "Host responded, but CANsub.2 API identification failed: invalid JSON"
            ) from exc

    def get_api_version(self) -> str:
        """GET /api/version — returns API version string (MAJOR.MINOR)."""
        status, body = self._request("/api/version")
        if status != 200:
            raise CansubApiError(
                f"CANsub.2 API version request failed with status {status}",
                status_code=status,
            )
        payload = self._decode_json(body)
        if not isinstance(payload, str) or not API_VERSION_PATTERN.match(payload):
            raise CansubIdentificationError(
                "Host responded, but CANsub.2 API identification failed: unexpected version format"
            )
        return payload

    def get_device_info(self) -> dict[str, Any]:
        """GET /api/info — returns device information object."""
        status, body = self._request("/api/info")
        if status != 200:
            raise CansubApiError(
                f"CANsub.2 device info request failed with status {status}",
                status_code=status,
            )
        payload = self._decode_json(body)
        if not isinstance(payload, dict):
            raise CansubIdentificationError(
                "Host responded, but CANsub.2 API identification failed: /api/info is not an object"
            )
        return payload

    def list_channels(self) -> list[int]:
        """GET /api/can — returns available CAN channel numbers."""
        status, body = self._request("/api/can")
        if status != 200:
            raise CansubApiError(
                f"CANsub.2 channel list request failed with status {status}",
                status_code=status,
            )
        payload = self._decode_json(body)
        if not isinstance(payload, list) or not all(isinstance(item, int) for item in payload):
            raise CansubIdentificationError(
                "Host responded, but CANsub.2 API identification failed: "
                "/api/can is not a channel list"
            )
        return payload

    def get_json(self, path: str) -> Any:
        """GET a JSON endpoint and return the decoded payload."""
        status, body = self._request(path)
        if status != 200:
            raise CansubApiError(
                f"CANsub.2 API request failed with status {status} for {path}",
                status_code=status,
            )
        return self._decode_json(body)

    def get_channel_status(self, channel: int) -> dict[str, Any]:
        """GET /api/can/{channel} — returns channel status object."""
        payload = self.get_json(f"/api/can/{channel}")
        if not isinstance(payload, dict):
            raise CansubIdentificationError(
                f"Unexpected CANsub.2 channel {channel} response: expected object"
            )
        return payload

    def get_channel_phy(self, channel: int) -> dict[str, Any]:
        """GET /api/can/{channel}/phy — returns read-only PHY configuration."""
        payload = self.get_json(f"/api/can/{channel}/phy")
        if not isinstance(payload, dict):
            raise CansubIdentificationError(
                f"Unexpected CANsub.2 channel {channel} PHY response: expected object"
            )
        return payload

    def get_channel_info(self, channel: int, *, include_phy: bool = True) -> CansubChannelStatus:
        """Return read-only channel status (and optional PHY configuration)."""
        status = self.get_channel_status(channel)
        phy = self.get_channel_phy(channel) if include_phy else None
        return CansubChannelStatus(
            channel=channel,
            host=self.host,
            state=_as_str(status.get("state")),
            frame_count=_as_int(status.get("frame_count")),
            frame_rate=_as_int(status.get("frame_rate")),
            bus_load=_as_int(status.get("bus_load")),
            rx_error_count=_as_int(status.get("rx_error_count")),
            tx_error_count=_as_int(status.get("tx_error_count")),
            bus_error_count=_as_int(status.get("bus_error_count")),
            phy=phy,
            raw_status=status,
        )

    def probe(self) -> CansubDeviceInfo:
        """Verify CANsub.2 identity and return read-only device information."""
        api_version = self.get_api_version()
        info = self.get_device_info()
        device_id = info.get("id")
        if not isinstance(device_id, str) or not device_id:
            raise CansubIdentificationError(
                "Host responded, but CANsub.2 API identification failed: missing device id"
            )

        channels = self.list_channels()
        return CansubDeviceInfo(
            host=self.host,
            api_version=api_version,
            device_id=device_id,
            hardware_version=_as_str(info.get("hw_ver")),
            firmware_version=_as_str(info.get("fw_ver")),
            mac_address=_as_str(info.get("mac")),
            usb_id=_as_str(info.get("usb")),
            channels=channels,
            raw_info=info,
        )


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def probe_host(
    host: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    verify_tls: bool = False,
) -> CansubDeviceInfo:
    """Connect directly to a CANsub.2 host and return device information."""
    return CansubClient(host, timeout=timeout, verify_tls=verify_tls).probe()


def get_channel_info(
    host: str,
    channel: int,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    verify_tls: bool = False,
    include_phy: bool = True,
) -> CansubChannelStatus:
    """Connect to a CANsub.2 host and return read-only channel information."""
    return CansubClient(
        host, timeout=timeout, verify_tls=verify_tls
    ).get_channel_info(channel, include_phy=include_phy)
