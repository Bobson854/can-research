"""Tests for DBC writer output."""

from __future__ import annotations

from canresearch.core.dbc_model import DbcDatabase, DbcMessage, DbcSignal
from canresearch.core.dbc_position import encode_dbc_extended_id
from canresearch.core.dbc_writer import render_dbc


def test_render_minimal_message() -> None:
    database = DbcDatabase(
        version="",
        nodes=("Vector__XXX",),
        messages=(
            DbcMessage(
                name="EEC1_SA00",
                can_id=0x0CF00400,
                dbc_frame_id=0x8CF00400,
                dlc=8,
                transmitter="Vector__XXX",
                pgn=61444,
                source_address=0,
                destination_address=None,
                origin="j1939_base_2001",
                signals=(
                    DbcSignal(
                        name="EngineSpeed",
                        start_bit=24,
                        bit_length=16,
                        byte_order=1,
                        signed=False,
                        factor=0.125,
                        offset=0,
                        minimum=0,
                        maximum=8031.875,
                        unit="rpm",
                        pgn=61444,
                        spn=190,
                        origin="j1939_base_2001",
                    ),
                ),
            ),
        ),
    )
    text = render_dbc(database)
    frame_id = encode_dbc_extended_id(0x0CF00400)
    assert f"BO_ {frame_id} EEC1_SA00: 8 Vector__XXX" in text
    assert ' SG_ EngineSpeed : 24|16@1+ (0.125,0)' in text
    assert '"rpm"' in text
