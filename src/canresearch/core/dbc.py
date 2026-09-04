"""DBC import and export (stub)."""

from __future__ import annotations

from pathlib import Path


def import_dbc(path: Path) -> None:
    """Import message/signal definitions from a DBC file into local reference storage."""
    raise NotImplementedError("DBC import is not yet implemented")


def build_machine_dbc(session_id: str, machine: str, output: Path) -> None:
    """Build a machine-specific DBC from session observations."""
    raise NotImplementedError("DBC build is not yet implemented")
