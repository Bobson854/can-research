"""Persistent asset metadata and session associations."""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from canresearch.storage.database import default_db_path, initialize

ASSET_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")


class AssetType(StrEnum):
    TRACTOR = "tractor"
    IMPLEMENT = "implement"
    CONTROLLER = "controller"
    OTHER = "other"


class SessionAssetRole(StrEnum):
    TRACTOR = "tractor"
    IMPLEMENT = "implement"
    CONTROLLER = "controller"
    OTHER = "other"


VALID_ASSET_TYPES = frozenset(AssetType)
VALID_SESSION_ROLES = frozenset(SessionAssetRole)


@dataclass(frozen=True, slots=True)
class AssetRecord:
    id: str
    asset_key: str
    asset_type: str
    display_name: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SessionAssetRecord:
    session_id: str
    asset_id: str
    asset_key: str
    display_name: str
    asset_type: str
    role: str
    created_at: datetime


def validate_asset_key(asset_key: str) -> str:
    """Normalize and validate a stable asset key."""
    key = asset_key.strip()
    if not key:
        msg = "asset_key is required"
        raise ValueError(msg)
    if key != key.lower():
        msg = f"asset_key must be lowercase: {asset_key!r}"
        raise ValueError(msg)
    if not ASSET_KEY_PATTERN.match(key):
        msg = (
            "asset_key must contain only lowercase letters, digits, and underscores: "
            f"{asset_key!r}"
        )
        raise ValueError(msg)
    return key


def validate_asset_type(asset_type: str) -> str:
    value = asset_type.strip().lower()
    if value not in VALID_ASSET_TYPES:
        allowed = ", ".join(sorted(VALID_ASSET_TYPES))
        msg = f"Invalid asset type {asset_type!r}; expected one of: {allowed}"
        raise ValueError(msg)
    return value


def validate_session_role(role: str) -> str:
    value = role.strip().lower()
    if value not in VALID_SESSION_ROLES:
        allowed = ", ".join(sorted(VALID_SESSION_ROLES))
        msg = f"Invalid session asset role {role!r}; expected one of: {allowed}"
        raise ValueError(msg)
    return value


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    return datetime.fromisoformat(value)


def _row_to_asset(row: sqlite3.Row) -> AssetRecord:
    return AssetRecord(
        id=row["id"],
        asset_key=row["asset_key"],
        asset_type=row["asset_type"],
        display_name=row["display_name"],
        manufacturer=row["manufacturer"],
        model=row["model"],
        serial_number=row["serial_number"],
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def _row_to_session_asset(row: sqlite3.Row) -> SessionAssetRecord:
    return SessionAssetRecord(
        session_id=row["session_id"],
        asset_id=row["asset_id"],
        asset_key=row["asset_key"],
        display_name=row["display_name"],
        asset_type=row["asset_type"],
        role=row["role"],
        created_at=_parse_datetime(row["created_at"]),
    )


def add_asset(
    *,
    asset_key: str,
    asset_type: str,
    display_name: str,
    manufacturer: str | None = None,
    model: str | None = None,
    serial_number: str | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> AssetRecord:
    """Create a new asset in the registry."""
    key = validate_asset_key(asset_key)
    kind = validate_asset_type(asset_type)
    name = display_name.strip()
    if not name:
        msg = "display_name is required"
        raise ValueError(msg)

    asset_id = uuid.uuid4().hex[:12]
    now = datetime.now(tz=UTC).isoformat()
    conn = initialize(db_path or default_db_path())
    try:
        try:
            conn.execute(
                """
                INSERT INTO assets (
                    id, asset_key, asset_type, display_name, manufacturer, model,
                    serial_number, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    key,
                    kind,
                    name,
                    manufacturer,
                    model,
                    serial_number,
                    notes,
                    now,
                    now,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            msg = f"Asset key already exists: {key}"
            raise ValueError(msg) from exc
        row = conn.execute("SELECT * FROM assets WHERE asset_key = ?", (key,)).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Failed to create asset {key}"
        raise RuntimeError(msg)
    return _row_to_asset(row)


def get_asset_by_key(asset_key: str, *, db_path: Path | None = None) -> AssetRecord:
    key = validate_asset_key(asset_key)
    conn = initialize(db_path or default_db_path())
    try:
        row = conn.execute("SELECT * FROM assets WHERE asset_key = ?", (key,)).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Asset not found: {key}"
        raise KeyError(msg)
    return _row_to_asset(row)


def list_assets(*, db_path: Path | None = None, limit: int = 100) -> list[AssetRecord]:
    conn = initialize(db_path or default_db_path())
    try:
        rows = conn.execute(
            """
            SELECT * FROM assets
            ORDER BY asset_key ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_asset(row) for row in rows]


def link_session_asset(
    session_id: str,
    asset_key: str,
    *,
    role: str,
    db_path: Path | None = None,
) -> SessionAssetRecord:
    """Associate an asset with a capture session."""
    session_role = validate_session_role(role)
    asset = get_asset_by_key(asset_key, db_path=db_path)
    conn = initialize(db_path or default_db_path())
    try:
        session_row = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session_row is None:
            msg = f"Session not found: {session_id}"
            raise KeyError(msg)
        try:
            conn.execute(
                """
                INSERT INTO session_assets (session_id, asset_id, role)
                VALUES (?, ?, ?)
                """,
                (session_id, asset.id, session_role),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            msg = (
                f"Asset {asset.asset_key!r} is already linked to session {session_id!r}"
            )
            raise ValueError(msg) from exc
        row = conn.execute(
            """
            SELECT sa.session_id, sa.asset_id, sa.role, sa.created_at,
                   a.asset_key, a.display_name, a.asset_type
            FROM session_assets sa
            JOIN assets a ON a.id = sa.asset_id
            WHERE sa.session_id = ? AND sa.asset_id = ?
            """,
            (session_id, asset.id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Failed to link asset {asset_key} to session {session_id}"
        raise RuntimeError(msg)
    return _row_to_session_asset(row)


def list_session_assets(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> list[SessionAssetRecord]:
    conn = initialize(db_path or default_db_path())
    try:
        session_row = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session_row is None:
            msg = f"Session not found: {session_id}"
            raise KeyError(msg)
        rows = conn.execute(
            """
            SELECT sa.session_id, sa.asset_id, sa.role, sa.created_at,
                   a.asset_key, a.display_name, a.asset_type
            FROM session_assets sa
            JOIN assets a ON a.id = sa.asset_id
            WHERE sa.session_id = ?
            ORDER BY sa.role ASC, a.asset_key ASC
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_session_asset(row) for row in rows]


def unlink_session_asset(
    session_id: str,
    asset_key: str,
    *,
    db_path: Path | None = None,
) -> None:
    asset = get_asset_by_key(asset_key, db_path=db_path)
    conn = initialize(db_path or default_db_path())
    try:
        cursor = conn.execute(
            """
            DELETE FROM session_assets
            WHERE session_id = ? AND asset_id = ?
            """,
            (session_id, asset.id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            msg = (
                f"Asset {asset.asset_key!r} is not linked to session {session_id!r}"
            )
            raise KeyError(msg)
    finally:
        conn.close()


def require_session_asset_link(
    session_id: str,
    asset_key: str,
    *,
    db_path: Path | None = None,
) -> AssetRecord:
    """Return asset metadata when it is linked to the session."""
    asset = get_asset_by_key(asset_key, db_path=db_path)
    conn = initialize(db_path or default_db_path())
    try:
        row = conn.execute(
            """
            SELECT 1 FROM session_assets
            WHERE session_id = ? AND asset_id = ?
            """,
            (session_id, asset.id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = (
            f"Asset {asset.asset_key!r} is not linked to session {session_id!r}; "
            "use `canresearch session asset add` first"
        )
        raise ValueError(msg)
    return asset


def default_dbc_filename(asset_key: str, dbc_type: str = "standard") -> str:
    """Return the default DBC filename for an asset."""
    key = validate_asset_key(asset_key)
    return f"{key}_{dbc_type}.dbc"
