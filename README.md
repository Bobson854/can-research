# can-research

Windows-first, CLI-first CAN research tool focused on **CSS Electronics CANsub.2** hardware, **J1939/ISOBUS** reference handling, capture/session analysis, machine-specific DBC generation, and an **MCP server** for AI-assisted interrogation (ChatGPT, Claude, etc.).

## Current status

The following milestones are **complete** on the development desk unit (Device ID
`7413f810`, firmware **02.04.00**, API **04.00**).

| Milestone | Status |
|-----------|--------|
| Private J1939 reference catalogue (PDF import) | Done |
| ISOBUS DDI import | Done |
| CANsub direct REST connection | Done |
| Persistent configurable host | Done |
| Read-only channel status | Done |
| WebSocket RX | Done |
| Persistent capture sessions (JSONL + SQLite) | Done |
| Real CAN bus capture (EDGE101 bench) | Done |
| Offline J1939 session classification | Done |
| Offline J1939 SPN value decode (known PGNs) | Done |
| Base machine DBC from reference-backed sessions | Done |
| Asset registry and session asset associations | Done |
| Asset-specific DBC provenance | Done |
| J1939 transport-protocol reassembly (BAM / RTS-CTS) | Done |
| J1939 NAME / Address Claim → asset identity mapping | Done |
| Read-only MCP session/research tools | Done |
| Live CANsub.2 MCP research controls (passive) | Done |
| Proprietary signal research primitives | Done |
| Candidate review / confirmation workflow (CLI) | Done |
| Asset research DBC generation (`<asset>_research.dbc`) | Done |
| MCP analysis tools (`list_session_events`, `preview_candidate_values`) | Done |
| Streamable HTTP MCP transport (`/mcp` on port 8765) | Done |
| Multi-instance backend configuration (`instance_key`, `display_name`) | Done |
| MCP instance identification (`get_instance_info`) | Done |

**MCP software is ready for connector deployment.** The ChatGPT connector and OpenAI
tunnel have **not** been installed or verified yet.

**Next operational milestone:** Deploy/configure the first CAN Research MCP tunnel
+ ChatGPT connector per installation, then perform guided live reverse-engineering
validation.

Connection details, bench lessons, and tested commands:
[docs/CANSUB_CONNECTION.md](docs/CANSUB_CONNECTION.md).

## V1 goal

1. **Build or import** a parsed local PGN/SPN reference database (from user-owned sources).
2. **Build a base tractor DBC** from a CANsub.2 logging session.
3. **Expose** sessions, reference lookups, correlation analysis, and DBC refinement through MCP.

No GUI in V1. No bundled SAE J1939 database.

## Features

| Area | Description |
|------|-------------|
| Hardware | CANsub.2 via USB (configured hostname) or Ethernet |
| Protocol | J1939/ISOBUS 29-bit identifier parsing and reference catalogue |
| DBC | Generate `<asset>_standard.dbc` from sessions; `<asset>_research.dbc` from confirmed candidates |
| Assets | Registry of tractor/implement/controller devices with session links |
| Capture | Session metadata in SQLite; raw frames in JSONL under `{data_dir}/sessions/` |
| Configuration | TOML at `data/config.toml`: `[instance]`, `[paths]`, `[cansub]` |
| MCP | 32 tools: stored/offline analysis, passive live CANsub research, signal research, instance identity |
| Storage | SQLite for metadata, references, candidates, findings; frames outside SQLite |

## Licensed / private data

**Do not commit** SAE J1939, ISO 11783, or other licensed standards content. Parsed reference data built from your own licensed sources belongs under `references/private/` or `data/` (both gitignored). This repository ships **no** comprehensive J1939/ISOBUS database.

## Requirements

- Windows (primary target; Linux/macOS may work for development)
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- Python 3.11+

## Quick start

```powershell
uv sync
uv run canresearch config show
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch device info
uv run pytest
```

Development defaults work without setting an instance (`instance_key = local`).
For a named deployment (workshop laptop, travel laptop, etc.):

```powershell
uv run canresearch config set-instance --key workshop --name "CAN Research - Workshop"
```

Repository examples use `uv run canresearch ...`, which runs the CLI inside the
project's uv-managed environment. A bare `canresearch ...` command only works if
the package has separately been installed on PATH.

## CLI commands

```text
uv run canresearch --help
uv run canresearch config show
uv run canresearch config set-instance --key <key> --name "<display name>"
uv run canresearch config set-host <hostname-or-ip>
uv run canresearch config set-data-dir <path>
uv run canresearch device info
uv run canresearch device channel-info <channel>
uv run canresearch device rx <channel>
uv run canresearch capture start --channel <n>
uv run canresearch capture stop [<session-id>]
uv run canresearch session list
uv run canresearch session summary <session-id>
uv run canresearch session analyze <session-id>
uv run canresearch session decode <session-id>
uv run canresearch session tp <session-id>
uv run canresearch session nodes <session-id> [--refresh] [--source-address 0x80] [--show-raw]
uv run canresearch asset add --key <key> --type tractor --name "..."
uv run canresearch asset list
uv run canresearch asset show <asset-key>
uv run canresearch asset node add <asset-key> <j1939-name>
uv run canresearch asset node list <asset-key>
uv run canresearch asset node remove <asset-key> <j1939-name>
uv run canresearch session asset add <session-id> <asset-key> --role tractor
uv run canresearch session asset list <session-id>
uv run canresearch session event add <session-id> --label "baseline_start"
uv run canresearch session event list <session-id>
uv run canresearch session compare <session-id> --baseline-event baseline_start --action-event scv2_extend
uv run canresearch session research rank <session-id> --baseline-event ... --action-event ...
uv run canresearch session research id <session-id> <can-id> ...
uv run canresearch session research counters <session-id> <can-id>
uv run canresearch session research checksums <session-id> <can-id>
uv run canresearch session research repeat <session-id> --baseline-events ... --action-events ...
uv run canresearch research candidate add --asset <key> --session <id> --can-id 0x... --start-bit N --length N --byte-order intel
uv run canresearch research candidate list [--asset <key>] [--status candidate|reviewed|confirmed|rejected]
uv run canresearch research candidate show <candidate-id>
uv run canresearch research candidate review <candidate-id>
uv run canresearch research candidate confirm <candidate-id> --name ... --factor ... --offset ... --unsigned
uv run canresearch research candidate reject <candidate-id> [--notes "..."]
uv run canresearch research candidate evidence <candidate-id>
uv run canresearch research dbc <asset-key> [--output path]
uv run canresearch session dbc <session-id> --asset <asset-key> [--source-address 0x00]
uv run canresearch reference import-j1939 ...
uv run canresearch mcp tools
```

### MCP serving

Both transports use the **same tool registry** (32 tools). Stdio is for desktop MCP
clients; streamable HTTP is for OpenAI tunnel / ChatGPT connector deployment.

**Stdio (Cursor, Claude Desktop, etc.):**

```powershell
uv run canresearch mcp serve
```

**Streamable HTTP (local connector endpoint):**

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Standard deployment example endpoint:

```text
http://127.0.0.1:8765/mcp
```

Port **8765** is a project convention (avoids BLE Research on `8000`), not an MCP
protocol requirement. Each laptop may use the same port because hosts differ.

A plain `GET` to `/mcp` may return HTTP **400** (missing session ID). That does
**not** mean the endpoint is down. Authoritative checks:

```powershell
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

### MCP tool surface (32 total)

| Group | Count | Purpose |
|-------|-------|---------|
| Read-only | 19 | Sessions, references, assets, candidates, DBC preview, instance identity |
| Live / passive | 7 | CANsub status, capture, events, bounded live observation |
| Signal research | 6 | Candidate evidence (rank, activity, counters, checksums, correlation) |

**Read-only tools:** `get_instance_info`, `list_sessions`, `get_session`,
`analyze_session`, `decode_session`, `inspect_transport`, `list_session_nodes`,
`list_assets`, `get_asset`, `list_asset_nodes`, `lookup_pgn`, `lookup_spn`,
`build_session_dbc_preview`, `list_research_candidates`, `get_research_candidate`,
`list_candidate_evidence`, `preview_research_dbc`, `list_session_events`,
`preview_candidate_values`.

**Live tools (passive):** `get_cansub_device_status`, `get_cansub_channel_status`,
`start_live_capture`, `stop_live_capture`, `observe_live_traffic`,
`mark_experiment_event`, `compare_experiment_windows`.

**Signal research:** `rank_signal_candidates`, `analyze_can_id_activity`,
`analyze_repeated_action`, `detect_counters`, `detect_checksums`,
`correlate_candidate_field`.

**MCP can:**

- Inspect references, sessions, assets, nodes, candidates, and evidence
- Preview standard and research DBCs in memory
- Identify which CAN Research backend instance is connected (`get_instance_info`)
- Observe live traffic, start/stop passive capture, mark experiment events
- Compare experiment windows and run deterministic signal research

**MCP cannot:**

- Create, review, confirm, or reject research candidates (CLI-only human boundary)
- Mutate confirmed DBC files or write DBCs to disk
- Transmit CAN or perform arbitrary bus injection

**No CAN transmission tools** are registered. Physical actions remain
human-in-the-loop.

Offline agent workflow:

1. `get_instance_info` (when multiple connectors may exist)
2. `list_sessions` → `get_session`
3. `analyze_session` → `list_session_nodes`
4. `lookup_pgn` / `lookup_spn`
5. `decode_session` → `inspect_transport` (if needed)
6. `list_session_events` (recover experiment markers)
7. `get_asset` / `list_asset_nodes`
8. `build_session_dbc_preview` / `preview_candidate_values` (analysis only)

Live experiment workflow:

1. `get_cansub_device_status` → `get_cansub_channel_status`
2. `start_live_capture`
3. `mark_experiment_event` (e.g. `baseline_start`)
4. operator idle / no action
5. `mark_experiment_event` (e.g. `scv2_extend`)
6. operator performs physical action
7. `stop_live_capture`
8. `compare_experiment_windows`
9. `rank_signal_candidates` / `analyze_can_id_activity` / … as needed

`observe_live_traffic` provides bounded aggregated traffic (default 3s, max 15s;
max 200 rows). It cannot run on a channel with an active capture (`channel_rx_in_use`).

Connector deployment guides (not yet executed):

- [docs/MCP_CONNECTION.md](docs/MCP_CONNECTION.md)
- [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md)

### Signal research (candidate evidence only)

After capture and experiment marking, use deterministic research primitives to rank
**candidates** — not confirmed signals. **No DBC files are modified automatically.**

**Candidate ≠ confirmed.** Persisted candidates require explicit CLI review and confirmation
before inclusion in `<asset_key>_research.dbc`. MCP exposes read-only candidate listing and
research DBC preview only.

### Candidate review → research DBC

```text
research evidence (session research / MCP signal tools)
  ↓ explicit CLI: research candidate add
candidate
  ↓ research candidate review
reviewed
  ↓ research candidate confirm (--name, --factor, --offset, signedness)
confirmed
  ↓ research dbc <asset-key>
<asset_key>_research.dbc
```

Load `<asset_key>_standard.dbc` (reference-backed J1939) and `<asset_key>_research.dbc`
(confirmed proprietary signals) together. No combined DBC is generated.

Frame identity for candidates and research DBC grouping is `(is_extended, can_id)`.

### Multi-instance model

Each laptop/backend is an **independent installation** with the same code and identical
32-tool MCP schemas. There is **no central routing or shared backend** yet.

| Concept | Meaning |
|---------|---------|
| **Instance** | Laptop/backend installation (`instance_key`, `display_name`) |
| **CANsub** | Physical CAN interface currently reachable from that installation |
| **Asset** | Machine/implement/controller being researched |
| **Session** | One recorded research/capture session (UUID) |
| **Connector** | ChatGPT route to one backend instance |

Examples (deployment configuration only — not hard-coded in application logic):

| | Workshop | Travel |
|---|---|---|
| `instance_key` | `workshop` | `travel` |
| Local MCP | `http://127.0.0.1:8765/mcp` | `http://127.0.0.1:8765/mcp` |
| Tunnel profile | `can-research-workshop` | `can-research-travel` |
| ChatGPT app | CAN Research - Workshop | CAN Research - Travel |

Same code, same MCP tool schemas, independent local data, independent tunnels/connectors.
CANsub hardware may move between installations — configure `[cansub].host` per machine.

See [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md) for full detail.

### Agricultural workflow example

```powershell
uv run canresearch session nodes abc123
uv run canresearch asset node add jd_6155r_01 0xAABBCCDDEEFF0011
uv run canresearch session dbc abc123 --asset jd_6155r_01
```

## Project layout

```text
src/canresearch/
  cli.py              CLI entry point
  config.py           Instance, paths, CANsub configuration
  core/               J1939, DBC, references, sessions, analysis
  cansub/             CANsub.2 API, WebSocket RX, capture
  mcp/                MCP server (stdio + streamable-http)
  storage/            SQLite metadata and migrations
config/examples/      Workshop/travel deployment examples
scripts/              MCP HTTP verification helper
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/CANSUB_CONNECTION.md](docs/CANSUB_CONNECTION.md) | Desk-unit connection notes, bench lessons, verified commands |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module boundaries, data flows, MCP and storage design |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Completed vs remaining V1 scope and success criteria |
| [docs/MCP_CONNECTION.md](docs/MCP_CONNECTION.md) | Per-instance ChatGPT connector checklist (tunnel not yet deployed) |
| [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md) | Multi-laptop deployment model and configuration |
| [docs/strict_dbc_compatibility_reference.md](docs/strict_dbc_compatibility_reference.md) | Strict DBC / webCAN compatibility target |

## License

MIT — see [LICENSE](LICENSE).
