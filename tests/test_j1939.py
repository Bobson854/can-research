"""J1939 identifier parsing tests."""

import pytest

from canresearch.core.j1939 import parse_j1939_id


def test_pdu1_destination_and_pgn() -> None:
    # PF=0xEA (234), PS=0xFF (dest), SA=0x21, priority=6, data_page=0
    # CAN ID: priority=6, DP=0, PF=0xEA, PS=0xFF, SA=0x21
    can_id = 0x18EAFF21
    parsed = parse_j1939_id(can_id)

    assert parsed.priority == 6
    assert parsed.data_page == 0
    assert parsed.pdu_format == 0xEA
    assert parsed.pdu_specific == 0xFF
    assert parsed.source_address == 0x21
    assert parsed.pgn == 0xEA00
    assert parsed.destination_address == 0xFF
    assert parsed.is_pdu1 is True


def test_pdu2_no_destination_in_id() -> None:
    # PF=0xFEF1 (65265 PDU2), PS=0x00, SA=0x00, priority=3
    can_id = 0x0CFEF100
    parsed = parse_j1939_id(can_id)

    assert parsed.priority == 3
    assert parsed.data_page == 0
    assert parsed.pdu_format == 0xFE
    assert parsed.pdu_specific == 0xF1
    assert parsed.source_address == 0x00
    assert parsed.pgn == 0xFEF1
    assert parsed.destination_address is None
    assert parsed.is_pdu1 is False


def test_data_page_affects_pgn() -> None:
    # data_page=1, PF=0x00, PS=0xFF (PDU1 dest), SA=0x01
    can_id = 0x1900FF01
    parsed = parse_j1939_id(can_id)

    assert parsed.data_page == 1
    assert parsed.pgn == 0x10000
    assert parsed.destination_address == 0xFF


def test_invalid_can_id_raises() -> None:
    with pytest.raises(ValueError, match="29-bit"):
        parse_j1939_id(0x20000000)
