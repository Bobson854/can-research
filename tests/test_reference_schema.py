"""Reference schema migration tests."""

import sqlite3
from pathlib import Path

import pytest

from canresearch.storage.database import SCHEMA_VERSION, get_schema_version, initialize


def test_schema_version_is_v10() -> None:
    assert SCHEMA_VERSION == 10


def test_v2_tables_created(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = initialize(db_path)
    assert get_schema_version(conn) == SCHEMA_VERSION

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "schema_version",
        "reference_sources",
        "reference_pgns",
        "reference_spns",
        "reference_pgn_spns",
        "reference_ddis",
        "reference_ddi_device_classes",
        "reference_import_warnings",
        "machines",
        "sessions",
        "observed_pgns",
        "findings",
        "dbc_revisions",
        "session_events",
        "research_candidates",
        "research_candidate_evidence",
        "research_candidate_status_history",
    }
    assert expected <= tables
    conn.close()


def test_unique_source_key(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = initialize(db_path)
    conn.execute(
        """
        INSERT INTO reference_sources (source_key, source_type, title, origin)
        VALUES ('test-source', 'test', 'Test', 'j1939_base_2001')
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO reference_sources (source_key, source_type, title, origin)
            VALUES ('test-source', 'test', 'Duplicate', 'j1939_base_2001')
            """
        )
    conn.close()


def test_migrate_from_v1(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = initialize(db_path)
    conn.execute(
        """
        INSERT INTO reference_sources (source_key, source_type, title, origin)
        VALUES ('legacy', 'test', 'Legacy', 'j1939_base_2001')
        """
    )
    source_id = conn.execute("SELECT id FROM reference_sources").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgns (pgn, name, source_id, origin)
        VALUES (65000, 'Test', ?, 'j1939_base_2001')
        """,
        (source_id,),
    )
    conn.commit()
    conn.close()

    conn2 = initialize(db_path)
    assert get_schema_version(conn2) == SCHEMA_VERSION
    row = conn2.execute("SELECT pgn, name FROM reference_pgns WHERE pgn = 65000").fetchone()
    assert row is not None
    conn2.close()
