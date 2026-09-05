"""Tests for J1939 to DBC position conversion."""

from __future__ import annotations

from canresearch.core.dbc_position import (
    decode_intel_dbc_signal,
    encode_dbc_extended_id,
    j1939_position_to_dbc_start_bit,
)
from canresearch.core.spn_bits import extract_raw_value


def test_eec1_sixteen_bit_intel_start_bit() -> None:
    start = j1939_position_to_dbc_start_bit(
        start_byte=4,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
    )
    assert start == 24


def test_sub_byte_two_bit_signal() -> None:
    start = j1939_position_to_dbc_start_bit(
        start_byte=1,
        start_bit=3,
        bit_length=2,
        byte_order="intel",
    )
    assert start == 4


def test_decode_equivalence_eec1_engine_speed() -> None:
    payload = bytes.fromhex("00 00 00 40 1f 00 00 00")
    j1939_raw = extract_raw_value(
        payload,
        start_byte=4,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
        signed=False,
    )
    dbc_start = j1939_position_to_dbc_start_bit(
        start_byte=4,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
    )
    dbc_raw = decode_intel_dbc_signal(
        payload,
        start_bit=dbc_start,
        bit_length=16,
        signed=False,
    )
    assert j1939_raw == 8000
    assert dbc_raw == j1939_raw


def test_extended_id_encoding() -> None:
    assert encode_dbc_extended_id(0x0CF00400) == 0x8CF00400
