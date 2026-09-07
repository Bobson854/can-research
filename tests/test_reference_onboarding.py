"""Tests for reference source registry and normalized bundle onboarding."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.mcp.reference_handlers import (
    handle_inspect_reference_source,
    handle_list_reference_sources,
    handle_lookup_reference_message,
    handle_search_reference_knowledge,
)
from canresearch.references.bundle_common import load_bundle_json
from canresearch.references.bundle_knowledge import import_bundle_file, search_reference_knowledge
from canresearch.references.bundle_validate import (
    acceptance_family_match,
    format_bundle_warnings,
    validate_reference_bundle,
)
from canresearch.references.source_registry import (
    ReferenceSourceNotFoundError,
    get_reference_source,
    register_reference_source,
)
from canresearch.storage.database import initialize

FIXTURES = Path(__file__).parent / "fixtures" / "reference_bundles"


def _register_fixture_source(tmp_path: Path, key: str) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    placeholder = tmp_path / f"{key}.txt"
    placeholder.write_text("synthetic source placeholder", encoding="utf-8")
    register_reference_source(
        key=key,
        path=placeholder,
        display_name=f"Test {key}",
        source_type="oem",
        visibility="private",
        data_dir=data_dir,
    )
    return data_dir


def test_register_source_private_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"%PDF-1.4 synthetic")
    record = register_reference_source(
        key="motor_manual",
        path=source,
        visibility="private",
        source_type="oem",
    )
    assert record.visibility == "private"
    from canresearch.references.source_registry import reference_sources_root

    root = reference_sources_root(data_dir)
    stored = root / record.stored_path
    assert stored.is_file()
    assert stored.read_bytes() == source.read_bytes()


def test_smartec_synthetic_bundle_validates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = _register_fixture_source(tmp_path, "smartec_mownet_synthetic")
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    payload = load_bundle_json(FIXTURES / "smartec_mownet_synthetic.json")
    report = validate_reference_bundle(payload, data_dir=data_dir)
    assert report.valid
    assert not report.errors


def test_db_series_synthetic_bundle_validates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = _register_fixture_source(tmp_path, "db_series_driver_synthetic")
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    payload = load_bundle_json(FIXTURES / "db_series_driver_synthetic.json")
    report = validate_reference_bundle(payload, data_dir=data_dir)
    assert report.valid


def test_message_family_match_db_series_patterns() -> None:
    assert acceptance_family_match(0x18705503, 0x18705500, 0xFFFFFF00)
    assert acceptance_family_match(0x1870A055, 0x18700055, 0xFFFF00FF)
    assert not acceptance_family_match(0x18705503, 0x18700055, 0xFFFF00FF)


def test_invalid_overlap_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _register_fixture_source(tmp_path, "overlap_test")
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    payload = {
        "schema_version": 1,
        "source_key": "overlap_test",
        "messages": [
            {
                "key": "m1",
                "name": "M1",
                "can_id": "0x100",
                "signals": [
                    {"key": "a", "name": "A", "start_bit": 0, "bit_length": 16},
                    {"key": "b", "name": "B", "start_bit": 8, "bit_length": 16},
                ],
            }
        ],
    }
    report = validate_reference_bundle(payload, data_dir=data_dir)
    assert not report.valid
    assert any(issue.category == "signal_overlap" for issue in report.errors)


def test_import_search_and_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _register_fixture_source(tmp_path, "smartec_mownet_synthetic")
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    db_path = data_dir / "references" / "canresearch.db"
    conn = initialize(db_path)
    bundle_path = FIXTURES / "smartec_mownet_synthetic.json"
    report1, _ = import_bundle_file(conn, bundle_path, data_dir=data_dir)
    report2, _ = import_bundle_file(conn, bundle_path, data_dir=data_dir)
    assert report1.messages == report2.messages == 2
    result = search_reference_knowledge(conn, query="TargetRPM", limit=10)
    assert result["total"] >= 1
    conn.close()


def test_mcp_list_and_lookup_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _register_fixture_source(tmp_path, "db_series_driver_synthetic")
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    db_path = data_dir / "references" / "canresearch.db"
    conn = initialize(db_path)
    import_bundle_file(conn, FIXTURES / "db_series_driver_synthetic.json", data_dir=data_dir)
    conn.close()

    monkeypatch.setattr("canresearch.mcp.reference_handlers.default_db_path", lambda: db_path)
    listed = handle_list_reference_sources()
    assert listed["count"] == 1
    assert listed["sources"][0]["key"] == "db_series_driver_synthetic"

    inspected = handle_inspect_reference_source(source_key="db_series_driver_synthetic")
    assert inspected["visibility"] == "private"
    assert inspected["imported_knowledge"]["message_families"] >= 5

    lookup = handle_lookup_reference_message(can_id=0x18705503, is_extended=True)
    assert lookup["match_count"] >= 1

    search = handle_search_reference_knowledge(query="MaxSpeed", limit=5)
    assert search["total"] >= 1


def test_unregistered_source_key_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    payload = load_bundle_json(FIXTURES / "smartec_mownet_synthetic.json")
    report = validate_reference_bundle(payload, data_dir=data_dir)
    assert not report.valid


def test_missing_source_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    with pytest.raises(ReferenceSourceNotFoundError):
        get_reference_source("missing")


def test_sqlite_integer_overflow_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _register_fixture_source(tmp_path, "sqlite_overflow")
    monkeypatch.setattr("canresearch.references.source_registry.resolve_data_dir", lambda: data_dir)
    payload = {
        "schema_version": 1,
        "source_key": "sqlite_overflow",
        "messages": [
            {
                "key": "ws_member",
                "name": "Working Set Member",
                "pgn": 65036,
                "signals": [
                    {
                        "key": "name_of_member",
                        "name": "NAME of Working Set Member",
                        "start_bit": 0,
                        "bit_length": 64,
                        "maximum": 18446744073709551615,
                    }
                ],
            }
        ],
    }
    report = validate_reference_bundle(payload, data_dir=data_dir)
    assert not report.valid
    assert any(issue.category == "sqlite_integer" for issue in report.errors)
    assert "18446744073709551615" in report.errors[0].message


def test_format_bundle_warnings_summarizes_pgn_only_can_id() -> None:
    from canresearch.references.bundle_validate import BundleValidationIssue

    warnings = [
        BundleValidationIssue("warning", "incomplete", "no exact CAN ID on message", f"messages[{i}]")
        for i in range(117)
    ]
    lines = format_bundle_warnings(warnings)
    assert len(lines) == 1
    assert "117 messages have no exact CAN ID" in lines[0]
    assert "PGN-level definitions" in lines[0]
