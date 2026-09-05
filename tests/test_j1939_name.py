"""Tests for J1939 NAME parsing."""

from __future__ import annotations

import pytest

from canresearch.core.j1939_name import (
    build_j1939_name_payload,
    parse_j1939_name_payload,
    parse_j1939_name_text,
    parse_j1939_name_value,
)


def test_parse_known_raw_value_fields() -> None:
    raw = 0x8000000000000000 | (2 << 60) | (2 << 49) | (130 << 40) | (123 << 21) | 456789
    name = parse_j1939_name_value(raw)
    assert name.raw_value == raw
    assert name.identity_number == 456789
    assert name.manufacturer_code == 123
    assert name.ecu_instance == 0
    assert name.function_instance == 0
    assert name.function == 130
    assert name.reserved == 0
    assert name.vehicle_system == 2
    assert name.vehicle_system_instance == 0
    assert name.industry_group == 2
    assert name.arbitrary_address_capable is True


def test_little_endian_payload_assembly() -> None:
    raw = 0xAABBCCDDEEFF0011
    payload = raw.to_bytes(8, byteorder="little")
    assert payload == bytes([0x11, 0x00, 0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])
    name = parse_j1939_name_payload(payload)
    assert name.raw_value == raw


def test_build_payload_roundtrip() -> None:
    payload = build_j1939_name_payload(
        identity_number=0x1FFFFF,
        manufacturer_code=0x7FF,
        ecu_instance=0x7,
        function_instance=0x1F,
        function=0xFF,
        vehicle_system=0x7F,
        vehicle_system_instance=0x0F,
        industry_group=0x7,
        arbitrary_address_capable=False,
        reserved=1,
    )
    name = parse_j1939_name_payload(payload)
    assert name.identity_number == 0x1FFFFF
    assert name.manufacturer_code == 0x7FF
    assert name.ecu_instance == 0x7
    assert name.function_instance == 0x1F
    assert name.function == 0xFF
    assert name.reserved == 1
    assert name.vehicle_system == 0x7F
    assert name.vehicle_system_instance == 0x0F
    assert name.industry_group == 0x7
    assert name.arbitrary_address_capable is False


def test_name_hex_preserves_leading_zeros() -> None:
    name = parse_j1939_name_value(0x11)
    assert name.name_hex == "0x0000000000000011"


def test_parse_name_text_variants() -> None:
    from_build = parse_j1939_name_payload(
        build_j1939_name_payload(identity_number=1, manufacturer_code=275, function=0)
    )
    assert parse_j1939_name_text(from_build.name_hex).raw_value == from_build.raw_value
    assert parse_j1939_name_text(from_build.name_hex[2:]).raw_value == from_build.raw_value


def test_arbitrary_address_capable_bit() -> None:
    capable = parse_j1939_name_payload(
        build_j1939_name_payload(
            identity_number=1,
            manufacturer_code=1,
            arbitrary_address_capable=True,
        )
    )
    not_capable = parse_j1939_name_payload(
        build_j1939_name_payload(
            identity_number=1,
            manufacturer_code=1,
            arbitrary_address_capable=False,
        )
    )
    assert capable.arbitrary_address_capable is True
    assert not_capable.arbitrary_address_capable is False
    assert capable.raw_value != not_capable.raw_value


def test_format_summary() -> None:
    name = parse_j1939_name_text("0x1122334455667788")
    lines = name.format_summary()
    assert lines[0] == "NAME: 0x1122334455667788"
    assert any(line.startswith("Manufacturer code:") for line in lines)


def test_payload_too_short() -> None:
    with pytest.raises(ValueError, match="at least 8 bytes"):
        parse_j1939_name_payload(b"\x00" * 7)


def test_name_text_too_long() -> None:
    with pytest.raises(ValueError, match="too long"):
        parse_j1939_name_text("0x" + "1" * 17)
