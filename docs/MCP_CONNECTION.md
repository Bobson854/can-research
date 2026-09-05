# CAN Research MCP connection

Per-instance operational guide for exposing a local CAN Research MCP server to ChatGPT
via an OpenAI tunnel. **MCP software is ready; no ChatGPT connector or tunnel profile
has been verified yet.**

See also:

- [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md) — three-layer troubleshooting
- [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) — workshop/travel model

## Three independent states

These must **all** agree before tools work in ChatGPT:

1. **Local MCP service** — 32 tools, initialize OK, correct `get_instance_info`
2. **OpenAI tunnel** — healthy, targets `http://127.0.0.1:8765/mcp` on the same host
3. **ChatGPT app** — published schema refreshed, app enabled in the chat/workspace

## Per-instance deployment record

Fill one block per laptop/backend **before** creating its ChatGPT connector:

| Field | Example (workshop) | Example (travel) |
|---|---|---|
| `instance_key` | `workshop` | `travel` |
| `display_name` | `CAN Research - Workshop` | `CAN Research - Travel` |
| Local MCP port | `8765` | `8765` |
| Local MCP URL | `http://127.0.0.1:8765/mcp` | `http://127.0.0.1:8765/mcp` |
| Tunnel profile | `can-research-workshop` | `can-research-travel` |
| ChatGPT connector name | `CAN Research - Workshop` | `CAN Research - Travel` |
| Last successful verification | _date_ | _date_ |

Confirm backend identity after connect: MCP tool `get_instance_info()`.

## Summary (template — dev host)

| Item | Value |
|---|---|
| Project | CAN Research |
| Schema version | 8 |
| MCP tool count | **32** |
| Read-only | 19 |
| Live (passive CANsub) | 7 |
| Signal research | 6 |
| Local MCP URL | `http://127.0.0.1:8765/mcp` |
| Bind host | `127.0.0.1` |
| Bind port | `8765` |
| MCP transport | **streamable-http** (stdio still available for desktop clients) |
| Tunnel profile name | `can-research-<instance_key>` (e.g. `can-research-workshop`) |
| Tunnel target URL | `http://127.0.0.1:8765/mcp` |
| ChatGPT app authentication | **No auth** (match BLE Research / internal read-only pattern) |
| Last successful local verification | **2026-09-05** (Windows dev host) |

> **Do not delete/recreate the ChatGPT app merely because tool schemas appear stale.**
> Verify local MCP, then tunnel, then refresh the existing app schema and test in a
> fresh chat.

## Expected tool inventory (frozen)

```
Total: 32
Read-only: 19 | Live: 7 | Signal research: 6
```

No CAN TX tools. No MCP create/review/confirm/reject candidate tools.

List locally:

```powershell
uv run canresearch mcp tools
```

Exact names are asserted in `tests/test_mcp.py`.

## Layer 1 — Local MCP service

### Transport

The server registry is shared. Desktop MCP clients use **stdio**; ChatGPT / OpenAI
tunnel uses **streamable-http** at `/mcp`.

Previously the implementation was **stdio only**; a thin transport adapter was added
in `serve()` — no duplicate handlers or schema changes.

### Start (streamable-http for tunnel)

From the repository root on the **same host that runs the tunnel client**:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Stdio (Cursor / Claude Desktop):

```powershell
uv run canresearch mcp serve
```

Port **8765** is chosen to avoid collision with BLE Research (`8000`).

### Check local status

1. Process listening:

   ```powershell
   curl.exe -i http://127.0.0.1:8765/mcp
   ```

   A plain `GET` may return `400 Bad Request` (missing session ID). That indicates
   the endpoint is up — not a failure.

2. MCP initialize + tool list (authoritative):

   ```powershell
   uv run python scripts/mcp_verify_http.py
   uv run python scripts/mcp_verify_http.py --url http://127.0.0.1:8765/mcp
   ```

   Expect: `tool_count: 32`, `match: True`.

3. Registry listing (no HTTP session):

   ```powershell
   uv run canresearch mcp tools
   ```

4. Automated tests:

   ```powershell
   uv run pytest
   uv run ruff check .
   ```

### Smoke tests

**Read-only (safe, no hardware):**

```text
get_instance_info()
list_sessions(limit=5)
```

**Passive live (after ChatGPT connector is active; requires CANsub.2 on network):**

```text
get_cansub_device_status()
```

Do not run the live test unless hardware is available.

## Layer 2 — OpenAI tunnel

### Client location

BLE Research uses `/opt/openai-tunnel-client` on the Linux tunnel host, profile
`ble-research` → `http://127.0.0.1:8000/mcp`.

CAN Research uses a **separate per-instance profile** (e.g. `can-research-workshop`) → `http://127.0.0.1:8765/mcp`.

**Important:** The MCP server and tunnel client must run on the **same machine**
(tunnel targets `127.0.0.1`). Deploy or run CAN Research on the tunnel host before
creating the profile.

### Status on this milestone

| Check | Result (2026-09-05) |
|---|---|
| Local MCP HTTP verified | Yes — 32 tools, initialize OK |
| `openai-tunnel-client` on Windows dev host | **Not installed** |
| WSL / `/opt/openai-tunnel-client` | **Not available** on Windows dev host |
| Profile `can-research-<instance_key>` created | **Pending** — requires tunnel host access |
| BLE `ble-research` profile | **Not modified** (not present on this host) |

### Create profile (on tunnel host)

Run on the machine where `/opt/openai-tunnel-client` is installed. Inspect the
client's current CLI first — do not assume syntax:

```bash
/opt/openai-tunnel-client --help
/opt/openai-tunnel-client profile list
/opt/openai-tunnel-client profile show ble-research   # reference only — do not edit
```

Create **one** new profile per instance (example — adjust to actual client syntax):

```bash
# Example pattern; replace with commands from --help / ble-research service unit
/opt/openai-tunnel-client profile create can-research-workshop \
  --target http://127.0.0.1:8765/mcp
/opt/openai-tunnel-client profile start can-research-workshop
/opt/openai-tunnel-client profile status can-research-workshop
```

Verify:

- Profile `can-research-<instance_key>` exists separately from `ble-research`
- Target URL is `http://127.0.0.1:8765/mcp`
- Process stays running; status shows connected/healthy
- Stable tunnel URL is printed (record below once available)
- No repeated auth/reconnect errors
- `ble-research` profile and URL unchanged

Record when configured:

| Field | Value |
|---|---|
| Tunnel client path | `/opt/openai-tunnel-client` |
| Tunnel client version | _TBD — run client `--version` on tunnel host_ |
| Profile name | `can-research-<instance_key>` (e.g. `can-research-workshop`) |
| Public tunnel URL | _TBD after profile start_ |

### Start / restart tunnel

Use the tunnel host's service manager or client CLI (same as BLE). Example:

```bash
/opt/openai-tunnel-client profile restart can-research-workshop
/opt/openai-tunnel-client profile status can-research-workshop
```

## Layer 3 — ChatGPT app (manual)

Stop here until layers 1 and 2 are proven on the tunnel host.

### Manual setup values

| Field | Value |
|---|---|
| Connector / app name | **CAN Research - \<display name\>** (e.g. CAN Research - Workshop) |
| Tunnel URL | _TBD — from `can-research-<instance_key>` profile status_ |
| Expected tools | **32** |
| Authentication | **No auth** (internal read-only; match tunnel setup) |
| Tool groups | 19 read-only / 7 live / 6 signal research |

### Fresh-chat verification

Ask:

> How many CAN Research tools can you see? List their names.

Then run read-only smoke tests:

> Call `get_instance_info` and confirm `instance_key` matches this installation.

> Call `list_sessions` with `limit=5` and summarize the result.

Passive live (if CANsub available):

> Call `get_cansub_device_status` and report whether a device is reachable.

## Troubleshooting (three layers)

| Layer | Symptom | What to check | Likely cause |
|---|---|---|---|
| **1. Local MCP** | Wrong tool count locally | `uv run canresearch mcp tools`; `scripts/mcp_verify_http.py`; `pytest tests/test_mcp.py` | Code/deploy issue — fix before tunnel or ChatGPT |
| **1. Local MCP** | Connection refused | Server process running? Port 8765 free? | Service not started or wrong port |
| **1. Local MCP** | Initialize fails | Server logs; verify script output | Transport misconfiguration |
| **2. Tunnel** | Tunnel unhealthy | `profile status can-research-<instance_key>`; process list | Wrong target URL or local MCP down |
| **2. Tunnel** | Calls fail through tunnel | Curl/script against `127.0.0.1:8765/mcp` from tunnel host | Tunnel OK but backend unhealthy |
| **2. Tunnel** | BLE broken after CAN setup | `ble-research` profile unchanged; still targets `:8000/mcp` | Accidental profile overwrite |
| **3. ChatGPT app** | Stale/missing tools | App config tool count vs local 32 | Schema cache — refresh tunnel, re-check app, **new chat** |
| **3. ChatGPT app** | Works in one chat only | App enabled for that chat/workspace | Enable app; use fresh chat for authoritative test |

## Release checklist (connector)

- [x] MCP tools frozen at 32 (19 / 7 / 6)
- [x] Streamable HTTP transport at `http://127.0.0.1:8765/mcp`
- [x] Local initialize + 32-tool verification passed (2026-09-05)
- [x] Multi-instance configuration (`instance_key`, `display_name`, `get_instance_info`)
- [ ] CAN Research MCP running on tunnel host alongside tunnel client
- [ ] Tunnel profile `can-research-<instance_key>` healthy
- [ ] ChatGPT connector created with tunnel URL (not yet done)
- [ ] Fresh-chat tool-name check passes
- [ ] Read-only smoke test (`list_sessions(limit=5)`) passes in chat
