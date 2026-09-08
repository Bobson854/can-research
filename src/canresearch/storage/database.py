"""SQLite persistence for metadata, references, and analysis artefacts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 11

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
    2: """
        CREATE TABLE IF NOT EXISTS reference_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            revision TEXT,
            coverage_date TEXT,
            origin TEXT NOT NULL,
            source_path TEXT,
            source_url TEXT,
            fingerprint TEXT,
            imported_at TEXT NOT NULL DEFAULT (datetime('now')),
            notes TEXT
        );

        ALTER TABLE reference_pgns RENAME TO reference_pgns_legacy_v1;
        ALTER TABLE reference_spns RENAME TO reference_spns_legacy_v1;

        CREATE TABLE reference_pgns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pgn INTEGER NOT NULL,
            name TEXT,
            acronym TEXT,
            description TEXT,
            transmission_rate TEXT,
            payload_length INTEGER,
            default_priority INTEGER,
            data_page INTEGER,
            pdu_format INTEGER,
            pdu_specific INTEGER,
            source_id INTEGER NOT NULL REFERENCES reference_sources(id),
            origin TEXT NOT NULL,
            source_page INTEGER,
            raw_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_id, pgn)
        );

        CREATE TABLE reference_spns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spn INTEGER NOT NULL,
            name TEXT,
            definition TEXT,
            description TEXT,
            data_length_bits INTEGER,
            resolution TEXT,
            offset TEXT,
            minimum TEXT,
            maximum TEXT,
            unit TEXT,
            data_type TEXT,
            status TEXT,
            source_id INTEGER NOT NULL REFERENCES reference_sources(id),
            origin TEXT NOT NULL,
            source_page INTEGER,
            raw_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_id, spn)
        );

        CREATE TABLE reference_pgn_spns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pgn_id INTEGER NOT NULL REFERENCES reference_pgns(id) ON DELETE CASCADE,
            spn_id INTEGER REFERENCES reference_spns(id),
            spn INTEGER NOT NULL,
            position_order INTEGER,
            start_byte INTEGER,
            start_bit INTEGER,
            bit_length INTEGER,
            byte_order TEXT,
            source_id INTEGER NOT NULL REFERENCES reference_sources(id),
            source_page INTEGER,
            raw_position_text TEXT,
            UNIQUE (source_id, pgn_id, spn, raw_position_text)
        );

        CREATE TABLE reference_ddis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ddi INTEGER NOT NULL,
            name TEXT NOT NULL,
            definition TEXT,
            comment TEXT,
            unit_symbol TEXT,
            unit_description TEXT,
            resolution TEXT,
            can_min TEXT,
            can_max TEXT,
            display_min TEXT,
            display_max TEXT,
            sae_spn INTEGER,
            submit_by TEXT,
            submit_date TEXT,
            submit_company TEXT,
            revision_number INTEGER,
            current_status TEXT,
            status_date TEXT,
            status_comments TEXT,
            source_id INTEGER NOT NULL REFERENCES reference_sources(id),
            origin TEXT NOT NULL,
            source_page INTEGER,
            raw_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_id, ddi)
        );

        CREATE TABLE reference_ddi_device_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ddi_id INTEGER NOT NULL REFERENCES reference_ddis(id) ON DELETE CASCADE,
            device_class INTEGER NOT NULL,
            device_class_name TEXT,
            UNIQUE (ddi_id, device_class)
        );

        CREATE TABLE reference_import_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER REFERENCES reference_sources(id),
            severity TEXT NOT NULL,
            category TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_reference_pgns_pgn ON reference_pgns(pgn);
        CREATE INDEX IF NOT EXISTS idx_reference_pgns_source ON reference_pgns(source_id);
        CREATE INDEX IF NOT EXISTS idx_reference_pgns_origin ON reference_pgns(origin);
        CREATE INDEX IF NOT EXISTS idx_reference_spns_spn ON reference_spns(spn);
        CREATE INDEX IF NOT EXISTS idx_reference_spns_source ON reference_spns(source_id);
        CREATE INDEX IF NOT EXISTS idx_reference_spns_origin ON reference_spns(origin);
        CREATE INDEX IF NOT EXISTS idx_reference_pgn_spns_pgn ON reference_pgn_spns(pgn_id);
        CREATE INDEX IF NOT EXISTS idx_reference_pgn_spns_spn ON reference_pgn_spns(spn);
        CREATE INDEX IF NOT EXISTS idx_reference_ddis_ddi ON reference_ddis(ddi);
        CREATE INDEX IF NOT EXISTS idx_reference_ddis_source ON reference_ddis(source_id);
        CREATE INDEX IF NOT EXISTS idx_reference_ddis_origin ON reference_ddis(origin);
        CREATE INDEX IF NOT EXISTS idx_reference_sources_origin ON reference_sources(origin);
    """,
    3: """
        ALTER TABLE sessions ADD COLUMN host TEXT;
        ALTER TABLE sessions ADD COLUMN channel INTEGER;
    """,
    4: """
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            asset_key TEXT NOT NULL UNIQUE,
            asset_type TEXT NOT NULL,
            manufacturer TEXT,
            model TEXT,
            display_name TEXT NOT NULL,
            serial_number TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS session_assets (
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            asset_id TEXT NOT NULL REFERENCES assets(id),
            role TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (session_id, asset_id)
        );

        CREATE INDEX IF NOT EXISTS idx_assets_key ON assets(asset_key);
        CREATE INDEX IF NOT EXISTS idx_session_assets_session ON session_assets(session_id);
        CREATE INDEX IF NOT EXISTS idx_session_assets_asset ON session_assets(asset_id);
    """,
    5: """
        CREATE TABLE IF NOT EXISTS j1939_nodes (
            id TEXT PRIMARY KEY,
            name_value TEXT NOT NULL UNIQUE,
            manufacturer_code INTEGER,
            identity_number INTEGER,
            function INTEGER,
            function_instance INTEGER,
            ecu_instance INTEGER,
            vehicle_system INTEGER,
            vehicle_system_instance INTEGER,
            industry_group INTEGER,
            arbitrary_address_capable INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS j1939_node_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL REFERENCES j1939_nodes(id) ON DELETE CASCADE,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            source_address INTEGER NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            claim_count INTEGER NOT NULL DEFAULT 1,
            cannot_claim INTEGER NOT NULL DEFAULT 0,
            UNIQUE (node_id, session_id, source_address)
        );

        CREATE TABLE IF NOT EXISTS asset_j1939_nodes (
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            node_id TEXT NOT NULL UNIQUE REFERENCES j1939_nodes(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (asset_id, node_id)
        );

        CREATE INDEX IF NOT EXISTS idx_j1939_nodes_name ON j1939_nodes(name_value);
        CREATE INDEX IF NOT EXISTS idx_j1939_node_obs_session
            ON j1939_node_observations(session_id);
        CREATE INDEX IF NOT EXISTS idx_j1939_node_obs_node ON j1939_node_observations(node_id);
        CREATE INDEX IF NOT EXISTS idx_asset_j1939_nodes_asset ON asset_j1939_nodes(asset_id);
    """,
    6: """
        CREATE TABLE IF NOT EXISTS session_events (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            timestamp_us INTEGER NOT NULL,
            label TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);
        CREATE INDEX IF NOT EXISTS idx_session_events_label
            ON session_events(session_id, label);
    """,
    7: """
        CREATE TABLE IF NOT EXISTS research_candidates (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            origin_session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
            can_id INTEGER NOT NULL,
            is_extended INTEGER NOT NULL DEFAULT 1,
            pgn INTEGER,
            source_address INTEGER,
            destination_address INTEGER,
            start_bit INTEGER NOT NULL,
            bit_length INTEGER NOT NULL,
            byte_order TEXT NOT NULL CHECK (byte_order IN ('intel', 'motorola')),
            signedness TEXT NOT NULL CHECK (signedness IN ('signed', 'unsigned', 'unknown')),
            classification TEXT NOT NULL DEFAULT 'unknown'
                CHECK (classification IN ('signal', 'counter', 'checksum', 'reserved', 'unknown')),
            status TEXT NOT NULL DEFAULT 'candidate'
                CHECK (status IN ('candidate', 'reviewed', 'confirmed', 'rejected')),
            suggested_name TEXT,
            signal_name TEXT,
            unit TEXT,
            factor REAL,
            offset REAL,
            minimum REAL,
            maximum REAL,
            notes TEXT,
            confirmed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS research_candidate_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT NOT NULL REFERENCES research_candidates(id) ON DELETE CASCADE,
            evidence_type TEXT NOT NULL CHECK (evidence_type IN (
                'window_comparison',
                'repeat_consistency',
                'counter_detection',
                'checksum_detection',
                'reference_correlation',
                'manual_note'
            )),
            evidence_json TEXT NOT NULL,
            session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS research_candidate_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT NOT NULL REFERENCES research_candidates(id) ON DELETE CASCADE,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_research_candidates_asset
            ON research_candidates(asset_id);
        CREATE INDEX IF NOT EXISTS idx_research_candidates_status
            ON research_candidates(asset_id, status);
        CREATE INDEX IF NOT EXISTS idx_research_candidates_can_id
            ON research_candidates(asset_id, can_id);
        CREATE INDEX IF NOT EXISTS idx_research_candidate_evidence_candidate
            ON research_candidate_evidence(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_research_candidate_status_history
            ON research_candidate_status_history(candidate_id);
    """,
    8: """
        CREATE INDEX IF NOT EXISTS idx_research_candidates_frame
            ON research_candidates(asset_id, is_extended, can_id);
        CREATE INDEX IF NOT EXISTS idx_research_candidates_asset_status
            ON research_candidates(asset_id, status);
    """,
    9: """
        CREATE TABLE IF NOT EXISTS reference_knowledge_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            bundle_schema_version INTEGER NOT NULL,
            generated_by TEXT,
            generated_at TEXT,
            fingerprint TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, fingerprint)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            object_key TEXT NOT NULL,
            name TEXT,
            protocol TEXT,
            can_id INTEGER,
            is_extended INTEGER,
            pgn INTEGER,
            source_address INTEGER,
            destination_address INTEGER,
            dlc INTEGER,
            period_ms INTEGER,
            priority INTEGER,
            description TEXT,
            source_location_json TEXT,
            confidence TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, object_key)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            message_object_key TEXT NOT NULL,
            signal_key TEXT NOT NULL,
            name TEXT,
            start_bit INTEGER,
            bit_length INTEGER,
            byte_order TEXT,
            signedness TEXT,
            factor REAL,
            offset REAL,
            unit TEXT,
            minimum REAL,
            maximum REAL,
            description TEXT,
            enum_key TEXT,
            source_location_json TEXT,
            confidence TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, message_object_key, signal_key)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_message_families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            object_key TEXT NOT NULL,
            name TEXT,
            pattern INTEGER NOT NULL,
            mask INTEGER NOT NULL,
            variable_field TEXT,
            variable_role TEXT,
            description TEXT,
            source_location_json TEXT,
            confidence TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, object_key)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_registers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            object_key TEXT NOT NULL,
            address TEXT,
            name TEXT,
            width INTEGER,
            signedness TEXT,
            factor REAL,
            offset REAL,
            unit TEXT,
            access TEXT,
            minimum REAL,
            maximum REAL,
            default_value TEXT,
            description TEXT,
            enum_key TEXT,
            source_location_json TEXT,
            confidence TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, object_key)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_fault_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            object_key TEXT NOT NULL,
            value TEXT,
            name TEXT,
            description TEXT,
            source_location_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, object_key)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_protocol_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            object_key TEXT NOT NULL,
            category TEXT,
            name TEXT,
            value TEXT,
            unit TEXT,
            description TEXT,
            source_location_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, object_key)
        );

        CREATE TABLE IF NOT EXISTS reference_knowledge_enums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            enum_key TEXT NOT NULL,
            values_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (source_key, enum_key)
        );

        CREATE INDEX IF NOT EXISTS idx_ref_knowledge_messages_can
            ON reference_knowledge_messages(can_id, is_extended);
        CREATE INDEX IF NOT EXISTS idx_ref_knowledge_messages_pgn
            ON reference_knowledge_messages(pgn);
        CREATE INDEX IF NOT EXISTS idx_ref_knowledge_messages_source
            ON reference_knowledge_messages(source_key);
        CREATE INDEX IF NOT EXISTS idx_ref_knowledge_signals_source
            ON reference_knowledge_signals(source_key);
        CREATE INDEX IF NOT EXISTS idx_ref_knowledge_families_source
            ON reference_knowledge_message_families(source_key);
    """,
    10: """
        ALTER TABLE session_events ADD COLUMN origin TEXT;
    """,
    11: """
        ALTER TABLE sessions ADD COLUMN capture_server_id TEXT;
        ALTER TABLE sessions ADD COLUMN capture_heartbeat_at TEXT;
        ALTER TABLE sessions ADD COLUMN interrupted_reason TEXT;
    """,
}


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
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
        if version == 2:
            _migrate_v2(conn)
        elif version == 3:
            _migrate_v3(conn)
        elif version == 4:
            _migrate_v4(conn)
        elif version == 5:
            _migrate_v5(conn)
        elif version == 6:
            _migrate_v6(conn)
        elif version == 7:
            _migrate_v7(conn)
        elif version == 8:
            _migrate_v8(conn)
        elif version == 9:
            _migrate_v9(conn)
        elif version == 10:
            _migrate_v10(conn)
        elif version == 11:
            _migrate_v11(conn)
        else:
            conn.executescript(MIGRATIONS[version])
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Upgrade reference tables to normalized provenance-aware schema."""
    if _table_exists(conn, "reference_sources"):
        return
    conn.executescript(MIGRATIONS[2])


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """Add capture host/channel columns to sessions."""
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "host" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN host TEXT")
    if "channel" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN channel INTEGER")


def _migrate_v4(conn: sqlite3.Connection) -> None:
    """Add asset registry and session-asset associations."""
    if _table_exists(conn, "assets"):
        return
    conn.executescript(MIGRATIONS[4])


def _migrate_v5(conn: sqlite3.Connection) -> None:
    """Add J1939 node identity and asset-node links."""
    if _table_exists(conn, "j1939_nodes"):
        return
    conn.executescript(MIGRATIONS[5])


def _migrate_v6(conn: sqlite3.Connection) -> None:
    """Add session experiment event markers."""
    if _table_exists(conn, "session_events"):
        return
    conn.executescript(MIGRATIONS[6])


def _migrate_v7(conn: sqlite3.Connection) -> None:
    """Add research candidate review workflow tables."""
    if _table_exists(conn, "research_candidates"):
        return
    conn.executescript(MIGRATIONS[7])


def _migrate_v8(conn: sqlite3.Connection) -> None:
    """Add frame-identity index for research candidates."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_research_candidates_frame'"
    ).fetchone()
    if row is not None:
        return
    conn.executescript(MIGRATIONS[8])


def _migrate_v9(conn: sqlite3.Connection) -> None:
    """Add normalized reference bundle knowledge tables."""
    if _table_exists(conn, "reference_knowledge_messages"):
        return
    conn.executescript(MIGRATIONS[9])


def _migrate_v10(conn: sqlite3.Connection) -> None:
    """Add origin metadata to session experiment markers."""
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(session_events)").fetchall()
    }
    if "origin" not in columns:
        conn.execute("ALTER TABLE session_events ADD COLUMN origin TEXT")


def _migrate_v11(conn: sqlite3.Connection) -> None:
    """Add capture liveness metadata to sessions."""
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "capture_server_id" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN capture_server_id TEXT")
    if "capture_heartbeat_at" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN capture_heartbeat_at TEXT")
    if "interrupted_reason" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN interrupted_reason TEXT")


def initialize(db_path: Path) -> sqlite3.Connection:
    """Open database and ensure schema is at current version."""
    conn = connect(db_path)
    migrate(conn)
    return conn


def default_db_path() -> Path:
    """Default location for the local metadata and reference database."""
    from canresearch.config import resolve_data_dir

    return resolve_data_dir() / "references" / "canresearch.db"
