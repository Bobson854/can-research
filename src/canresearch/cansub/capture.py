"""Live capture from CANsub.2 hardware (stub)."""

from __future__ import annotations

from pathlib import Path

from canresearch.core.sessions import CaptureStore, NullCaptureStore


def start_capture(
    device_id: str,
    session_name: str | None = None,
    store: CaptureStore | None = None,
    output_dir: Path | None = None,
) -> str:
    """Start a live capture; returns session ID."""
    raise NotImplementedError("CANsub.2 capture start is not yet implemented")


def stop_capture() -> None:
    """Stop the active capture session."""
    raise NotImplementedError("CANsub.2 capture stop is not yet implemented")


def default_capture_store() -> CaptureStore:
    """Return the default capture store implementation."""
    return NullCaptureStore()
