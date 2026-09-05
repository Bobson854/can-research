"""J1939 SPN raw bit extraction from CAN payload bytes."""

from __future__ import annotations

J1939_INTEL = "intel"
J1939_MOTOROLA = "motorola"

_BYTE_ORDERS = {
    "intel": J1939_INTEL,
    "little": J1939_INTEL,
    "little-endian": J1939_INTEL,
    "motorola": J1939_MOTOROLA,
    "big": J1939_MOTOROLA,
    "big-endian": J1939_MOTOROLA,
}


def normalize_byte_order(value: str | None, *, default_intel: bool = False) -> str | None:
    if value is None or not value.strip():
        return J1939_INTEL if default_intel else None
    return _BYTE_ORDERS.get(value.strip().lower())


def j1939_linear_bit_index(start_byte: int, start_bit: int) -> int:
    """Map J1939 byte/bit notation to a 0-based linear bit index (LSB-first)."""
    if start_byte < 1:
        msg = f"start_byte must be >= 1, got {start_byte}"
        raise ValueError(msg)
    if start_bit < 1 or start_bit > 8:
        msg = f"start_bit must be 1-8, got {start_bit}"
        raise ValueError(msg)
    return (start_byte - 1) * 8 + (8 - start_bit)


def extract_raw_value(
    payload: bytes,
    *,
    start_byte: int,
    start_bit: int | None,
    bit_length: int,
    byte_order: str,
    signed: bool,
) -> int:
    """Extract a raw integer from payload using J1939 bit/byte conventions."""
    if bit_length <= 0:
        msg = f"bit_length must be positive, got {bit_length}"
        raise ValueError(msg)
    if start_byte < 1:
        msg = f"start_byte must be >= 1, got {start_byte}"
        raise ValueError(msg)

    if start_bit is None:
        return _extract_whole_bytes(
            payload,
            start_byte=start_byte,
            bit_length=bit_length,
            byte_order=byte_order,
            signed=signed,
        )

    return _extract_j1939_bits(
        payload,
        start_byte=start_byte,
        start_bit=start_bit,
        bit_length=bit_length,
        signed=signed,
    )


def _extract_whole_bytes(
    payload: bytes,
    *,
    start_byte: int,
    bit_length: int,
    byte_order: str,
    signed: bool,
) -> int:
    if bit_length % 8 != 0:
        msg = "whole-byte extraction requires bit_length divisible by 8"
        raise ValueError(msg)

    start_idx = start_byte - 1
    num_bytes = bit_length // 8
    end_idx = start_idx + num_bytes
    if end_idx > len(payload):
        msg = f"signal extends past payload ({end_idx} > {len(payload)})"
        raise ValueError(msg)

    chunk = payload[start_idx:end_idx]
    endian = "little" if byte_order == J1939_INTEL else "big"
    value = int.from_bytes(chunk, endian)
    if signed and bit_length > 0 and value >= (1 << (bit_length - 1)):
        value -= 1 << bit_length
    return value


def _extract_j1939_bits(
    payload: bytes,
    *,
    start_byte: int,
    start_bit: int,
    bit_length: int,
    signed: bool,
) -> int:
    value = 0
    for index in range(bit_length):
        offset = start_bit + index - 1
        actual_byte = start_byte + offset // 8
        bit_in_byte = (offset % 8) + 1
        linear = j1939_linear_bit_index(actual_byte, bit_in_byte)
        byte_idx = linear // 8
        bit_in_payload_byte = linear % 8
        if byte_idx >= len(payload):
            msg = f"signal extends past payload ({byte_idx + 1} > {len(payload)})"
            raise ValueError(msg)
        bit = (payload[byte_idx] >> bit_in_payload_byte) & 1
        value |= bit << index

    if signed and bit_length > 0 and value >= (1 << (bit_length - 1)):
        value -= 1 << bit_length
    return value
