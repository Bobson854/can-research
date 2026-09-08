"""Tests for the passive local capture marker companion."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from canresearch.core.marker_companion import (
    LOCAL_COMPANION_ORIGIN,
    MarkerCompanionError,
    local_timestamp_us,
    record_companion_marker,
    resolve_attached_session,
)
from canresearch.core.session_events import add_session_event, list_session_events
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.storage.database import SCHEMA_VERSION, initialize


@pytest.fixture
def marker_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    db_path = tmp_path / "canresearch.db"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(
        "canresearch.storage.database.default_db_path",
        lambda: db_path,
    )
    return {"db_path": db_path, "sessions_dir": sessions_dir}


def _create_recording_session(
    env: dict[str, Path],
    *,
    session_id: str,
    name: str | None = None,
) -> None:
    create_session(
        session_id=session_id,
        name=name,
        host="bench.local",
        channel=1,
        device_id="dev1",
        frame_store_path=str(env["sessions_dir"] / session_id / "frames.jsonl"),
        db_path=env["db_path"],
    )


def test_schema_version_is_v10() -> None:
    assert SCHEMA_VERSION == 10


def test_resolve_attached_session_auto_single(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001", name="Bench run")
    attached = resolve_attached_session(db_path=marker_env["db_path"])
    assert attached.session_id == "cap001"
    assert attached.name == "Bench run"
    assert attached.status == SessionStatus.RECORDING


def test_resolve_attached_session_refuses_zero(marker_env) -> None:
    with pytest.raises(MarkerCompanionError) as exc:
        resolve_attached_session(db_path=marker_env["db_path"])
    assert exc.value.code == "no_active_capture"


def test_resolve_attached_session_refuses_multiple(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")
    _create_recording_session(marker_env, session_id="cap002")
    with pytest.raises(MarkerCompanionError) as exc:
        resolve_attached_session(db_path=marker_env["db_path"])
    assert exc.value.code == "multiple_active_captures"
    assert len(exc.value.sessions) == 2


def test_resolve_attached_session_explicit_id(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")
    _create_recording_session(marker_env, session_id="cap002")
    attached = resolve_attached_session(session_id="cap002", db_path=marker_env["db_path"])
    assert attached.session_id == "cap002"


def test_resolve_attached_session_rejects_non_recording(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")
    finalize_session(
        "cap001",
        status=SessionStatus.COMPLETED,
        frame_count=0,
        db_path=marker_env["db_path"],
    )
    with pytest.raises(MarkerCompanionError) as exc:
        resolve_attached_session(session_id="cap001", db_path=marker_env["db_path"])
    assert exc.value.code == "capture_not_active"


def test_record_companion_marker_sets_origin_and_timestamp(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")
    ts = 1_700_000_000_000_000
    event = record_companion_marker(
        "cap001",
        "baseline",
        notes="operator idle",
        timestamp_us=ts,
        db_path=marker_env["db_path"],
    )
    assert event.label == "baseline"
    assert event.notes == "operator idle"
    assert event.origin == LOCAL_COMPANION_ORIGIN
    assert event.timestamp_us == ts

    listed = list_session_events("cap001", db_path=marker_env["db_path"])
    assert len(listed) == 1
    assert listed[0].origin == LOCAL_COMPANION_ORIGIN


def test_record_companion_marker_custom_label_and_note(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")
    event = record_companion_marker(
        "cap001",
        "operator_step_3",
        notes="panel opened",
        db_path=marker_env["db_path"],
    )
    assert event.label == "operator_step_3"
    assert event.notes == "panel opened"


def test_companion_markers_compatible_with_legacy_mcp_markers(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")
    legacy = add_session_event(
        "cap001",
        "baseline_start",
        notes="via MCP",
        timestamp_us=100,
        db_path=marker_env["db_path"],
    )
    companion = record_companion_marker(
        "cap001",
        "page_opened",
        db_path=marker_env["db_path"],
    )
    events = list_session_events("cap001", db_path=marker_env["db_path"])
    assert len(events) == 2
    assert events[0].label == legacy.label
    assert events[0].origin is None
    assert events[1].label == companion.label
    assert events[1].origin == LOCAL_COMPANION_ORIGIN


def test_concurrent_marker_writes(marker_env) -> None:
    _create_recording_session(marker_env, session_id="cap001")

    def write_marker(index: int) -> None:
        record_companion_marker(
            "cap001",
            f"action_{index}",
            db_path=marker_env["db_path"],
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_marker, range(20)))

    events = list_session_events("cap001", db_path=marker_env["db_path"])
    assert len(events) == 20
    labels = {event.label for event in events}
    assert len(labels) == 20


def test_local_timestamp_us_is_positive_int() -> None:
    ts = local_timestamp_us()
    assert isinstance(ts, int)
    assert ts > 0


def test_session_events_table_has_origin_column(marker_env) -> None:
    conn = initialize(marker_env["db_path"])
    try:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(session_events)").fetchall()
        }
    finally:
        conn.close()
    assert "origin" in columns
