"""Regression tests for research candidate / DBC identity hardening."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.dbc_position import (
    CLASSIC_CAN_PAYLOAD_BITS,
    validate_classic_payload_field,
)
from canresearch.core.j1939_tp import encode_j1939_can_id
from canresearch.core.research_candidates import (
    ResearchCandidateError,
    Signedness,
    confirm_candidate,
    create_research_candidate,
    list_all_confirmed_research_candidates,
    mark_candidate_reviewed,
)
from canresearch.core.research_dbc import generate_asset_research_dbc
from canresearch.core.sessions import create_session
from canresearch.storage.database import SCHEMA_VERSION, initialize


@pytest.fixture
def hardening_env(tmp_path: Path) -> dict[str, Path | str]:
    db_path = tmp_path / "test.db"
    frames_path = tmp_path / "frames.jsonl"
    frames_path.write_text("", encoding="utf-8")
    initialize(db_path)
    session_id = "hardening-session"
    asset_key = "weedit_quadro_01"
    create_session(
        session_id=session_id,
        name="hardening",
        host="test.local",
        channel=1,
        device_id="test",
        frame_store_path=str(frames_path),
        db_path=db_path,
    )
    add_asset(
        asset_key=asset_key,
        asset_type="implement",
        display_name="Weedit Quadro",
        db_path=db_path,
    )
    link_session_asset(session_id, asset_key, role="implement", db_path=db_path)
    return {"db_path": db_path, "session_id": session_id, "asset_key": asset_key}


def _confirm(
    env: dict[str, Path | str],
    *,
    can_id: int,
    is_extended: bool,
    start_bit: int,
    bit_length: int,
    name: str,
) -> str:
    created = create_research_candidate(
        asset_key=env["asset_key"],
        session_id=env["session_id"],
        can_id=can_id,
        is_extended=is_extended,
        start_bit=start_bit,
        bit_length=bit_length,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        db_path=env["db_path"],
    )
    mark_candidate_reviewed(created.id, db_path=env["db_path"])
    confirm_candidate(
        created.id,
        name=name,
        factor=1.0,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=env["db_path"],
    )
    return created.id


def test_schema_version_is_v10() -> None:
    assert SCHEMA_VERSION == 10


class TestClassicPayloadBounds:
    def test_intel_final_legal_one_bit(self) -> None:
        validate_classic_payload_field(
            start_bit=CLASSIC_CAN_PAYLOAD_BITS - 1,
            bit_length=1,
            byte_order="intel",
        )

    def test_intel_final_legal_multi_bit(self) -> None:
        validate_classic_payload_field(start_bit=48, bit_length=16, byte_order="intel")

    def test_intel_extends_past_payload(self) -> None:
        with pytest.raises(ValueError, match="extends past"):
            validate_classic_payload_field(start_bit=57, bit_length=8, byte_order="intel")

    def test_motorola_legal_whole_bytes(self) -> None:
        validate_classic_payload_field(start_bit=7, bit_length=16, byte_order="motorola")

    def test_motorola_extends_past_payload(self) -> None:
        with pytest.raises(ValueError, match="extends past"):
            validate_classic_payload_field(start_bit=0, bit_length=65, byte_order="motorola")

    def test_create_rejects_out_of_range_intel(self, hardening_env: dict[str, Path | str]) -> None:
        with pytest.raises(ResearchCandidateError) as exc:
            create_research_candidate(
                asset_key=hardening_env["asset_key"],
                session_id=hardening_env["session_id"],
                can_id=0x123,
                is_extended=False,
                start_bit=60,
                bit_length=8,
                byte_order="intel",
                db_path=hardening_env["db_path"],
            )
        assert exc.value.code == "invalid_field_definition"

    def test_create_rejects_invalid_motorola(self, hardening_env: dict[str, Path | str]) -> None:
        with pytest.raises(ResearchCandidateError) as exc:
            create_research_candidate(
                asset_key=hardening_env["asset_key"],
                session_id=hardening_env["session_id"],
                can_id=0x200,
                is_extended=False,
                start_bit=0,
                bit_length=65,
                byte_order="motorola",
                db_path=hardening_env["db_path"],
            )
        assert exc.value.code == "invalid_field_definition"


def test_standard_and_extended_same_numeric_id_do_not_conflict(
    hardening_env: dict[str, Path | str],
) -> None:
    shared_id = 0x123
    _confirm(
        hardening_env,
        can_id=shared_id,
        is_extended=False,
        start_bit=0,
        bit_length=8,
        name="Std_Signal",
    )
    _confirm(
        hardening_env,
        can_id=shared_id,
        is_extended=True,
        start_bit=16,
        bit_length=16,
        name="Ext_Signal",
    )

    summary = generate_asset_research_dbc(
        hardening_env["asset_key"],
        db_path=hardening_env["db_path"],
    )
    assert summary.signals_generated == 2
    assert summary.messages_generated == 2
    frame_ids = {msg.dbc_frame_id for msg in summary.database.messages}
    assert shared_id in frame_ids
    assert (shared_id | 0x80000000) in frame_ids


def test_research_dbc_includes_more_than_200_confirmed(
    hardening_env: dict[str, Path | str],
) -> None:
    total = 210
    for index in range(total):
        can_id = 0x200 + index
        _confirm(
            hardening_env,
            can_id=can_id,
            is_extended=False,
            start_bit=0,
            bit_length=8,
            name=f"Sig_{index:03d}",
        )

    loaded = list_all_confirmed_research_candidates(
        hardening_env["asset_key"],
        db_path=hardening_env["db_path"],
        page_size=50,
    )
    assert len(loaded) == total

    summary = generate_asset_research_dbc(
        hardening_env["asset_key"],
        db_path=hardening_env["db_path"],
    )
    assert summary.confirmed_signal_count == total
    assert summary.signals_generated == total
    assert summary.messages_generated == total


def test_pdu1_message_names_include_destination_address(
    hardening_env: dict[str, Path | str],
) -> None:
    pgn = 0xEF00
    sa = 0x8A
    da_a = 0x03
    da_b = 0x04
    can_a = encode_j1939_can_id(pgn=pgn, source_address=sa, destination_address=da_a)
    can_b = encode_j1939_can_id(pgn=pgn, source_address=sa, destination_address=da_b)

    _confirm(
        hardening_env,
        can_id=can_a,
        is_extended=True,
        start_bit=0,
        bit_length=8,
        name="Field_A",
    )
    _confirm(
        hardening_env,
        can_id=can_b,
        is_extended=True,
        start_bit=0,
        bit_length=8,
        name="Field_B",
    )

    summary = generate_asset_research_dbc(
        hardening_env["asset_key"],
        db_path=hardening_env["db_path"],
    )
    names = {msg.name for msg in summary.database.messages}
    assert "Prop_PGN61184_SA8A_DA03" in names
    assert "Prop_PGN61184_SA8A_DA04" in names
    assert len(names) == 2
