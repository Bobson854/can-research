"""Tests for asset research DBC generation."""

from __future__ import annotations

from pathlib import Path

from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.dbc_position import encode_dbc_extended_id
from canresearch.core.research_candidates import (
    CandidateClassification,
    Signedness,
    confirm_candidate,
    create_research_candidate,
    mark_candidate_reviewed,
    reject_candidate,
)
from canresearch.core.research_dbc import (
    DBC_TYPE_RESEARCH,
    generate_asset_research_dbc,
    write_asset_research_dbc,
)
from canresearch.storage.database import initialize
from tests.fixtures.synthetic_proprietary import (
    PRESSURE_SCALE,
    SYNTHETIC_CAN_ID,
    write_synthetic_session,
)


def _setup_asset_session(tmp_path: Path) -> dict[str, Path | str]:
    db_path = tmp_path / "test.db"
    frames_path = tmp_path / "frames.jsonl"
    initialize(db_path)
    asset_key = "weedit_quadro_01"
    session_id = "synth-session"
    add_asset(
        asset_key=asset_key,
        asset_type="implement",
        display_name="Weedit Quadro",
        db_path=db_path,
    )
    write_synthetic_session(
        session_id=session_id,
        db_path=db_path,
        frames_path=frames_path,
    )
    link_session_asset(session_id, asset_key, role="implement", db_path=db_path)
    return {"db_path": db_path, "session_id": session_id, "asset_key": asset_key}


def _confirm_pressure(env: dict[str, Path | str]) -> str:
    candidate = create_research_candidate(
        asset_key=env["asset_key"],
        session_id=env["session_id"],
        can_id=SYNTHETIC_CAN_ID,
        start_bit=16,
        bit_length=16,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        classification=CandidateClassification.SIGNAL.value,
        suggested_name="Pressure_Test",
        factor=PRESSURE_SCALE,
        offset=0.0,
        unit="bar",
        db_path=env["db_path"],
    )
    mark_candidate_reviewed(candidate.id, db_path=env["db_path"])
    confirm_candidate(
        candidate.id,
        name="Pressure_Test",
        factor=PRESSURE_SCALE,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        unit="bar",
        db_path=env["db_path"],
    )
    return candidate.id


def test_research_dbc_only_includes_confirmed(tmp_path: Path) -> None:
    env = _setup_asset_session(tmp_path)
    _confirm_pressure(env)

    reviewed = create_research_candidate(
        asset_key=env["asset_key"],
        session_id=env["session_id"],
        can_id=SYNTHETIC_CAN_ID,
        start_bit=32,
        bit_length=1,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        db_path=env["db_path"],
    )
    mark_candidate_reviewed(reviewed.id, db_path=env["db_path"])

    rejected = create_research_candidate(
        asset_key=env["asset_key"],
        session_id=env["session_id"],
        can_id=SYNTHETIC_CAN_ID,
        start_bit=0,
        bit_length=8,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        classification=CandidateClassification.COUNTER.value,
        db_path=env["db_path"],
    )
    reject_candidate(rejected.id, db_path=env["db_path"])

    summary = generate_asset_research_dbc(env["asset_key"], db_path=env["db_path"])
    assert summary.dbc_type == DBC_TYPE_RESEARCH
    assert summary.signals_generated == 1
    assert summary.messages_generated == 1
    assert "Pressure_Test" in summary.database.messages[0].signals[0].name


def test_counter_excluded_by_default(tmp_path: Path) -> None:
    env = _setup_asset_session(tmp_path)
    counter = create_research_candidate(
        asset_key=env["asset_key"],
        session_id=env["session_id"],
        can_id=SYNTHETIC_CAN_ID,
        start_bit=0,
        bit_length=8,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        classification=CandidateClassification.COUNTER.value,
        db_path=env["db_path"],
    )
    mark_candidate_reviewed(counter.id, db_path=env["db_path"])
    confirm_candidate(
        counter.id,
        name="Frame_Counter",
        factor=1.0,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        classification=CandidateClassification.COUNTER.value,
        db_path=env["db_path"],
    )

    summary = generate_asset_research_dbc(env["asset_key"], db_path=env["db_path"])
    assert summary.signals_generated == 0

    with_protocol = generate_asset_research_dbc(
        env["asset_key"],
        db_path=env["db_path"],
        include_protocol_fields=True,
    )
    assert with_protocol.signals_generated == 1


def test_extended_id_encoding_and_signal_line(tmp_path: Path) -> None:
    env = _setup_asset_session(tmp_path)
    _confirm_pressure(env)

    summary = generate_asset_research_dbc(env["asset_key"], db_path=env["db_path"])
    message = summary.database.messages[0]
    assert message.dbc_frame_id == encode_dbc_extended_id(SYNTHETIC_CAN_ID)
    signal = message.signals[0]
    assert signal.start_bit == 16
    assert signal.bit_length == 16
    assert signal.byte_order == 1
    assert signal.signed is False
    assert signal.factor == PRESSURE_SCALE
    assert signal.offset == 0.0
    assert signal.unit == "bar"


def test_deterministic_output(tmp_path: Path) -> None:
    env = _setup_asset_session(tmp_path)
    _confirm_pressure(env)

    first = generate_asset_research_dbc(env["asset_key"], db_path=env["db_path"])
    second = generate_asset_research_dbc(env["asset_key"], db_path=env["db_path"])
    from canresearch.core.dbc_writer import render_dbc

    assert render_dbc(first.database) == render_dbc(second.database)


def test_synthetic_workflow_end_to_end(tmp_path: Path) -> None:
    env = _setup_asset_session(tmp_path)
    _confirm_pressure(env)

    output = tmp_path / "weedit_quadro_01_research.dbc"
    summary = write_asset_research_dbc(env["asset_key"], output=output, db_path=env["db_path"])
    text = output.read_text(encoding="ascii")
    assert summary.output_path == output
    assert "Pressure_Test" in text
    assert "16|16@1+" in text
    assert "(0.1,0)" in text
    assert '"bar"' in text
    assert "DBC type: research" in text
    assert f"BO_ {encode_dbc_extended_id(SYNTHETIC_CAN_ID)}" in text


def test_multiple_sessions_same_asset(tmp_path: Path) -> None:
    env = _setup_asset_session(tmp_path)
    _confirm_pressure(env)

    session2 = "synth-session-2"
    frames2 = tmp_path / "frames2.jsonl"
    write_synthetic_session(session_id=session2, db_path=env["db_path"], frames_path=frames2)
    link_session_asset(session2, env["asset_key"], role="implement", db_path=env["db_path"])

    action = create_research_candidate(
        asset_key=env["asset_key"],
        session_id=session2,
        can_id=SYNTHETIC_CAN_ID,
        start_bit=32,
        bit_length=1,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        db_path=env["db_path"],
    )
    mark_candidate_reviewed(action.id, db_path=env["db_path"])
    confirm_candidate(
        action.id,
        name="Action_Flag",
        factor=1.0,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=env["db_path"],
    )

    summary = generate_asset_research_dbc(env["asset_key"], db_path=env["db_path"])
    assert summary.signals_generated == 2
    assert summary.messages_generated == 1
