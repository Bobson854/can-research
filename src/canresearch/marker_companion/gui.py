"""Passive capture marker companion GUI."""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from canresearch.core.marker_companion import (
    STANDARD_MARKER_LABELS,
    AttachedSession,
    MarkerCompanionError,
    record_companion_marker,
    resolve_attached_session,
    session_event_to_dict,
)
from canresearch.core.session_events import SessionEvent

FOCUS_TOPMOST_MS = 200


def _format_session_line(session: AttachedSession) -> str:
    name = session.name or "(unnamed)"
    channel = session.channel if session.channel is not None else "?"
    return f"{session.session_id} — {name} — ch{channel} — {session.status.value}"


def bring_window_to_foreground(
    window: tk.Misc,
    *,
    topmost_ms: int = FOCUS_TOPMOST_MS,
) -> None:
    """Raise a Tk window on the active desktop (Windows-safe focus sequence)."""
    window.deiconify()
    window.update_idletasks()
    window.lift()
    window.focus_force()
    try:
        window.attributes("-topmost", True)
        window.after(topmost_ms, lambda: _clear_topmost(window))
    except tk.TclError:
        pass


def _clear_topmost(window: tk.Misc) -> None:
    try:
        window.attributes("-topmost", False)
    except tk.TclError:
        pass


def _raise_hidden_owner_for_modal(root: tk.Tk, *, topmost_ms: int = FOCUS_TOPMOST_MS) -> None:
    """Prepare a withdrawn Tk root as a modal parent without showing an empty window."""
    root.withdraw()
    try:
        root.overrideredirect(True)
    except tk.TclError:
        pass
    try:
        root.geometry("1x1+0+0")
    except tk.TclError:
        pass
    root.update_idletasks()
    root.lift()
    root.focus_force()
    try:
        root.attributes("-topmost", True)
        root.after(topmost_ms, lambda: _clear_topmost(root))
    except tk.TclError:
        pass


def show_startup_error(code: str, message: str) -> None:
    """Show a foreground error dialog for startup failures."""
    root = tk.Tk()
    try:
        _raise_hidden_owner_for_modal(root)
        messagebox.showerror(
            "Capture marker companion",
            f"{code}\n\n{message}",
            parent=root,
        )
    finally:
        _clear_topmost(root)
        try:
            root.destroy()
        except tk.TclError:
            pass


def report_startup_failure(code: str, message: str) -> int:
    """Print a startup failure and show a foreground error dialog."""
    print(f"[FAIL] {code}: {message}", file=sys.stderr)
    show_startup_error(code, message)
    return 1


class MarkerCompanionApp:
    """Thin Tkinter shell over the marker companion service."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        session_id: str,
        db_path: Path | None = None,
        on_record: Callable[..., SessionEvent] | None = None,
    ) -> None:
        self.root = root
        self.session_id = session_id
        self.db_path = db_path
        self._record = on_record or record_companion_marker
        self._status_var = tk.StringVar(value="Ready")
        self._session_var = tk.StringVar()
        self._custom_label = tk.StringVar()
        self._custom_note = tk.StringVar()
        self._build()
        self._refresh_session_state()
        self.root.after(2000, self._poll_session_state)

    def _build(self) -> None:
        self.root.title("CAN Research — Capture Markers")
        self.root.geometry("520x420")
        self.root.minsize(480, 380)

        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Attached session:", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W,
        )
        ttk.Label(header, textvariable=self._session_var, wraplength=480).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Passive annotation only — no CAN transmission.",
            foreground="#555555",
        ).pack(anchor=tk.W, pady=(6, 0))

        buttons = ttk.LabelFrame(self.root, text="Standard markers", padding=10)
        buttons.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))

        shortcuts = {
            "baseline": "F1",
            "page_opened": "F2",
            "node_selected": "F3",
            "save_pressed": "F4",
            "save_complete": "F5",
            "action": "F6",
        }
        for row, label in enumerate(STANDARD_MARKER_LABELS):
            key = shortcuts[label]
            ttk.Button(
                buttons,
                text=f"{label} ({key})",
                command=lambda lbl=label: self._mark(lbl),
            ).grid(row=row // 2, column=row % 2, sticky=tk.EW, padx=4, pady=4)
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

        custom = ttk.LabelFrame(self.root, text="Custom marker", padding=10)
        custom.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Label(custom, text="Label").grid(row=0, column=0, sticky=tk.W)
        label_entry = ttk.Entry(custom, textvariable=self._custom_label, width=40)
        label_entry.grid(row=0, column=1, sticky=tk.EW, padx=(8, 0))
        ttk.Label(custom, text="Note (optional)").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        note_entry = ttk.Entry(custom, textvariable=self._custom_note, width=40)
        note_entry.grid(row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=(6, 0))
        ttk.Button(custom, text="Record custom (Enter)", command=self._mark_custom).grid(
            row=2,
            column=1,
            sticky=tk.E,
            pady=(8, 0),
        )
        custom.columnconfigure(1, weight=1)
        label_entry.bind("<Return>", lambda _event: self._mark_custom())
        note_entry.bind("<Return>", lambda _event: self._mark_custom())

        status = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        status.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status, textvariable=self._status_var, wraplength=480).pack(anchor=tk.W)

        for index, _label in enumerate(STANDARD_MARKER_LABELS, start=1):
            self.root.bind(
                f"<F{index}>",
                lambda _event, lbl=STANDARD_MARKER_LABELS[index - 1]: self._mark(lbl),
            )

    def _refresh_session_state(self) -> None:
        try:
            session = resolve_attached_session(
                session_id=self.session_id,
                db_path=self.db_path,
            )
        except MarkerCompanionError as exc:
            self._session_var.set(f"{exc.code}: {exc.message}")
            self._status_var.set("Session no longer recording — close and restart companion.")
            return
        self._session_var.set(_format_session_line(session))

    def _poll_session_state(self) -> None:
        self._refresh_session_state()
        self.root.after(2000, self._poll_session_state)

    def _mark(self, label: str) -> None:
        try:
            event = self._record(self.session_id, label, db_path=self.db_path)
        except MarkerCompanionError as exc:
            messagebox.showerror("Marker failed", f"{exc.code}: {exc.message}")
            self._status_var.set(f"Failed: {exc.message}")
            return
        except ValueError as exc:
            messagebox.showerror("Marker failed", str(exc))
            self._status_var.set(f"Failed: {exc}")
            return
        payload = session_event_to_dict(event)
        self._status_var.set(
            f"Recorded {payload['label']} at {payload['timestamp']} (id={payload['id']})",
        )

    def _mark_custom(self) -> None:
        label = self._custom_label.get().strip()
        if not label:
            messagebox.showwarning("Custom marker", "Enter a label first.")
            return
        note = self._custom_note.get().strip() or None
        try:
            event = self._record(
                self.session_id,
                label,
                notes=note,
                db_path=self.db_path,
            )
        except MarkerCompanionError as exc:
            messagebox.showerror("Marker failed", f"{exc.code}: {exc.message}")
            self._status_var.set(f"Failed: {exc.message}")
            return
        except ValueError as exc:
            messagebox.showerror("Marker failed", str(exc))
            self._status_var.set(f"Failed: {exc}")
            return
        payload = session_event_to_dict(event)
        self._status_var.set(
            f"Recorded {payload['label']} at {payload['timestamp']} (id={payload['id']})",
        )
        self._custom_label.set("")
        self._custom_note.set("")


def pick_session_interactive(sessions: tuple[AttachedSession, ...]) -> AttachedSession | None:
    """Show a foreground session picker when multiple captures are active."""
    root = tk.Tk()
    root.title("Select active capture")
    root.geometry("640x320")
    root.minsize(520, 260)
    selected: dict[str, AttachedSession | None] = {"value": None}

    ttk.Label(
        root,
        text="Multiple recording sessions are active. Select one:",
        padding=10,
    ).pack(anchor=tk.W)

    listbox = tk.Listbox(root, width=70, height=min(len(sessions), 8))
    for item in sessions:
        listbox.insert(tk.END, _format_session_line(item))
    listbox.selection_set(0)
    listbox.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

    def accept() -> None:
        index = listbox.curselection()
        if not index:
            messagebox.showwarning("Select session", "Choose a session.", parent=root)
            return
        selected["value"] = sessions[index[0]]
        root.quit()

    def cancel() -> None:
        selected["value"] = None
        root.quit()

    actions = ttk.Frame(root, padding=(10, 0, 10, 10))
    actions.pack(fill=tk.X)
    ttk.Button(actions, text="Attach", command=accept).pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(actions, text="Cancel", command=cancel).pack(side=tk.RIGHT)
    root.protocol("WM_DELETE_WINDOW", cancel)
    bring_window_to_foreground(root)
    root.mainloop()
    root.destroy()
    return selected["value"]


def resolve_attached_session_for_launch(
    *,
    session_id: str | None = None,
    db_path: Path | None = None,
) -> AttachedSession | MarkerCompanionError:
    """Resolve attachment or return a structured startup error."""
    try:
        return resolve_attached_session(session_id=session_id, db_path=db_path)
    except MarkerCompanionError as exc:
        return exc


def launch_companion(
    *,
    session_id: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Resolve session attachment and open the marker companion window."""
    attached = resolve_attached_session_for_launch(session_id=session_id, db_path=db_path)
    if isinstance(attached, MarkerCompanionError):
        if attached.code == "multiple_active_captures":
            print(
                "Multiple active captures — select one in the dialog.",
                file=sys.stderr,
            )
            chosen = pick_session_interactive(attached.sessions)
            if chosen is None:
                return report_startup_failure(
                    "session_selection_cancelled",
                    "No session selected.",
                )
            attached = chosen
        else:
            return report_startup_failure(attached.code, attached.message)

    print(f"Opening marker companion for session {attached.session_id}...")
    root = tk.Tk()
    MarkerCompanionApp(root, session_id=attached.session_id, db_path=db_path)
    bring_window_to_foreground(root)
    print("Marker companion window is ready.")
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Passive local capture marker companion (annotation only).",
    )
    parser.add_argument(
        "--session-id",
        help="Attach to a specific recording session (required when multiple are active).",
    )
    args = parser.parse_args(argv)
    return launch_companion(session_id=args.session_id)


if __name__ == "__main__":
    sys.exit(main())
