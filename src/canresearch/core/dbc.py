"""DBC import and session-backed export."""

from __future__ import annotations

from pathlib import Path

from canresearch.core.dbc_generation import SessionDbcSummary, generate_session_dbc
from canresearch.core.dbc_writer import write_dbc


def import_dbc(path: Path) -> None:
    """Import message/signal definitions from a DBC file into local reference storage."""
    raise NotImplementedError("DBC import is not yet implemented")


def build_session_dbc(
    session_id: str,
    output: Path,
    *,
    db_path: Path | None = None,
    pgn_filter: int | None = None,
) -> SessionDbcSummary:
    """Build and write a reference-backed machine DBC from a capture session."""
    summary = generate_session_dbc(session_id, db_path=db_path, pgn_filter=pgn_filter)
    write_dbc(summary.database, output)
    return summary
