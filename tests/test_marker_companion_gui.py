"""Tests for marker companion GUI startup and window focus."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import tkinter as tk

from canresearch.core.marker_companion import AttachedSession, MarkerCompanionError
from canresearch.core.sessions import SessionStatus
from canresearch.marker_companion.gui import (
    bring_window_to_foreground,
    launch_companion,
    report_startup_failure,
    show_startup_error,
)


def _recording_session(session_id: str = "cap001") -> AttachedSession:
    return AttachedSession(
        session_id=session_id,
        name="Bench run",
        host="bench.local",
        channel=1,
        status=SessionStatus.RECORDING,
    )


def test_bring_window_to_foreground_sequence() -> None:
    window = MagicMock()
    bring_window_to_foreground(window, topmost_ms=75)
    window.deiconify.assert_called_once()
    window.update_idletasks.assert_called_once()
    window.lift.assert_called_once()
    window.focus_force.assert_called_once()
    window.attributes.assert_called_with("-topmost", True)
    after_args = window.after.call_args
    assert after_args is not None
    assert after_args[0][0] == 75


def test_bring_window_to_foreground_ignores_topmost_tcl_error() -> None:
    window = MagicMock()
    window.attributes.side_effect = tk.TclError("unsupported")
    bring_window_to_foreground(window)
    window.deiconify.assert_called_once()
    window.lift.assert_called_once()


def test_show_startup_error_uses_foreground_holder(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_root = MagicMock()
    mock_holder = MagicMock()
    mock_tk = MagicMock(return_value=mock_root)
    mock_toplevel = MagicMock(return_value=mock_holder)

    monkeypatch.setattr("canresearch.marker_companion.gui.tk.Tk", mock_tk)
    monkeypatch.setattr("canresearch.marker_companion.gui.tk.Toplevel", mock_toplevel)
    focus = MagicMock()
    monkeypatch.setattr("canresearch.marker_companion.gui.bring_window_to_foreground", focus)
    msgbox = MagicMock()
    monkeypatch.setattr("canresearch.marker_companion.gui.messagebox.showerror", msgbox)

    show_startup_error("no_active_capture", "Start live capture first.")

    mock_root.withdraw.assert_called_once()
    mock_toplevel.assert_called_once_with(mock_root)
    focus.assert_called_once_with(mock_holder)
    msgbox.assert_called_once()
    assert msgbox.call_args.kwargs["parent"] is mock_holder
    mock_holder.destroy.assert_called_once()
    mock_root.destroy.assert_called_once()


def test_report_startup_failure_prints_and_shows_dialog(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    show = MagicMock()
    monkeypatch.setattr("canresearch.marker_companion.gui.show_startup_error", show)

    rc = report_startup_failure("capture_not_active", "Session is not recording.")

    assert rc == 1
    assert "[FAIL] capture_not_active: Session is not recording." in capsys.readouterr().err
    show.assert_called_once_with("capture_not_active", "Session is not recording.")


def test_launch_companion_success_prints_and_focuses(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attached = _recording_session()
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.resolve_attached_session_for_launch",
        lambda **kwargs: attached,
    )

    mock_root = MagicMock()
    monkeypatch.setattr("canresearch.marker_companion.gui.tk.Tk", lambda: mock_root)
    monkeypatch.setattr("canresearch.marker_companion.gui.MarkerCompanionApp", MagicMock())
    focus = MagicMock()
    monkeypatch.setattr("canresearch.marker_companion.gui.bring_window_to_foreground", focus)

    rc = launch_companion()

    assert rc == 0
    out = capsys.readouterr().out
    assert "Opening marker companion for session cap001..." in out
    assert "Marker companion window is ready." in out
    focus.assert_called_once_with(mock_root)
    mock_root.mainloop.assert_called_once()
    mock_root.withdraw.assert_not_called()


def test_launch_companion_no_active_capture(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MarkerCompanionError("no_active_capture", "No active recording session found.")
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.resolve_attached_session_for_launch",
        lambda **kwargs: error,
    )
    report = MagicMock(return_value=1)
    monkeypatch.setattr("canresearch.marker_companion.gui.report_startup_failure", report)

    rc = launch_companion()

    assert rc == 1
    report.assert_called_once_with("no_active_capture", error.message)


def test_launch_companion_rejects_stopped_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MarkerCompanionError(
        "capture_not_active",
        "Session 'cap001' is not recording (status=completed)",
    )
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.resolve_attached_session_for_launch",
        lambda **kwargs: error,
    )
    report = MagicMock(return_value=1)
    monkeypatch.setattr("canresearch.marker_companion.gui.report_startup_failure", report)

    rc = launch_companion(session_id="cap001")

    assert rc == 1
    report.assert_called_once_with("capture_not_active", error.message)


def test_launch_companion_multiple_cancelled(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MarkerCompanionError(
        "multiple_active_captures",
        "Multiple recording sessions found.",
        sessions=(_recording_session("cap001"), _recording_session("cap002")),
    )
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.resolve_attached_session_for_launch",
        lambda **kwargs: error,
    )
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.pick_session_interactive",
        lambda sessions: None,
    )
    report = MagicMock(return_value=1)
    monkeypatch.setattr("canresearch.marker_companion.gui.report_startup_failure", report)

    rc = launch_companion()

    assert rc == 1
    assert "Multiple active captures" in capsys.readouterr().err
    report.assert_called_once_with("session_selection_cancelled", "No session selected.")


def test_launch_companion_multiple_selection_success(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MarkerCompanionError(
        "multiple_active_captures",
        "Multiple recording sessions found.",
        sessions=(_recording_session("cap001"), _recording_session("cap002")),
    )
    chosen = _recording_session("cap002")
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.resolve_attached_session_for_launch",
        lambda **kwargs: error,
    )
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.pick_session_interactive",
        lambda sessions: chosen,
    )

    mock_root = MagicMock()
    monkeypatch.setattr("canresearch.marker_companion.gui.tk.Tk", lambda: mock_root)
    monkeypatch.setattr("canresearch.marker_companion.gui.MarkerCompanionApp", MagicMock())
    monkeypatch.setattr("canresearch.marker_companion.gui.bring_window_to_foreground", MagicMock())

    rc = launch_companion()

    assert rc == 0
    out = capsys.readouterr().out
    assert "Opening marker companion for session cap002..." in out
    assert "Marker companion window is ready." in out


def test_launch_companion_calls_session_picker_for_multiple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MarkerCompanionError(
        "multiple_active_captures",
        "Multiple recording sessions found.",
        sessions=(_recording_session("cap001"), _recording_session("cap002")),
    )
    monkeypatch.setattr(
        "canresearch.marker_companion.gui.resolve_attached_session_for_launch",
        lambda **kwargs: error,
    )
    picker = MagicMock(return_value=_recording_session("cap002"))
    monkeypatch.setattr("canresearch.marker_companion.gui.pick_session_interactive", picker)
    monkeypatch.setattr("canresearch.marker_companion.gui.tk.Tk", MagicMock())
    monkeypatch.setattr("canresearch.marker_companion.gui.MarkerCompanionApp", MagicMock())
    monkeypatch.setattr("canresearch.marker_companion.gui.bring_window_to_foreground", MagicMock())

    launch_companion()

    picker.assert_called_once_with(error.sessions)
