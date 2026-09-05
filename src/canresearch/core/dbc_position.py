"""Convert J1939 catalogue positions to DBC start-bit notation."""

from __future__ import annotations

from canresearch.core.spn_bits import J1939_INTEL, J1939_MOTOROLA, j1939_linear_bit_index


def j1939_lsb_linear_index(
    start_byte: int,
    start_bit: int | None,
    bit_length: int,
) -> int:
    """Return the payload linear bit index of the signal LSB (Intel convention)."""
    if start_bit is None:
        return (start_byte - 1) * 8
    last_rel = (start_bit - 1) + (bit_length - 1)
    actual_byte = start_byte + last_rel // 8
    bit_in_byte = (last_rel % 8) + 1
    return j1939_linear_bit_index(actual_byte, bit_in_byte)


def j1939_msb_linear_index(
    start_byte: int,
    start_bit: int | None,
) -> int:
    """Return the payload linear bit index of the signal MSB."""
    if start_bit is None:
        return j1939_linear_bit_index(start_byte, 1)
    return j1939_linear_bit_index(start_byte, start_bit)


def j1939_position_to_dbc_start_bit(
    *,
    start_byte: int,
    start_bit: int | None,
    bit_length: int,
    byte_order: str,
) -> int | None:
    """Convert a catalogue mapping position to a DBC SG_ start bit.

    Intel/little-endian (@1): DBC start bit is the signal LSB.
    Motorola/big-endian (@0): DBC start bit is the signal MSB; only byte-aligned
    mappings without sub-byte start bits are supported.
    """
    if byte_order == J1939_INTEL:
        return j1939_lsb_linear_index(start_byte, start_bit, bit_length)

    if byte_order == J1939_MOTOROLA:
        if start_bit is not None:
            return None
        if bit_length % 8 != 0:
            return None
        return j1939_msb_linear_index(start_byte, start_bit)

    return None


def signal_bit_range(start_bit: int, bit_length: int) -> tuple[int, int]:
    """Inclusive-exclusive bit range [start, end) in DBC Intel linear space."""
    return start_bit, start_bit + bit_length


def decode_intel_dbc_signal(
    payload: bytes,
    *,
    start_bit: int,
    bit_length: int,
    signed: bool,
) -> int:
    """Decode a @1+ DBC signal from payload (matches cantools Intel layout)."""
    total_bits = len(payload) * 8
    if start_bit + bit_length > total_bits:
        msg = f"signal extends past payload ({start_bit + bit_length} > {total_bits})"
        raise ValueError(msg)

    value = 0
    for index in range(bit_length):
        absolute = start_bit + index
        byte_idx = absolute // 8
        bit_in_byte = absolute % 8
        bit = (payload[byte_idx] >> bit_in_byte) & 1
        value |= bit << index

    if signed and bit_length > 0 and value >= (1 << (bit_length - 1)):
        value -= 1 << bit_length
    return value


def encode_dbc_extended_id(can_id: int) -> int:
    """Encode a 29-bit CAN ID for Vector-style DBC BO_ lines."""
    return can_id | 0x80000000
