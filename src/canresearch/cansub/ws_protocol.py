"""CANsub.2 WebSocket binary protocol (HDLC + CAN frame serialization).

See: https://canlogger.csselectronics.com/cansub-docs/cansub2/api/api_ws.html
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from canresearch.cansub.exceptions import CansubFrameError

HDLC_BOUNDARY = 0x7E
HDLC_ESCAPE = 0x7D
HDLC_ESCAPE_XOR = 0x20
TIMESTAMP_EPOCH_US = 1735689600000000
TIMESTAMP_EPOCH_S = 1735689600

CANFD_DLC_LENGTHS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64)


class CansubErrorKind(IntEnum):
    BIT = 0
    ACK = 1
    FORM = 2
    STUFF = 3
    CRC = 4


ERROR_KIND_LABELS = {
    CansubErrorKind.BIT: "BIT ERROR",
    CansubErrorKind.ACK: "ACK ERROR",
    CansubErrorKind.FORM: "FORM ERROR",
    CansubErrorKind.STUFF: "STUFF ERROR",
    CansubErrorKind.CRC: "CRC ERROR",
}


@dataclass(frozen=True, slots=True)
class CansubFrame:
    """One CAN bus frame from the CANsub WebSocket stream."""

    channel: int
    timestamp_us: int
    can_id: int | None
    extended: bool
    fd: bool
    rtr: bool
    brs: bool
    esi: bool
    tx_ack: bool
    dlc: int | None
    data: bytes
    is_error_frame: bool
    error_type: str | None
    raw: bytes


class HdlcFrameParser:
    """Incremental parser for HDLC-framed CANsub WebSocket binary messages."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._in_frame = False
        self._frame = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        """Feed raw WebSocket bytes; return unstuffed payloads with valid CRC."""
        payloads: list[bytes] = []
        for byte in chunk:
            if byte == HDLC_BOUNDARY:
                if self._in_frame and self._frame:
                    payload = _decode_hdlc_frame(bytes(self._frame))
                    if payload is not None:
                        payloads.append(payload)
                self._in_frame = True
                self._frame.clear()
                continue
            if self._in_frame:
                self._frame.append(byte)
        return payloads

    def parse_frames(self, chunk: bytes, *, channel: int) -> list[CansubFrame]:
        """Feed bytes and return parsed CAN frames."""
        frames: list[CansubFrame] = []
        for payload in self.feed(chunk):
            if not payload:
                continue
            parsed = parse_can_payload(payload, channel=channel)
            if not parsed:
                msg = "unable to decode CAN payload"
                raise CansubFrameError(msg)
            frames.extend(parsed)
        return frames


def decode_timestamp_us(data: bytes) -> int:
    """Decode CANsub's 48-bit big-endian timestamp to absolute UTC microseconds.

    Wire format: microseconds since 2025-01-01 00:00:00 UTC (see CANsub WS API).
    """
    if len(data) < 6:
        msg = f"Not enough data bytes for CANsub timestamp ({len(data)} bytes)"
        raise CansubFrameError(msg)
    timestamp_rel_us = int.from_bytes(data[0:6], "big")
    return TIMESTAMP_EPOCH_US + timestamp_rel_us


def parse_can_payload(payload: bytes, *, channel: int) -> list[CansubFrame]:
    """Parse one or more serialized CAN frames from an HDLC payload."""
    frames: list[CansubFrame] = []
    offset = 0
    while offset < len(payload):
        try:
            frame, consumed = parse_can_frame(payload[offset:], channel=channel)
        except CansubFrameError:
            break
        frames.append(frame)
        if consumed <= 0:
            break
        offset += consumed
    return frames


def parse_can_frame(data: bytes, *, channel: int) -> tuple[CansubFrame, int]:
    """Parse a single serialized CAN frame."""
    if len(data) < 7:
        msg = f"Not enough data bytes for CAN frame ({len(data)} bytes)"
        raise CansubFrameError(msg)

    timestamp_us = decode_timestamp_us(data)
    flags6 = data[6]

    is_error = (flags6 & 0xA0) == 0x20
    if is_error:
        error_code = data[7] & 0x07 if len(data) >= 8 else 0
        try:
            error_type = ERROR_KIND_LABELS[CansubErrorKind(error_code)]
        except ValueError:
            error_type = f"ERROR {error_code}"
        raw = data[:8] if len(data) >= 8 else data[:7]
        consumed = 8 if len(data) >= 8 else 7
        return (
            CansubFrame(
                channel=channel,
                timestamp_us=timestamp_us,
                can_id=None,
                extended=False,
                fd=False,
                rtr=False,
                brs=False,
                esi=False,
                tx_ack=False,
                dlc=None,
                data=b"",
                is_error_frame=True,
                error_type=error_type,
                raw=raw,
            ),
            consumed,
        )

    if len(data) < 8:
        msg = f"Not enough data bytes for CAN frame ({len(data)} bytes)"
        raise CansubFrameError(msg)

    flags7 = data[7]
    fd = bool(flags6 & 0x80)
    rtr = bool(flags6 & 0x40)
    tx_ack = bool(flags6 & 0x10)
    dlc = flags6 & 0x0F
    extended = bool(flags7 & 0x80)

    if extended:
        can_id = (
            (flags7 & 0x1F) << 24 | data[8] << 16 | data[9] << 8 | data[10]
        ) & 0x1FFFFFFF
        header_len = 11
    else:
        can_id = ((flags7 & 0x07) << 8 | data[8]) & 0x7FF
        header_len = 9

    data_len = 0 if rtr else _data_length(dlc, fd=fd)
    total_len = header_len + data_len
    if len(data) < total_len:
        msg = f"Not enough data bytes for payload (need {total_len}, got {len(data)})"
        raise CansubFrameError(msg)

    payload = data[header_len:total_len]
    raw = data[:total_len]
    return (
        CansubFrame(
            channel=channel,
            timestamp_us=timestamp_us,
            can_id=can_id,
            extended=extended,
            fd=fd,
            rtr=rtr,
            brs=bool(flags6 & 0x20) if fd else False,
            esi=bool(flags6 & 0x08) if fd else False,
            tx_ack=tx_ack,
            dlc=dlc,
            data=payload,
            is_error_frame=False,
            error_type=None,
            raw=raw,
        ),
        total_len,
    )


def _data_length(dlc: int, *, fd: bool) -> int:
    if fd:
        if dlc >= len(CANFD_DLC_LENGTHS):
            msg = f"Invalid CAN FD DLC: {dlc}"
            raise CansubFrameError(msg)
        return CANFD_DLC_LENGTHS[dlc]
    if dlc > 8:
        msg = f"Invalid classical CAN DLC: {dlc}"
        raise CansubFrameError(msg)
    return dlc


def _decode_hdlc_frame(stuffed: bytes) -> bytes | None:
    try:
        unstuffed = _unstuff_bytes(stuffed)
    except CansubFrameError:
        return None
    if len(unstuffed) < 4:
        return None
    payload, crc_bytes = unstuffed[:-4], unstuffed[-4:]
    expected_crc = int.from_bytes(crc_bytes, "big")
    actual_crc = _crc32_ieee8023(payload)
    if actual_crc != expected_crc:
        return None
    return payload


def _unstuff_bytes(data: bytes) -> bytes:
    out = bytearray()
    idx = 0
    while idx < len(data):
        byte = data[idx]
        if byte == HDLC_ESCAPE:
            if idx + 1 >= len(data):
                msg = "Unexpected end of HDLC escape sequence"
                raise CansubFrameError(msg)
            out.append(data[idx + 1] ^ HDLC_ESCAPE_XOR)
            idx += 2
            continue
        out.append(byte)
        idx += 1
    return bytes(out)


def _crc32_ieee8023(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF
