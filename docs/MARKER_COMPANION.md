# Capture marker companion

Windows-local **passive annotation** during an active live capture. Records precise
experiment markers on the capture host without ChatGPT, tunnel, or MCP round-trips.

**This does not transmit CAN frames**, alter CANsub configuration, or change MCP capture
semantics. It only appends rows to the existing `session_events` table.

---

## When to use

Use the companion when an operator performs physical UI actions that should align with
captured traffic — for example:

- screen/page opened
- tree node selected
- save pressed
- save completed
- deliberate action window

Start **live capture first**, then open the companion.

---

## Launch

From the repository root (after `setup.cmd`):

```cmd
marker-companion.cmd
```

Or:

```powershell
uv run canresearch session marker-companion
uv run python scripts/marker_companion.py
```

On successful attach the terminal prints:

```text
Opening marker companion for session <id>...
Marker companion window is ready.
```

Startup failures print `[FAIL] <code>: <message>` and show a foreground error dialog.

When multiple captures are recording, pass an explicit session:

```powershell
uv run canresearch session marker-companion --session-id <session-id>
```

---

## Attachment rules

| Active captures | Behaviour |
|-----------------|-----------|
| **Exactly one** | Attaches automatically |
| **Zero** | Error — start live capture first |
| **Multiple** | Selection dialog (GUI) or pass `--session-id` |

The window shows session ID, name, channel, and **recording** state. It polls every 2s
and warns if the session is no longer recording.

---

## Standard markers

| Button / key | Label |
|--------------|-------|
| F1 | `baseline` |
| F2 | `page_opened` |
| F3 | `node_selected` |
| F4 | `save_pressed` |
| F5 | `save_complete` |
| F6 | `action` |

Custom label and optional note fields are also available (Enter to record).

Keyboard shortcuts apply when the companion window is focused (not global system hooks).

---

## Windows manual acceptance

After starting live capture, run `marker-companion.cmd` from the repository root.

**Expected (single active capture):**

1. Terminal prints `Opening marker companion for session <id>...` then `Marker companion window is ready.`
2. **CAN Research — Capture Markers** appears on the desktop within a few seconds, in the foreground and ready for F1–F6 / button clicks.
3. The terminal remains blocked while the GUI is open (normal — close the window to return to the prompt).
4. Pressing a marker button updates the status line and writes to `session_events`.

**Expected (no active capture):**

1. Terminal prints `[FAIL] no_active_capture: ...` with a non-zero exit code.
2. A foreground error dialog shows the same reason.

**Expected (multiple active captures):**

1. Terminal prints `Multiple active captures — select one in the dialog.`
2. A foreground **Select active capture** window appears; choose **Attach** or **Cancel**.
3. Cancel prints `[FAIL] session_selection_cancelled: ...` and exits non-zero.

If the window does not appear, confirm a capture is **recording** (`uv run canresearch session list`) and that no other full-screen app is blocking new windows.

---

## Storage and compatibility

Markers are written through the same `session_events` layer as MCP `mark_experiment_event`
and CLI `session event add`. Companion markers set:

```text
origin = local_companion
```

Legacy MCP/CLI markers keep `origin = null`. All markers share the same schema and appear
in `list_session_events` / `compare_experiment_windows`.

Timestamps use **local capture-host wall time** (UTC microseconds) at button/key press.

SQLite uses WAL mode for safe concurrent writes while the capture process records frames.

---

## Verify

```powershell
uv run canresearch session event list <session-id>
```

Look for `[local_companion]` in CLI output, or `origin` in MCP `list_session_events`.

---

## Related

- [CANSUB_SETUP.md](CANSUB_SETUP.md) — live capture
- [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) — experiment workflow
- [MCP_SETUP.md](MCP_SETUP.md) — MCP live tools (`mark_experiment_event`)
