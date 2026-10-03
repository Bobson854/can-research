# CAN Research MCP connection

> **Deployment record — not canonical installation instructions.**
>
> This document records a previously validated **Office** installation and may contain
> instance-specific paths, device IDs, ports, or **historical tool counts** (e.g. 32 tools
> at verification time). For current setup, see [MCP_SETUP.md](MCP_SETUP.md) and verify
> with `uv run canresearch mcp tools` (baseline **41 tools**; SQLite schema **v11** on current builds).

Per-instance operational guide for exposing a local CAN Research MCP server to ChatGPT
via an OpenAI tunnel.

**Office deployment verified end-to-end:** initial install **2026-09-05**; Windows
reboot recovery **2026-09-06** (MCP + tunnel restart only — connector and Skill persisted).

See also:

- [MCP_SETUP.md](MCP_SETUP.md) — **public** normal startup after reboot and one-time install
- [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md) — Office verified deployment record
- [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) — workshop/travel model

## Three independent states

These must **all** agree before tools work in ChatGPT:

1. **Local MCP service** — healthy, current tool registry, initialize OK, correct `get_instance_info` (verified at **32 tools** on 2026-09-05; current baseline **41**)
2. **OpenAI tunnel** — healthy, targets `http://127.0.0.1:8765/mcp` on the same host
3. **ChatGPT app/plugin** — published schema discovered/refreshed and enabled in the chat/workspace

## Verified Office deployment record

Shared infrastructure (unchanged across baseline updates):

| Field | Value |
|---|---|
| `instance_key` | `office` |
| `display_name` | `CAN Research - Office` |
| Local MCP port | `8765` |
| Local MCP URL | `http://127.0.0.1:8765/mcp` |
| MCP transport | `streamable-http` |
| Tunnel name | `can-research-office` |
| Tunnel-client profile | `can-research-office` |
| Tunnel client version | `0.0.14` |
| Tunnel health listener | `127.0.0.1:8081` |
| ChatGPT connector/plugin | `can-research-office` / CAN Research - Office |

### Historical tool baseline (2026-09-05 / 2026-09-06)

| Field | Value |
|---|---|
| MCP tool count | **32** |
| Read-only bindings | 19 |
| Live (passive CANsub) | 7 |
| Signal research | 6 |
| Fresh-chat verification | **Passed 2026-09-05** |
| Reboot recovery | **Passed 2026-09-06** — MCP + tunnel restart only; connector + Skill persisted |
| DB schema at reboot check | **v8** (historical) |

### Current tool baseline (verified **2026-10-03**)

After MCP server restart and ChatGPT connector **Refresh tools**:

| Field | Value |
|---|---|
| MCP public tools | **41** |
| Read-only bindings | **28** |
| Live (passive CANsub) | **7** |
| Signal research | **6** |
| ToolAnnotations | **38** read (`readOnlyHint=true`) · **3** write orchestration (`start_live_capture`, `stop_live_capture`, `mark_experiment_event`) |
| CAN TX over MCP | **false** |

**Live capture stop semantics (2026-10-03):** CH1 passive capture started via MCP;
**18 frames** in ~2.23 s; deliberate `stop_live_capture` returned **`completed`**
(session `ad61fe672155` — bench record). An immediate second start reached preflight only and
failed with **`timing_proof_failed`** (no frames during passive proof window) — expected when
the bus is quiet; **not** evidence of channel-release failure after the first stop.

Prior runtime bug (pre-fix): clean operator/API stop incorrectly surfaced **`interrupted`**;
corrected in application code — re-verify after deploy with `stop_live_capture` → `completed`.

Port `8081` is used for the OpenAI tunnel health/admin listener because SABnzbd
already owns `127.0.0.1:8080` on the Office workstation.

Confirm backend identity after connect with MCP tool `get_instance_info()`.

## Per-instance deployment template

| Field | Example (workshop) | Example (travel) |
|---|---|---|
| `instance_key` | `workshop` | `travel` |
| `display_name` | `CAN Research - Workshop` | `CAN Research - Travel` |
| Local MCP port | `8765` | `8765` |
| Local MCP URL | `http://127.0.0.1:8765/mcp` | `http://127.0.0.1:8765/mcp` |
| Tunnel profile | `can-research-workshop` | `can-research-travel` |
| ChatGPT connector name | `CAN Research - Workshop` | `CAN Research - Travel` |
| Last successful verification | _date_ | _date_ |

## Expected tool inventory (current)

```text
Total: 41
Read-only bindings: 28 | Live: 7 | Signal research: 6
ToolAnnotations: 38 read · 3 write orchestration (41 exported tools)
```

Historical September 2026 Office connector: **32** tools (19 / 7 / 6) — see table above.

No CAN TX tools. No MCP create/review/confirm/reject candidate tools.

List locally:

```powershell
uv run canresearch mcp tools
```

Exact names are asserted in `tests/test_mcp.py`.

## Layer 1 — Local MCP service

### Start

From the repository root on the same machine that will run `tunnel-client.exe`:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Desktop stdio remains available:

```powershell
uv run canresearch mcp serve
```

### Verify

```powershell
uv run python scripts/mcp_verify_http.py
```

Expected:

```text
url: http://127.0.0.1:8765/mcp
tool_count: 41
read_only: 28
live: 7
signal_research: 6
match: True
```

A plain GET can return HTTP `400` or `406`; that does not by itself mean the
streamable HTTP endpoint is down.

## Layer 2 — OpenAI tunnel

Use the official OpenAI Windows tunnel client. The Office setup was verified with
`tunnel-client` v0.0.14.

Download the normal Windows AMD64 client package, not the
`runtime-cloudflared` archive.

Create one OpenAI tunnel per CAN Research workstation, for example:

```text
can-research-office
```

Create a separate runtime API key, then persist it for the Windows user:

```powershell
setx CONTROL_PLANE_API_KEY "sk-REPLACE_WITH_REAL_RUNTIME_KEY"
```

Close and reopen PowerShell after `setx`.

Create the profile once:

```powershell
$env:CONTROL_PLANE_TUNNEL_ID="tunnel_REPLACE_WITH_REAL_ID"

.\tunnel-client.exe init `
  --sample sample_mcp_remote_no_auth `
  --profile can-research-office `
  --tunnel-id $env:CONTROL_PLANE_TUNNEL_ID `
  --mcp-server-url http://127.0.0.1:8765/mcp
```

The tunnel ID is then stored in the profile under the Windows user's config
directory.

Verify with:

```powershell
.\tunnel-client.exe doctor --profile can-research-office --explain --health.listen-addr 127.0.0.1:8081
```

Office expected result:

```text
RESULT ok
```

Start the tunnel:

```powershell
.\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

Leave the process running while ChatGPT is using the connector.

For the full install sequence, API-key UI details, port-conflict handling, and
common failure cases, use [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md).

## Layer 3 — ChatGPT plugin/connector

Only configure/discover the connector while both are running:

1. CAN Research MCP on `127.0.0.1:8765`
2. `tunnel-client.exe run ...`

The ChatGPT plugin page should populate an **Actions** section with the MCP tool
schema. That is the sign that schema discovery succeeded.

### Fresh-chat verification

Ask:

> How many CAN Research tools can you see? List their names.

Expected (current baseline):

```text
41 tools
28 read-only/offline bindings
7 live CANsub
6 proprietary signal-research
```

(Historical fresh-chat checks in September 2026 expected **32** tools / **19** read-only.)

Then:

> Call `get_instance_info`.

Expected Office identity:

```text
instance_key: office
display_name: CAN Research - Office
```

Then:

> Call `list_sessions` with `limit=5`.

Passive live test, if CANsub.2 is available:

> Call `get_cansub_device_status`.

*(Not re-run during the 2026-09-06 reboot test — do not assume hardware path verified that day.)*

## Normal startup (already installed)

Do **not** repeat one-time installation. After reboot, start only:

1. CAN Research MCP server
2. OpenAI `tunnel-client.exe`

Full commands, CMD vs PowerShell notes, and “do not recreate” list:

[MCP_SETUP.md — Normal startup after reboot](MCP_SETUP.md#normal-startup-after-reboot)

The ChatGPT connector and installed **can-signal-research** Skill persist across reboot.

## Troubleshooting

Always troubleshoot from the inside out:

| Layer | Symptom | Check |
|---|---|---|
| Local MCP | Wrong tool count | `uv run python scripts/mcp_verify_http.py` |
| Local MCP | Connection refused | MCP process running? Port 8765 free? |
| Tunnel | Doctor fails | `tunnel-client doctor --profile ... --explain` |
| Tunnel | Health listener collision | `netstat -ano \| findstr :8080`; identify PID before changing anything |
| Tunnel | API auth error | Check persisted `CONTROL_PLANE_API_KEY` in a new PowerShell session |
| ChatGPT | No Actions/tool schema | Confirm both MCP and tunnel are running first |
| ChatGPT | Stale/missing tools | Re-check lower layers, then use a fresh chat; do not immediately recreate the plugin |
| Identity | Wrong backend | `get_instance_info` must match the machine's configured instance |

## Connector verification checklist

**September 2026 (historical — 32-tool baseline)**

- [x] MCP tools at **32** (19 / 7 / 6) at initial Office validation
- [x] Streamable HTTP transport at `http://127.0.0.1:8765/mcp`
- [x] Local initialize + 32-tool verification passed
- [x] Multi-instance configuration (`instance_key`, `display_name`, `get_instance_info`)
- [x] Official Windows tunnel client installed
- [x] OpenAI tunnel `can-research-office` created
- [x] Runtime API key created and persisted
- [x] Tunnel profile `can-research-office` created
- [x] Tunnel doctor passed using health listener `127.0.0.1:8081`
- [x] ChatGPT plugin discovered the Actions schema
- [x] Fresh-chat tool-name/count check passed with **32 tools**
- [x] `get_instance_info` rechecked after Windows reboot (**2026-09-06**) — `office` / schema **v8** / **32 tools**

**October 2026 (current — 41-tool baseline)**

- [x] MCP server restarted; connector **Refresh tools** — **41** public tools visible
- [x] Explicit **ToolAnnotations** on every exported tool (38 read · 3 write orchestration)
- [x] CH1 `start_live_capture` → `recording`; deliberate `stop_live_capture` → **`completed`** (**2026-10-03**)
- [x] Subsequent start rejected at passive timing preflight (`timing_proof_failed`) when bus quiet — not channel stuck
- [ ] Re-run `get_cansub_device_status` when hardware is available
