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
    asset_key: str,
    db_path: Path | None = None,
    pgn_filter: int | None = None,
    source_addresses: tuple[int, ...] | None = None,
) -> SessionDbcSummary:
    """Build and write an asset-specific reference-backed DBC from a capture session."""
    summary = generate_session_dbc(
        session_id,
        asset_key=asset_key,
        db_path=db_path,
        pgn_filter=pgn_filter,
        source_addresses=source_addresses,
    )
    write_dbc(summary.database, output)
    return summary
