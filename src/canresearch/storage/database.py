"""SQLite persistence for metadata, references, and analysis artefacts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

MIGRATIONS: dict[int, str] = {
    1: """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reference_pgns (
            pgn INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            pdu_format INTEGER,
            default_priority INTEGER,
            source TEXT,
            imported_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reference_spns (
            spn INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            unit TEXT,
            source TEXT,
            imported_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS machines (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            make TEXT,
            model TEXT,
            year INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            device_id TEXT,
            machine_id TEXT REFERENCES machines(id),
            started_at TEXT NOT NULL,
            stopped_at TEXT,
            status TEXT NOT NULL DEFAULT 'recording',
            frame_store_path TEXT,
            frame_count INTEGER,
            notes TEXT,
            FOREIGN KEY (machine_id) REFERENCES machines(id)
        );

        CREATE TABLE IF NOT EXISTS observed_pgns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            pgn INTEGER NOT NULL,
            can_id INTEGER,
            source_address INTEGER,
            destination_address INTEGER,
            frame_count INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT,
            last_seen_at TEXT,
            UNIQUE (session_id, pgn, source_address, destination_address)
        );

        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            finding_type TEXT NOT NULL,
            pgn INTEGER,
            spn INTEGER,
            summary TEXT NOT NULL,
            details_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS dbc_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT REFERENCES machines(id),
            session_id TEXT REFERENCES sessions(id),
            revision INTEGER NOT NULL DEFAULT 1,
            file_path TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_observed_pgns_session ON observed_pgns(session_id);
        CREATE INDEX IF NOT EXISTS idx_findings_session ON findings(session_id);
        CREATE INDEX IF NOT EXISTS idx_dbc_revisions_machine ON dbc_revisions(machine_id);
    """,
}


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int | None:
    """Return current schema version, or None if uninitialized."""
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return None
    return int(row["version"]) if row else None


def migrate(conn: sqlite3.Connection, target_version: int = SCHEMA_VERSION) -> None:
    """Apply pending migrations up to target_version."""
    current = get_schema_version(conn)
    if current is None:
        current = 0

    for version in range(current + 1, target_version + 1):
        if version not in MIGRATIONS:
            msg = f"No migration defined for schema version {version}"
            raise RuntimeError(msg)
        conn.executescript(MIGRATIONS[version])
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()


def initialize(db_path: Path) -> sqlite3.Connection:
    """Open database and ensure schema is at current version."""
    conn = connect(db_path)
    migrate(conn)
    return conn


def default_db_path() -> Path:
    """Default location for the local metadata database."""
    return Path("data") / "canresearch.sqlite"
