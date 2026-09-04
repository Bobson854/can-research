"""Local PGN/SPN reference catalogue — re-exports from references package."""

from __future__ import annotations

from pathlib import Path

from canresearch.references.service import ReferenceService
from canresearch.storage.database import default_db_path, initialize


def _service(db_path: Path | None = None) -> ReferenceService:
    path = db_path or default_db_path()
    conn = initialize(path)
    return ReferenceService(conn)


def lookup_pgn(pgn: int, db_path: Path | None = None) -> list[dict[str, object]]:
    """Look up a PGN in the local reference catalogue."""
    rows = _service(db_path).lookup_pgn(pgn)
    return [dict(row) for row in rows]


def lookup_spn(spn: int, db_path: Path | None = None) -> list[dict[str, object]]:
    """Look up an SPN in the local reference catalogue."""
    rows = _service(db_path).lookup_spn(spn)
    return [dict(row) for row in rows]
