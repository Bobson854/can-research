# MCP tool metadata contract (ToolAnnotations)

ChatGPT and other MCP clients use **`tools/list` annotations** to classify tools (read vs
write, destructive, open-world, idempotent). When annotations are missing (`null`), clients
may conservatively treat passive read tools as high-risk writes.

CAN Research exports **explicit `ToolAnnotations`** on every public MCP tool. Annotations
describe intent only — they **do not** replace:

- application validation and limits in handlers;
- CLI-only human approval boundaries (e.g. research candidate confirm/reject);
- ChatGPT connector permission / safety UI;
- passive-only CAN policy (no CAN TX tools are registered).

Implementation: `src/canresearch/mcp/tool_annotations.py` + `_ToolBinding.semantic` in
`src/canresearch/mcp/server.py`. Tests: `tests/test_mcp_tool_annotations.py`.

## Classification policy

| Class | Tools | Annotations |
|-------|-------|-------------|
| **Read / analysis** | Offline session/reference/DBC tools, signal research evidence tools, passive CANsub inspection (`get_cansub_*`, `observe_live_traffic`, `compare_experiment_windows`, …) | `readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`, `idempotentHint=true` |
| **Write orchestration** | `start_live_capture`, `stop_live_capture`, `mark_experiment_event` | `readOnlyHint=false`, `destructiveHint=false`, `openWorldHint=false`, `idempotentHint=false` |

### Read vs write

- **Read** — No durable mutation of CAN Research session/event/capture state via MCP
  (previews and in-memory analysis only). Passive live observation that does not change
  CANsub PHY or transmit CAN frames is **read**, even when talking to hardware.
- **Write orchestration** — Creates/stops local capture sessions or appends experiment
  markers. Still **not** CAN bus transmission.

### Destructive

No public MCP tool is classified **`destructiveHint=true`**. Stopping capture finalizes a
session but is not treated as irreversible data destruction for MCP metadata purposes.

### Open world

All current tools target the **bounded local** CAN Research backend (SQLite/JSONL, configured
CANsub.2). **`openWorldHint=false`** for the public surface.

### Idempotence

Read tools are **`idempotentHint=true`** (safe retries at the MCP metadata layer).

Write orchestration tools are **`idempotentHint=false`** because retries can return
`capture_already_active`, `capture_not_active`, or append duplicate markers.

## Intentional absences

- No CAN TX / injection / probing tools over MCP.
- No MCP access to candidate confirmation, DBC file writes, or reference import mutations.

## Post-change verification (operators / maintainers)

After changing the MCP tool registry or annotations:

1. Run annotation tests: `uv run python -m pytest tests/test_mcp_tool_annotations.py`
2. Run MCP tests: `uv run python -m pytest tests/test_mcp*.py`
3. Inspect live export (optional):

   ```powershell
   uv run canresearch mcp tools
   uv run python scripts/mcp_verify_http.py
   ```

4. **Restart** the CAN Research MCP process (`start-can-research.cmd` or equivalent).
5. Confirm tunnel health if used: `.\status.cmd` (recreate tunnel/connector only when
   actually broken — not required for every restart).
6. In ChatGPT (or admin): **Refresh tools** on the connector (schema refresh — distinct
   from restarting the tunnel).
7. Smoke-test one **read** tool (`get_instance_info`) and one **write** tool
   (`mark_experiment_event` on an active capture, or start/stop capture in a test session).

Tool counts in documentation are **checkpoints** — verify with `uv run canresearch mcp tools`.

## Related docs

- [MCP_SETUP.md](MCP_SETUP.md) — serve, tunnel, normal restart
- [AI_INTEGRATION.md](AI_INTEGRATION.md) — connecting clients
