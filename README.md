# CAN Research

CAN Research is a toolkit for **understanding, documenting, and researching real CAN
networks**, built around [CSS Electronics CANsub.2](https://www.csselectronics.com/)
hardware and a **passive, evidence-first** workflow.

It is for engineers and technicians working on tractors, implements, industrial
controllers, and mixed J1939/proprietary buses — anyone who needs to move beyond ad-hoc
scripts and scattered PDFs toward **persistent, asset-scoped machine knowledge**.

## What problem it solves

Real CAN reverse engineering usually scatters knowledge across log files, one-off Python
scripts, DBC exports, and chat transcripts. CAN Research keeps capture, reference
catalogues, registered DBCs, normalized manual knowledge, session analysis, and
AI-guided research in **one operator-controlled workflow**.

The guiding idea is **known-first**:

```text
Use existing knowledge first.
Research only what remains unknown.
```

That means applying, in order: J1939/ISOBUS catalogue knowledge → normalized reference
bundles → registered DBCs → confirmed local research — before treating traffic as
proprietary.

## How the pieces fit together

```text
CAN bus  →  CANsub.2  →  CAN Research core  →  MCP  →  ChatGPT / Skills
```

| Layer | Role |
|-------|------|
| **CAN Research core** | Deterministic capture, sessions, reference import, DBC library, coverage, evidence |
| **MCP server** | Bounded read-only API for AI clients (passive live observation; no CAN TX) |
| **Skills** | Guided workflows: onboarding, reference conversion, signal research |

Three Skills ship as source under `skills/` (package locally — see
[SKILL_INSTALLATION.md](docs/SKILL_INSTALLATION.md)):

| Skill | When to use |
|-------|-------------|
| **can-onboarding** | Fresh install, second laptop, post-reboot recovery |
| **can-reference-builder** | Messy PDF/XLSX/CSV/manual → Reference Bundle V1 JSON |
| **can-signal-research** | Known-first proprietary signal research |

## AI-guided workflows

CAN Research is designed to be operated **with generative AI** — not as a replacement for
deterministic measurement, but as the interactive layer that helps you navigate setup,
reference intake, and research without memorizing every command and document first.

```text
CAN Research core  →  MCP  →  Skills  →  AI (ChatGPT / compatible host)
```

| Layer | Role |
|-------|------|
| **CAN Research core** | Deterministic CAN capabilities — capture, sessions, reference import, DBC library, coverage, evidence |
| **MCP** | Exposes those capabilities to AI clients (bounded, passive; no CAN TX) |
| **Skills** | Guided workflows, domain reasoning, and orchestration for multi-step tasks |
| **AI** | Interactive operator layer — adapts steps to your machine, answers, and prior context |

**Use each layer for what it does best:**

- **Documentation** stores stable instructions
- **Deterministic core** verifies facts
- **MCP** exposes bounded capabilities
- **AI** adapts workflow to the user
- **Specialist Skills** guide higher-level tasks

Skills are the **recommended interface for complex workflows** — onboarding, reference
ingestion, proprietary signal research. They are not a novelty or demo layer. The **CLI**
and **MCP** remain fully available for direct, manual, scripted, or automated use when you
know exactly what you need.

You do **not** need to understand the entire system before beginning. Install
**can-onboarding**, connect MCP, and work through its checkpoints — it verifies each stage,
skips what is already proven, and hands off to specialist Skills where appropriate.

### Specialist Skills

Source under `skills/` — package locally: [SKILL_INSTALLATION.md](docs/SKILL_INSTALLATION.md).

**can-onboarding**

- First-time installation guidance
- CANsub.2 setup
- MCP / tunnel / connector setup
- Skill installation
- DBC and reference onboarding verification
- Smoke testing
- Troubleshooting common setup issues
- Handoff to research Skills

**can-reference-builder**

- Converts OEM manuals, PDFs, spreadsheets, DBCs, CSV, text, and other source material into normalized CAN reference knowledge
- Preserves provenance and uncertainty
- Guides validate/import (CAN Research core performs deterministic import)

**can-signal-research**

- Standards-first / known-first analysis
- DBC coverage
- Passive inference
- Controlled experiments
- Proprietary signal research
- Evidence and confidence reporting

### Typical new-user path

```text
New user
   ↓
Install CAN Research
   ↓
Start can-onboarding
   ↓
Verify CANsub.2 + MCP
   ↓
Import existing DBC / reference knowledge
   ↓
Begin CAN research (can-signal-research)
```

Architecture detail: [AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md).

## Where to start

| Goal | Start here |
|------|------------|
| Install and validate a new machine | [docs/USER_ONBOARDING.md](docs/USER_ONBOARDING.md) · **can-onboarding** |
| DBCs, manuals, licensing, reference model | [docs/REFERENCE_DATA.md](docs/REFERENCE_DATA.md) |
| **OEM manual / PDF / spreadsheet intake** | [docs/REFERENCE_ONBOARDING.md](docs/REFERENCE_ONBOARDING.md) · **can-reference-builder** |
| Bundle schema / JSON contract | [docs/REFERENCE_BUNDLE_FORMAT.md](docs/REFERENCE_BUNDLE_FORMAT.md) |
| Proprietary signal research architecture | [docs/AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md) · **can-signal-research** |
| Why CAN Research exists (positioning) | [docs/PRODUCT_POSITIONING.md](docs/PRODUCT_POSITIONING.md) |

## Safety and trust boundaries

- **Passive MCP** — no arbitrary CAN TX, replay, injection, or autonomous machine control
- **CLI-only confirmation** — research candidates are not confirmed through MCP
- **Separate knowledge classes** — reference-backed vs DBC vs confirmed research vs AI hypothesis
- **Licensed material** — never commit SAE/ISO/OEM source documents; keep private originals local

Details: [REFERENCE_DATA.md](docs/REFERENCE_DATA.md) · [AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md)

## V1 at a glance

| Area | Current capability |
|------|-------------------|
| Hardware | CANsub.2 (USB mDNS hostname or Ethernet) |
| Reference | J1939/ISOBUS PDF catalogue; source registry + Reference Bundle V1 import |
| DBC | Library register/inspect/coverage; `<asset>_standard.dbc` / `<asset>_research.dbc` |
| MCP | **41 tools** (28 read-only · 7 live/passive · 6 signal research) — verify with `uv run canresearch mcp tools` |
| Database schema | **v9** (`get_instance_info` reports current version) |
| GUI | None — CLI-first |

Milestone history: [docs/V1_SCOPE.md](docs/V1_SCOPE.md). Bench/deployment records:
[CANSUB_CONNECTION.md](docs/CANSUB_CONNECTION.md) · [MCP_CONNECTION.md](docs/MCP_CONNECTION.md).

## Features

| Area | Description |
|------|-------------|
| Hardware | CANsub.2 via configured hostname or Ethernet |
| Protocol | J1939/ISOBUS parsing, reference catalogue, bundle knowledge |
| DBC | Registered library + generated standard/research asset DBCs |
| Assets | Tractor/implement/controller registry with session links |
| Capture | SQLite metadata + JSONL frames under `{data_dir}/sessions/` |
| Configuration | `data/config.toml`: `[instance]`, `[paths]`, `[cansub]` |
| MCP | Passive analysis substrate for AI Skills |
| Storage | SQLite schema v9; frames outside SQLite |

## Licensed / private data

**Do not commit** SAE J1939, ISO 11783, or other licensed standards content.

Policy and workflows: [docs/REFERENCE_DATA.md](docs/REFERENCE_DATA.md). This repository
ships **no** comprehensive J1939/ISOBUS database.

## Getting started

**New users:** install the recommended Skills before beginning setup — see
[SKILL_INSTALLATION.md](docs/SKILL_INSTALLATION.md). They are intended to reduce onboarding
friction and guide verification at each stage, rather than requiring you to manually
interpret every setup document. Then start **can-onboarding** or follow
[USER_ONBOARDING.md](docs/USER_ONBOARDING.md).

Quick software install: [docs/INSTALLATION.md](docs/INSTALLATION.md) · CANsub:
[docs/CANSUB_SETUP.md](docs/CANSUB_SETUP.md) · MCP:
[docs/MCP_SETUP.md](docs/MCP_SETUP.md).

```powershell
uv sync
uv run canresearch config show
uv run canresearch --help
```

**After reboot:** restart MCP + tunnel only — [MCP_SETUP.md](docs/MCP_SETUP.md#normal-startup-after-reboot).

**Multiple machines:** [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md) ·
**Problems:** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

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
```

For named deployments:

```powershell
uv run canresearch config set-instance --key workshop --name "CAN Research - Workshop"
```

Use `uv run canresearch ...` so commands run in the project's uv-managed environment.

## CLI

The CLI is the operator interface for import, capture, assets, research confirmation, and
MCP serving. **Canonical command discovery:**

```powershell
uv run canresearch --help
uv run canresearch reference --help
uv run canresearch session --help
```

Reference onboarding commands (summary):

```powershell
uv run canresearch reference source add <path> --key <key> --visibility private
uv run canresearch reference bundle validate <bundle.json>
uv run canresearch reference bundle import <bundle.json>
uv run canresearch reference dbc register --key <key> <path>
uv run canresearch session dbc-coverage <session-id>
```

Full onboarding sequence: [USER_ONBOARDING.md](docs/USER_ONBOARDING.md).

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
41-tool MCP schemas. There is **no central routing or shared backend** yet.

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
skills/               AI Skills source (can-onboarding, can-reference-builder, can-signal-research)
scripts/              MCP HTTP verification helper
```

## Documentation

### Installation and operations

| Document | Description |
|----------|-------------|
| [docs/USER_ONBOARDING.md](docs/USER_ONBOARDING.md) | **End-to-end new user path** — install, knowledge intake, known-first research |
| [docs/REFERENCE_DATA.md](docs/REFERENCE_DATA.md) | **CAN knowledge model** — catalogue, sources, bundles, DBCs, provenance |
| [docs/REFERENCE_ONBOARDING.md](docs/REFERENCE_ONBOARDING.md) | **Operator workflow** — manual/PDF → source → bundle → import |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Clone, uv, config, first-run smoke test |
| [docs/CANSUB_SETUP.md](docs/CANSUB_SETUP.md) | CANsub.2 connectivity, channels, WebSocket ownership |
| [docs/MCP_SETUP.md](docs/MCP_SETUP.md) | MCP serve, tunnel, ChatGPT connector, reboot startup |
| [docs/SKILL_INSTALLATION.md](docs/SKILL_INSTALLATION.md) | All three Skills — package and install |
| [docs/MULTI_INSTANCE_DEPLOYMENT.md](docs/MULTI_INSTANCE_DEPLOYMENT.md) | Independent machines (office, workshop, laptop, travel) |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Decision guide for common failures |

### Architecture and research

| Document | Description |
|----------|-------------|
| [docs/PRODUCT_POSITIONING.md](docs/PRODUCT_POSITIONING.md) | **Why CAN Research exists** — differentiation, user value, complementary tooling |
| [docs/AI_GUIDED_SIGNAL_RESEARCH.md](docs/AI_GUIDED_SIGNAL_RESEARCH.md) | AI + MCP + Skill workflow for proprietary signal discovery |
| [skills/can-signal-research/SKILL.md](skills/can-signal-research/SKILL.md) | Signal research Skill source |
| [skills/can-onboarding/SKILL.md](skills/can-onboarding/SKILL.md) | Onboarding Skill source |
| [skills/can-reference-builder/SKILL.md](skills/can-reference-builder/SKILL.md) | Reference bundle conversion Skill source |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module boundaries, data flows, MCP and storage design |
| [docs/REFERENCE_BUNDLE_FORMAT.md](docs/REFERENCE_BUNDLE_FORMAT.md) | Reference Bundle V1 schema and validation contract |

### Bench records (historical / deployment-specific)

| Document | Description |
|----------|-------------|
| [docs/CANSUB_CONNECTION.md](docs/CANSUB_CONNECTION.md) | Desk-unit bench notes and verified commands |
| [docs/MCP_CONNECTOR_INSTALL_GUIDE.md](docs/MCP_CONNECTOR_INSTALL_GUIDE.md) | Office MCP/tunnel verified deployment |
| [docs/MCP_CONNECTION.md](docs/MCP_CONNECTION.md) | Per-instance connector verification state |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Completed vs remaining V1 scope (milestone log) |
| [docs/strict_dbc_compatibility_reference.md](docs/strict_dbc_compatibility_reference.md) | Strict DBC / webCAN compatibility target |

## License

MIT — see [LICENSE](LICENSE).
