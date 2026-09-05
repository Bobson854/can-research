"""Tests for CANsub.2 WebSocket binary protocol parsing."""

from __future__ import annotations

import pytest

from canresearch.cansub.exceptions import CansubFrameError
from canresearch.cansub.ws_protocol import (
    TIMESTAMP_EPOCH_US,
    HdlcFrameParser,
    decode_timestamp_us,
    parse_can_frame,
)

# Official test vectors from CANsub.2 WebSocket API documentation.
TEST_VECTORS = [
    pytest.param(
        bytes.fromhex("7E 1C AE 8C 13 E0 00 01 07 FF 00 98 4F D1 B8 7E"),
        [{"can_id": 0x7FF, "extended": False, "fd": False, "dlc": 1, "data": b"\x00"}],
        id="TV-01-standard",
    ),
    pytest.param(
        bytes.fromhex("7E 39 5D 18 27 C0 00 01 9F FF FF FF 00 82 83 9F 92 7E"),
        [{"can_id": 0x1FFFFFFF, "extended": True, "fd": False, "dlc": 1, "data": b"\x00"}],
        id="TV-02-extended",
    ),
    pytest.param(
        bytes.fromhex("7E 00 00 00 00 00 00 48 00 01 EF 87 F8 40 7E"),
        [{"can_id": 0x001, "extended": False, "fd": False, "rtr": True, "dlc": 8, "data": b""}],
        id="TV-03-rtr",
    ),
    pytest.param(
        bytes.fromhex("7E 00 00 00 00 00 00 81 00 01 00 AF 74 88 69 7E"),
        [{"can_id": 0x001, "extended": False, "fd": True, "dlc": 1, "data": b"\x00"}],
        id="TV-04-fd",
    ),
    pytest.param(
        bytes.fromhex("7E 00 00 00 00 00 00 01 00 01 00 42 2D 3E 52 7E"),
        [{"can_id": 0x001, "extended": False, "fd": False, "dlc": 1, "data": b"\x00"}],
        id="TV-09-basic",
    ),
    pytest.param(
        bytes.fromhex(
            "7E 00 00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 01 00 02 02 "
            "00 00 00 00 00 00 01 00 03 03 00 00 00 00 00 00 01 00 04 04 D1 2C 1F D9 7E"
        ),
        [
            {"can_id": 0x001, "dlc": 1, "data": b"\x01"},
            {"can_id": 0x002, "dlc": 1, "data": b"\x02"},
            {"can_id": 0x003, "dlc": 1, "data": b"\x03"},
            {"can_id": 0x004, "dlc": 1, "data": b"\x04"},
        ],
        id="TV-11-multi-frame",
    ),
    pytest.param(
        bytes.fromhex("7E 00 00 00 00 00 00 11 00 01 00 12 34 69 CD 7E"),
        [{"can_id": 0x001, "extended": False, "tx_ack": True, "dlc": 1, "data": b"\x00"}],
        id="TV-08-tx-ack",
    ),
    pytest.param(
        bytes.fromhex("7E 00 00 00 00 00 00 20 A6 02 FF B6 7E"),
        [{"is_error_frame": True}],
        id="TV-19-error",
    ),
]


@pytest.mark.parametrize(("network", "expected"), TEST_VECTORS)
def test_official_test_vectors(network: bytes, expected: list[dict]) -> None:
    parser = HdlcFrameParser()
    frames = parser.parse_frames(network, channel=1)
    assert len(frames) == len(expected)
    for frame, exp in zip(frames, expected, strict=True):
        if exp.get("is_error_frame"):
            assert frame.is_error_frame
            if "error_type" in exp:
                assert frame.error_type == exp["error_type"]
            continue
        assert frame.can_id == exp["can_id"]
        assert frame.extended == exp.get("extended", False)
        assert frame.fd == exp.get("fd", False)
        assert frame.rtr == exp.get("rtr", False)
        assert frame.tx_ack == exp.get("tx_ack", False)
        assert frame.dlc == exp["dlc"]
        assert frame.data == exp["data"]


def test_invalid_crc_frame_is_skipped() -> None:
    valid = bytes.fromhex("7E 00 00 00 00 00 00 01 00 01 00 42 2D 3E 52 7E")
    invalid = bytes.fromhex(
        "7E 00 00 00 00 00 00 01 00 02 02 00 00 00 00 7E"
    )
    parser = HdlcFrameParser()
    frames = parser.parse_frames(valid + invalid, channel=1)
    assert len(frames) == 1
    assert frames[0].can_id == 0x001


def test_malformed_can_payload_raises() -> None:
    with pytest.raises(CansubFrameError, match="Not enough data"):
        parse_can_frame(bytes.fromhex("00 00 00"), channel=1)


def test_stuffed_data_bytes() -> None:
    network = bytes.fromhex(
        "7E 00 00 00 00 00 00 08 00 01 7D 5E 7D 5E 7D 5E 7D 5E "
        "7D 5D 7D 5D 7D 5D 7D 5D 67 49 97 08 7E"
    )
    parser = HdlcFrameParser()
    frames = parser.parse_frames(network, channel=1)
    assert len(frames) == 1
    assert frames[0].data == bytes.fromhex("7E 7E 7E 7E 7D 7D 7D 7D")


def test_timestamp_zero_is_2025_epoch() -> None:
    assert decode_timestamp_us(bytes(6)) == TIMESTAMP_EPOCH_US
    frame, _ = parse_can_frame(bytes.fromhex("00 00 00 00 00 00 01 00 01 00"), channel=1)
    assert frame.timestamp_us == TIMESTAMP_EPOCH_US


def test_timestamp_tv01_matches_official_vector() -> None:
    network = bytes.fromhex("7E 1C AE 8C 13 E0 00 01 07 FF 00 98 4F D1 B8 7E")
    frames = HdlcFrameParser().parse_frames(network, channel=1)
    assert len(frames) == 1
    rel_us = int.from_bytes(bytes.fromhex("1C AE 8C 13 E0 00"), "big")
    assert frames[0].timestamp_us == TIMESTAMP_EPOCH_US + rel_us


def test_timestamp_big_endian_not_little_endian() -> None:
    header = bytes.fromhex("00 00 00 00 01 00 01 00 01 00")
    frame_be, _ = parse_can_frame(header, channel=1)
    rel_us = int.from_bytes(bytes.fromhex("00 00 00 00 01 00"), "big")
    assert frame_be.timestamp_us == TIMESTAMP_EPOCH_US + rel_us
    wrong_le = int.from_bytes(bytes.fromhex("00 00 00 00 01 00").ljust(8, b"\x00"), "little")
    assert frame_be.timestamp_us != wrong_le


def test_timestamp_ordering_and_delta_preserved() -> None:
    first = bytes.fromhex("00 00 00 00 00 00 01 00 01 00")
    second = bytes.fromhex("00 00 00 0F 42 40 01 00 02 02")
    frame_a, _ = parse_can_frame(first, channel=1)
    frame_b, _ = parse_can_frame(second, channel=1)
    assert frame_a.timestamp_us < frame_b.timestamp_us
    assert frame_b.timestamp_us - frame_a.timestamp_us == 1_000_000


def test_timestamp_decode_requires_six_bytes() -> None:
    with pytest.raises(CansubFrameError, match="timestamp"):
        decode_timestamp_us(bytes(5))
