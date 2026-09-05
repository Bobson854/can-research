"""Tests for J1939 SPN bit extraction."""

from __future__ import annotations

import pytest

from canresearch.core.spn_bits import (
    extract_raw_value,
    j1939_linear_bit_index,
    normalize_byte_order,
)


def test_j1939_linear_bit_index_msb() -> None:
    assert j1939_linear_bit_index(1, 1) == 7
    assert j1939_linear_bit_index(1, 8) == 0


def test_extract_two_bits_within_byte() -> None:
    payload = bytes.fromhex("10 00 00 00 00 00 00 00")
    raw = extract_raw_value(
        payload,
        start_byte=1,
        start_bit=3,
        bit_length=2,
        byte_order="intel",
        signed=False,
    )
    assert raw == 0b10


def test_extract_sixteen_bit_little_endian() -> None:
    payload = bytes.fromhex("00 00 00 40 1f 00 00 00")
    raw = extract_raw_value(
        payload,
        start_byte=4,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
        signed=False,
    )
    assert raw == 8000


def test_extract_signed_negative() -> None:
    payload = bytes.fromhex("00 00 00 00 00 ff ff ff")
    raw = extract_raw_value(
        payload,
        start_byte=7,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
        signed=True,
    )
    assert raw == -1


def test_extract_exceeds_payload_raises() -> None:
    payload = bytes.fromhex("00 00 00 00")
    with pytest.raises(ValueError, match="payload"):
        extract_raw_value(
            payload,
            start_byte=4,
            start_bit=None,
            bit_length=16,
            byte_order="intel",
            signed=False,
        )


def test_normalize_byte_order_defaults() -> None:
    assert normalize_byte_order(None, default_intel=True) == "intel"
    assert normalize_byte_order(None, default_intel=False) is None
    assert normalize_byte_order("Motorola") == "motorola"
