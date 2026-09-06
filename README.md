# can-research

Windows-first, CLI-first CAN research tool focused on **CSS Electronics CANsub.2**
hardware, **J1939/ISOBUS** reference handling, capture/session analysis,
machine-specific DBC generation, an **MCP server** for deterministic AI access, and a
**CAN Signal Research Skill** for AI-guided proprietary signal discovery.

The project operates in **three layers**:

1. **Deterministic CAN Research core** — parsing, capture, reference lookup, candidate evidence, DBC generation
2. **CAN Research MCP interface** — stable 32-tool substrate (passive live + offline analysis)
3. **CAN Signal Research Skill** — generative workflow orchestration above MCP (ChatGPT/Codex)

Basic J1939/ISOBUS decoding from the reference catalogue is **not** the differentiator.
The value is making **asset-specific proprietary signal discovery** substantially easier
than repeatedly writing one-off Python scripts.

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
| Office ChatGPT MCP connector (live, 32 tools) | Done |
| CAN Signal Research Skill installed in ChatGPT (Office) | Done |
| First passive AI-guided proprietary signal trial (Office bench) | Done |

**Office installation validated:** The CAN Research MCP connector is live on the Office
Windows host (`instance_key = office`), exposes **32 tools**, and the
**can-signal-research** Skill has completed an initial **passive** live-analysis trial
on CANsub.2 channel 1 — no CAN TX, no MCP candidate confirmation. This is an **early
bench validation**, not a finished autonomous reverse-engineering product.

**Next milestone:** Asset-scoped guided research trial (register asset, known baseline,
unknown remainder, passive-first inference, physical experiment only if needed, CLI
confirm). See [docs/AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md).

Connection details: [docs/CANSUB_SETUP.md](docs/CANSUB_SETUP.md) (public) ·
[docs/CANSUB_CONNECTION.md](docs/CANSUB_CONNECTION.md) (bench record).

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
| MCP | 41 tools: stored/offline analysis, reference bundles, DBC library/coverage, passive live CANsub, signal research |
| AI Skill | `can-signal-research` — guided proprietary discovery via ChatGPT + MCP (portable across installations) |
| Storage | SQLite for metadata, references, candidates, findings; frames outside SQLite |

## AI-guided proprietary signal research

The main differentiation is **not** basic J1939/ISOBUS decoding from the reference
catalogue. The intended workflow is:

```text
connect
  → identify / scope asset
  → apply reference-backed knowledge
  → apply existing confirmed asset knowledge
  → build known baseline (<asset>_standard.dbc)
  → inventory proprietary / unknown remainder
  → generative AI forms hypotheses (passive evidence first)
  → MCP gathers deterministic evidence
  → passive inference when sufficient
  → physical experiment only when ambiguity remains
  → propose candidate
  → explicit human confirmation (CLI)
  → research DBC (<asset>_research.dbc)
```

On the **Office** bench, the **can-signal-research** Skill is installed in ChatGPT,
invokes the working CAN Research MCP connector, and has completed a first **passive**
live trial (15 s observation, proprietary PDU1-style traffic, useful field-structure
inferences without operator hardware manipulation). Inferences remain **research
hypotheses** until CLI confirmation — not reference facts or confirmed DBC entries.

Full design contract: [docs/AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md).
Skill scaffold: [skills/can-signal-research/SKILL.md](skills/can-signal-research/SKILL.md).

Safety boundaries unchanged: **passive / no CAN TX**, **32-tool MCP substrate**,
**CLI-only candidate confirmation**, strict **asset scope**, separate
**standard vs research DBC** files.

## Licensed / private data

**Do not commit** SAE J1939, ISO 11783, or other licensed standards content.

Full policy and import options: [docs/REFERENCE_DATA.md](docs/REFERENCE_DATA.md).
Onboarding: [docs/USER_ONBOARDING.md](docs/USER_ONBOARDING.md).

Parsed reference data built from your own licensed sources belongs under `references/private/` or `data/` (both gitignored). This repository ships **no** comprehensive J1939/ISOBUS database.

## Getting started

**New user?** Start here → **[docs/USER_ONBOARDING.md](docs/USER_ONBOARDING.md)** (install +
CANsub + **your existing knowledge** + Skill + known-first research).

**Bringing DBCs / reference material?** → **[docs/REFERENCE_DATA.md](docs/REFERENCE_DATA.md)**

CAN Research has three layers: **deterministic core** → **MCP (41 tools)** →
**CAN Signal Research Skill** (generative orchestration in ChatGPT).

```text
CAN bus
   ↓
CANsub.2
   ↓
CAN Research core
   ↓
MCP
   ↓
ChatGPT / Codex / other MCP client
   ↓
CAN Signal Research Skill
```

### Installation path (summary)

Full 14-step onboarding: **[docs/USER_ONBOARDING.md](docs/USER_ONBOARDING.md)**

| Step | Action | Details |
|------|--------|---------|
| 1 | Install CAN Research | [docs/INSTALLATION.md](docs/INSTALLATION.md) |
| 2–4 | Instance, CANsub, validate traffic | [CANSUB_SETUP.md](docs/CANSUB_SETUP.md) |
| 5–10 | **Add your CAN knowledge** | [REFERENCE_DATA.md](docs/REFERENCE_DATA.md) |
| 11 | MCP + Skill | [MCP_SETUP.md](docs/MCP_SETUP.md) · [SKILL_INSTALLATION.md](docs/SKILL_INSTALLATION.md) |
| 12–14 | Asset, known-first, research remainder | [USER_ONBOARDING.md](docs/USER_ONBOARDING.md) |

**Already installed?** After reboot, restart only MCP + tunnel — [MCP_SETUP.md](docs/MCP_SETUP.md#normal-startup-after-reboot).

**Multiple machines?** Each is self-contained — [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md).

**Problems?** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

### First-run smoke test

```powershell
uv run canresearch device info
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

With MCP connected in ChatGPT:

```text
get_instance_info → get_cansub_device_status → get_cansub_channel_status → observe_live_traffic
```

Confirm frames before research capture. Matches [Skill V2 preflight](skills/can-signal-research/SKILL.md).

## Requirements

- Windows (primary target; Linux/macOS may work for development)
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- Python 3.11+

## Quick start (minimal)

```powershell
uv sync
uv run canresearch config show
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch device info
uv run pytest
```

For the full path see [Getting started](#getting-started) and [docs/INSTALLATION.md](docs/INSTALLATION.md).

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
uv run canresearch session dbc-coverage <session-id> [--source <key> ...] [--asset <key>] [--limit N]
uv run canresearch reference source add <path> --key <key> [--visibility private|public|licensed] ...
uv run canresearch reference source list
uv run canresearch reference source inspect <key>
uv run canresearch reference bundle validate <bundle.json>
uv run canresearch reference bundle import <bundle.json>
uv run canresearch reference search "<query>"
uv run canresearch reference dbc register --key <key> <path> [--name ...] [--type user_supplied|oem|...] [--asset <key>]
uv run canresearch reference dbc list [--asset <key>]
uv run canresearch reference dbc inspect <key>
uv run canresearch reference import-j1939 ...
uv run canresearch mcp tools
```

### MCP serving

Both transports use the **same tool registry** (41 tools). Stdio is for desktop MCP
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

**Already installed?** After a Windows reboot, restart only the **MCP server** and
**tunnel client** — the ChatGPT connector and installed Skill persist.

→ [Normal startup after reboot](docs/MCP_SETUP.md#normal-startup-after-reboot)

### MCP tool surface (41 total)

| Group | Count | Purpose |
|-------|-------|---------|
| Read-only | 28 | Sessions, references, assets, bundles, DBC library/coverage, instance identity |
| Live / passive | 7 | CANsub status, capture, events, bounded live observation |
| Signal research | 6 | Candidate evidence (rank, activity, counters, checksums, correlation) |

**Read-only tools:** `get_instance_info`, `list_sessions`, `get_session`,
`analyze_session`, `decode_session`, `inspect_transport`, `list_session_nodes`,
`list_assets`, `get_asset`, `list_asset_nodes`, `lookup_pgn`, `lookup_spn`,
`build_session_dbc_preview`, `list_research_candidates`, `get_research_candidate`,
`list_candidate_evidence`, `preview_research_dbc`, `list_session_events`,
`preview_candidate_values`, `list_dbc_sources`, `inspect_dbc`, `lookup_dbc_message`,
`lookup_dbc_signal`, `analyze_dbc_coverage`, `list_reference_sources`,
`inspect_reference_source`, `search_reference_knowledge`, `lookup_reference_message`.

**Live tools (passive):** `get_cansub_device_status`, `get_cansub_channel_status`,
`start_live_capture`, `stop_live_capture`, `observe_live_traffic`,
`mark_experiment_event`, `compare_experiment_windows`.

**Signal research:** `rank_signal_candidates`, `analyze_can_id_activity`,
`analyze_repeated_action`, `detect_counters`, `detect_checksums`,
`correlate_candidate_field`.

**MCP can:**

- Inspect references, sessions, assets, nodes, candidates, and evidence
- Preview standard and research DBCs in memory
- List, inspect, and look up registered DBC knowledge sources
- Analyze session coverage against registered DBCs (known-first output)
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

Live experiment workflow (when passive evidence is insufficient):

1. `get_cansub_device_status` → `get_cansub_channel_status`
2. `start_live_capture`
3. `mark_experiment_event` (e.g. `baseline_start`)
4. operator idle / no action
5. `mark_experiment_event` (e.g. `scv2_extend`)
6. operator performs physical action
7. `stop_live_capture`
8. `compare_experiment_windows`
9. `rank_signal_candidates` / `analyze_can_id_activity` / … as needed

Prefer **passive observation first** (`observe_live_traffic`) and contextual inference
before requesting physical actions — see [AI-guided signal research](docs/AI_GUIDED_SIGNAL_RESEARCH.md).

`observe_live_traffic` provides bounded aggregated traffic (default 3s, max 15s;
max 200 rows). It cannot run on a channel with an active capture (`channel_rx_in_use`).

Connector deployment guides:

- [docs/MCP_SETUP.md](docs/MCP_SETUP.md) — **public** MCP + tunnel setup (canonical)
- [docs/MCP_CONNECTOR_INSTALL_GUIDE.md](docs/MCP_CONNECTOR_INSTALL_GUIDE.md) — verified Office deployment record
- [docs/MCP_CONNECTION.md](docs/MCP_CONNECTION.md) — per-instance checklist
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
skills/               AI Skill scaffolds (e.g. can-signal-research)
scripts/              MCP HTTP verification helper
```

## Documentation

### Installation and operations

| Document | Description |
|----------|-------------|
| [docs/USER_ONBOARDING.md](docs/USER_ONBOARDING.md) | **End-to-end new user path** — install, knowledge intake, known-first research |
| [docs/REFERENCE_DATA.md](docs/REFERENCE_DATA.md) | **CAN knowledge model** — catalogue, sources, bundles, DBCs, provenance |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Clone, uv, config, first-run smoke test |
| [docs/CANSUB_SETUP.md](docs/CANSUB_SETUP.md) | CANsub.2 connectivity, channels, WebSocket ownership |
| [docs/MCP_SETUP.md](docs/MCP_SETUP.md) | MCP serve, tunnel, ChatGPT connector, reboot startup |
| [docs/SKILL_INSTALLATION.md](docs/SKILL_INSTALLATION.md) | CAN Signal Research Skill install/update |
| [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md) | Independent machines (office, workshop, laptop, travel) |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Decision guide for common failures |

### Architecture and research

| Document | Description |
|----------|-------------|
| [docs/PRODUCT_POSITIONING.md](docs/PRODUCT_POSITIONING.md) | **Why CAN Research exists** — differentiation, user value, complementary tooling |
| [docs/AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md) | AI + MCP + Skill workflow for proprietary signal discovery |
| [skills/can-signal-research/SKILL.md](skills/can-signal-research/SKILL.md) | ChatGPT Skill source (canonical) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module boundaries, data flows, MCP and storage design |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Completed vs remaining V1 scope |

### Bench records (historical / deployment-specific)

| Document | Description |
|----------|-------------|
| [docs/CANSUB_CONNECTION.md](docs/CANSUB_CONNECTION.md) | Desk-unit bench notes and verified commands |
| [docs/MCP_CONNECTOR_INSTALL_GUIDE.md](docs/MCP_CONNECTOR_INSTALL_GUIDE.md) | Office MCP/tunnel verified deployment |
| [docs/MCP_CONNECTION.md](docs/MCP_CONNECTION.md) | Per-instance connector verification state |
| [docs/strict_dbc_compatibility_reference.md](docs/strict_dbc_compatibility_reference.md) | Strict DBC / webCAN compatibility target |

## License

MIT — see [LICENSE](LICENSE).
