"""Local PGN/SPN reference catalogue (stub)."""

from __future__ import annotations

from pathlib import Path


def import_reference_dbc(path: Path) -> None:
    """Parse a user-provided DBC and populate reference PGN/SPN tables."""
    raise NotImplementedError("Reference import is not yet implemented")


def lookup_pgn(pgn: int) -> dict[str, object] | None:
    """Look up a PGN in the local reference catalogue."""
    return None


def lookup_spn(spn: int) -> dict[str, object] | None:
    """Look up an SPN in the local reference catalogue."""
    return None
