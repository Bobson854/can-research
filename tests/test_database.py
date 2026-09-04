"""SQLite database initialization tests."""

from pathlib import Path

from canresearch.storage.database import SCHEMA_VERSION, get_schema_version, initialize


def test_database_initializes(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = initialize(db_path)

    assert db_path.exists()
    assert get_schema_version(conn) == SCHEMA_VERSION

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    }
    expected = {
        "schema_version",
        "reference_pgns",
        "reference_spns",
        "machines",
        "sessions",
        "observed_pgns",
        "findings",
        "dbc_revisions",
    }
    assert expected <= tables

    conn.close()


def test_migrate_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn1 = initialize(db_path)
    conn1.close()

    conn2 = initialize(db_path)
    assert get_schema_version(conn2) == SCHEMA_VERSION
    conn2.close()
