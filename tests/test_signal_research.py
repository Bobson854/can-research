"""Integration tests for proprietary signal research primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.core.candidate_fields import (
    evaluate_endianness_candidates,
    generate_field_candidates,
)
from canresearch.core.checksum_detection import detect_checksum_candidates
from canresearch.core.counter_detection import detect_counter_candidates
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.research_frames import format_can_id
from canresearch.core.signal_research import (
    analyze_can_id_activity,
    compare_repeated_actions,
    correlate_candidate_field,
    detect_checksums_for_can_id,
    detect_counters_for_can_id,
    rank_candidate_ids,
)
from canresearch.storage.database import initialize
from tests.fixtures.synthetic_proprietary import (
    ACTION_BIT,
    SYNTHETIC_CAN_ID,
    build_payload,
    write_synthetic_session,
)


@pytest.fixture
def synth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"
    session_id = "synth001"

    def _frames_path(sid: str) -> Path:
        return sessions_dir / sid / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    initialize(db_path)
    frames_path = _frames_path(session_id)
    meta = write_synthetic_session(session_id=session_id, db_path=db_path, frames_path=frames_path)
    return {"db_path": db_path, "session_id": session_id, **meta}


def test_rank_action_id_high(synth_env) -> None:
    result = rank_candidate_ids(
        synth_env["session_id"],
        baseline_event="baseline_1",
        action_event="scv2_extend_1",
        db_path=synth_env["db_path"],
    )
    assert result["candidates"]
    top = result["candidates"][0]
    assert top["can_id"] == format_can_id(SYNTHETIC_CAN_ID)
    assert top["change_score"] > 0
    assert top["evidence"]["action_activity"] >= top["evidence"]["baseline_activity"]


def test_analyze_can_id_activity(synth_env) -> None:
    result = analyze_can_id_activity(
        synth_env["session_id"],
        SYNTHETIC_CAN_ID,
        baseline_event="baseline_1",
        action_event="scv2_extend_1",
        db_path=synth_env["db_path"],
    )
    assert result["can_id"] == format_can_id(SYNTHETIC_CAN_ID)
    assert result["action"]["frame_count"] > 0
    byte2 = next(b for b in result["action"]["byte_activity"] if b["byte"] == 2)
    assert byte2["unique_values"] >= 1
    assert len(result["field_candidates"]) > 0


def test_repeated_action_consistency(synth_env) -> None:
    result = compare_repeated_actions(
        synth_env["session_id"],
        baseline_events=synth_env["baseline_events"],
        action_events=synth_env["action_events"],
        can_id=SYNTHETIC_CAN_ID,
        db_path=synth_env["db_path"],
    )
    action_bit = next(
        (row for row in result["bit_consistency"] if row["bit_index"] == ACTION_BIT),
        None,
    )
    assert action_bit is not None
    assert action_bit["consistency"] == 1.0
    assert action_bit["changed_in_action"] == 3
    assert action_bit["changed_in_baseline"] == 0


def test_detect_counter(synth_env) -> None:
    result = detect_counters_for_can_id(
        synth_env["session_id"],
        SYNTHETIC_CAN_ID,
        db_path=synth_env["db_path"],
    )
    byte0 = next(c for c in result["candidates"] if c["byte_index"] == 0 and c["modulus"] == 256)
    assert byte0["is_counter_candidate"] is True
    assert byte0["match_ratio"] >= 0.85


def test_detect_checksum(synth_env) -> None:
    result = detect_checksums_for_can_id(
        synth_env["session_id"],
        SYNTHETIC_CAN_ID,
        db_path=synth_env["db_path"],
    )
    assert any(c["algorithm"] == "xor8" and c["checksum_byte"] == 1 for c in result["candidates"])


def test_correlate_pressure_field(synth_env) -> None:
    result = correlate_candidate_field(
        synth_env["session_id"],
        SYNTHETIC_CAN_ID,
        start_bit=16,
        length=16,
        reference_series=synth_env["reference_series"],
        db_path=synth_env["db_path"],
    )
    assert result["matched_samples"] > 0
    assert result["pearson"] is not None
    assert result["pearson"] > 0.99
    assert result["factor"] is not None
    assert abs(result["factor"] - 0.1) < 0.01


def test_field_candidates_bounded() -> None:
    payloads = [
        build_payload(counter=i, pressure_raw=1000 + i, action_on=False)
        for i in range(50)
    ]
    candidates = generate_field_candidates(
        payloads,
        can_id=format_can_id(SYNTHETIC_CAN_ID),
        limit=10,
    )
    assert len(candidates) <= 10


def test_endianness_returns_both() -> None:
    payloads = [
        build_payload(counter=i, pressure_raw=1000 + i * 10, action_on=False)
        for i in range(20)
    ]
    result = evaluate_endianness_candidates(payloads, start_bit=16, length=16)
    assert result["intel"]["unique_count"] > 1


def test_counter_unit_incrementing() -> None:
    payloads = [bytes([i, 0, 0, 0, 0, 0, 0, 0]) for i in range(30)]
    candidates = detect_counter_candidates(payloads)
    assert any(c.byte_index == 0 and c.match_ratio >= 0.85 for c in candidates)


def test_checksum_random_rejected() -> None:
    payloads = [bytes([i, (i * 3) % 256, 1, 2, 3, 4, 5, 6]) for i in range(20)]
    candidates = detect_checksum_candidates(payloads, min_match_ratio=0.95)
    assert not any(c.match_ratio == 1.0 for c in candidates)


def test_repeat_mismatched_events(synth_env) -> None:
    with pytest.raises(LiveResearchError) as exc:
        compare_repeated_actions(
            synth_env["session_id"],
            baseline_events=["baseline_1"],
            action_events=["scv2_extend_1", "scv2_extend_2"],
            db_path=synth_env["db_path"],
        )
    assert exc.value.code == "invalid_event_pairs"
