"""J1939 29-bit CAN identifier parsing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class J1939Identifier:
    """Parsed fields from a J1939 29-bit extended CAN identifier."""

    raw_id: int
    priority: int
    data_page: int
    pdu_format: int
    pdu_specific: int
    source_address: int
    pgn: int
    destination_address: int | None

    @property
    def is_pdu1(self) -> bool:
        return self.pdu_format < 240


def parse_j1939_id(can_id: int) -> J1939Identifier:
    """Parse a 29-bit J1939 extended CAN identifier into its constituent fields.

    Bit layout (MSB → LSB):
      28-26 priority, 25 reserved, 24 data page, 23-16 PF, 15-8 PS, 7-0 SA.

    For PDU1 (PF < 240), PS is the destination address and PGN excludes PS.
    For PDU2 (PF >= 240), PS is part of the PGN and there is no DA in the ID.
    """
    if can_id < 0 or can_id > 0x1FFFFFFF:
        msg = f"CAN ID must be a 29-bit value (0–0x1FFFFFFF), got 0x{can_id:X}"
        raise ValueError(msg)

    priority = (can_id >> 26) & 0x7
    data_page = (can_id >> 24) & 0x1
    pdu_format = (can_id >> 16) & 0xFF
    pdu_specific = (can_id >> 8) & 0xFF
    source_address = can_id & 0xFF

    if pdu_format < 240:
        destination_address = pdu_specific
        pgn = (data_page << 16) | (pdu_format << 8)
    else:
        destination_address = None
        pgn = (data_page << 16) | (pdu_format << 8) | pdu_specific

    return J1939Identifier(
        raw_id=can_id,
        priority=priority,
        data_page=data_page,
        pdu_format=pdu_format,
        pdu_specific=pdu_specific,
        source_address=source_address,
        pgn=pgn,
        destination_address=destination_address,
    )
