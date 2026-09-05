"""Tests for persisted research candidate workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.research_candidates import (
    CandidateClassification,
    CandidateStatus,
    ResearchCandidateError,
    Signedness,
    add_candidate_evidence,
    confirm_candidate,
    create_research_candidate,
    get_research_candidate,
    list_candidate_evidence,
    list_research_candidates,
    mark_candidate_reviewed,
    reject_candidate,
)
from canresearch.core.sessions import create_session
from canresearch.storage.database import initialize


@pytest.fixture
def candidate_env(tmp_path: Path) -> dict[str, Path | str]:
    db_path = tmp_path / "test.db"
    frames_path = tmp_path / "frames.jsonl"
    frames_path.write_text("", encoding="utf-8")
    initialize(db_path)
    session_id = "sess-cand-01"
    asset_key = "weedit_quadro_01"
    create_session(
        session_id=session_id,
        name="candidate-test",
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


def _create_basic_candidate(env: dict[str, Path | str], **kwargs: object):
    defaults = {
        "asset_key": env["asset_key"],
        "session_id": env["session_id"],
        "can_id": 0x18FF748A,
        "start_bit": 16,
        "bit_length": 16,
        "byte_order": "intel",
        "signedness": Signedness.UNSIGNED.value,
        "classification": CandidateClassification.SIGNAL.value,
        "db_path": env["db_path"],
    }
    defaults.update(kwargs)
    return create_research_candidate(**defaults)  # type: ignore[arg-type]


def test_create_requires_asset_and_session(candidate_env: dict[str, Path | str]) -> None:
    with pytest.raises(ValueError, match="not linked"):
        create_research_candidate(
            asset_key=candidate_env["asset_key"],
            session_id="missing-session",
            can_id=0x18FF748A,
            start_bit=16,
            bit_length=16,
            byte_order="intel",
            db_path=candidate_env["db_path"],
        )


def test_create_list_show(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(
        candidate_env,
        suggested_name="Pressure_Test",
        factor=0.1,
        offset=0.0,
        unit="bar",
    )
    assert created.status == CandidateStatus.CANDIDATE.value
    assert created.asset_key == candidate_env["asset_key"]

    rows = list_research_candidates(
        asset_key=candidate_env["asset_key"],
        db_path=candidate_env["db_path"],
    )
    assert len(rows) == 1

    loaded = get_research_candidate(created.id, db_path=candidate_env["db_path"])
    assert loaded.start_bit == 16
    assert loaded.bit_length == 16


def test_status_workflow_happy_path(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(candidate_env)
    reviewed = mark_candidate_reviewed(created.id, db_path=candidate_env["db_path"])
    assert reviewed.to_status == CandidateStatus.REVIEWED.value

    confirmed = confirm_candidate(
        created.id,
        name="Pressure_Test",
        factor=0.1,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        unit="bar",
        db_path=candidate_env["db_path"],
    )
    assert confirmed.candidate.status == CandidateStatus.CONFIRMED.value
    assert confirmed.dbc_signal_name == "Pressure_Test"


def test_invalid_transitions(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(candidate_env)
    with pytest.raises(ResearchCandidateError) as exc:
        confirm_candidate(
            created.id,
            name="Pressure_Test",
            factor=0.1,
            offset=0.0,
            signedness=Signedness.UNSIGNED.value,
            db_path=candidate_env["db_path"],
        )
    assert exc.value.code == "invalid_status_transition"

    mark_candidate_reviewed(created.id, db_path=candidate_env["db_path"])
    confirm_candidate(
        created.id,
        name="Pressure_Test",
        factor=0.1,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=candidate_env["db_path"],
    )
    with pytest.raises(ResearchCandidateError) as exc:
        mark_candidate_reviewed(created.id, db_path=candidate_env["db_path"])
    assert exc.value.code == "invalid_status_transition"


def test_reject_from_candidate_and_reviewed(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(candidate_env)
    reject_candidate(created.id, notes="noise", db_path=candidate_env["db_path"])
    loaded = get_research_candidate(created.id, db_path=candidate_env["db_path"])
    assert loaded.status == CandidateStatus.REJECTED.value

    second = _create_basic_candidate(candidate_env, start_bit=32, bit_length=1)
    mark_candidate_reviewed(second.id, db_path=candidate_env["db_path"])
    reject_candidate(second.id, db_path=candidate_env["db_path"])
    assert (
        get_research_candidate(second.id, db_path=candidate_env["db_path"]).status
        == CandidateStatus.REJECTED.value
    )


def test_confirm_requires_metadata(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(
        candidate_env,
        signedness=Signedness.UNKNOWN.value,
    )
    mark_candidate_reviewed(created.id, db_path=candidate_env["db_path"])
    with pytest.raises(ResearchCandidateError) as exc:
        confirm_candidate(
            created.id,
            name="Pressure_Test",
            factor=0.1,
            offset=0.0,
            db_path=candidate_env["db_path"],
        )
    assert exc.value.code == "candidate_not_ready"


def test_name_sanitization(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(candidate_env)
    mark_candidate_reviewed(created.id, db_path=candidate_env["db_path"])
    result = confirm_candidate(
        created.id,
        name="2Pressure",
        factor=1.0,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=candidate_env["db_path"],
    )
    assert result.name_sanitized is True
    assert result.dbc_signal_name == "CAN2Pressure"


def test_overlap_rejects_confirmed(candidate_env: dict[str, Path | str]) -> None:
    first = _create_basic_candidate(candidate_env, start_bit=16, bit_length=16)
    mark_candidate_reviewed(first.id, db_path=candidate_env["db_path"])
    confirm_candidate(
        first.id,
        name="Pressure_A",
        factor=0.1,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=candidate_env["db_path"],
    )

    second = _create_basic_candidate(candidate_env, start_bit=20, bit_length=8)
    mark_candidate_reviewed(second.id, db_path=candidate_env["db_path"])
    with pytest.raises(ResearchCandidateError) as exc:
        confirm_candidate(
            second.id,
            name="Pressure_B",
            factor=1.0,
            offset=0.0,
            signedness=Signedness.UNSIGNED.value,
            db_path=candidate_env["db_path"],
        )
    assert exc.value.code == "signal_overlap"


def test_adjacent_fields_allowed(candidate_env: dict[str, Path | str]) -> None:
    first = _create_basic_candidate(candidate_env, start_bit=16, bit_length=16)
    mark_candidate_reviewed(first.id, db_path=candidate_env["db_path"])
    confirm_candidate(
        first.id,
        name="Pressure_A",
        factor=0.1,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=candidate_env["db_path"],
    )

    second = _create_basic_candidate(candidate_env, start_bit=32, bit_length=1)
    mark_candidate_reviewed(second.id, db_path=candidate_env["db_path"])
    confirm_candidate(
        second.id,
        name="Action_Flag",
        factor=1.0,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=candidate_env["db_path"],
    )


def test_evidence_append_only(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(candidate_env)
    row = add_candidate_evidence(
        created.id,
        evidence_type="reference_correlation",
        evidence={"pearson_r": 0.998, "factor": 0.1, "offset": 0.0},
        session_id=candidate_env["session_id"],
        db_path=candidate_env["db_path"],
    )
    assert row.evidence_type == "reference_correlation"
    rows = list_candidate_evidence(created.id, db_path=candidate_env["db_path"])
    assert len(rows) == 1

    add_candidate_evidence(
        created.id,
        evidence_type="manual_note",
        evidence={"text": "looks like hydraulic pressure"},
        db_path=candidate_env["db_path"],
    )
    assert len(list_candidate_evidence(created.id, db_path=candidate_env["db_path"])) == 2


def test_confirmed_survives_session_delete(candidate_env: dict[str, Path | str]) -> None:
    created = _create_basic_candidate(candidate_env)
    mark_candidate_reviewed(created.id, db_path=candidate_env["db_path"])
    confirm_candidate(
        created.id,
        name="Pressure_Test",
        factor=0.1,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        db_path=candidate_env["db_path"],
    )

    from canresearch.storage.database import connect

    conn = connect(candidate_env["db_path"])
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (candidate_env["session_id"],))
        conn.commit()
    finally:
        conn.close()

    loaded = get_research_candidate(created.id, db_path=candidate_env["db_path"])
    assert loaded.status == CandidateStatus.CONFIRMED.value
    assert loaded.origin_session_id is None
