# V1 scope

## Completed (desk bench)

- [x] CANsub.2 direct REST connection (configured hostname or Ethernet IP)
- [x] Persistent local config (`data/config.toml`: `[instance]`, `[paths]`, `[cansub]`)
- [x] Multi-instance installation identity (`instance_key`, `display_name`)
- [x] Read-only channel status (channels 1 and 2)
- [x] WebSocket RX
- [x] Live capture with session metadata in SQLite
- [x] JSONL `CaptureStore` for raw frames (`{data_dir}/sessions/`)
- [x] Real CAN bus capture — EDGE101 two-node bench (session `9622f81f1e67`, 116 frames)
- [x] Offline J1939 session classification (`session analyze`)
- [x] Offline J1939 SPN value decode for known standard PGNs (`session decode`)
- [x] Base machine DBC from reference-backed sessions (`session dbc`)
- [x] Asset registry and session asset associations (`asset`, `session asset`)
- [x] Asset-specific DBC provenance and filename convention
- [x] J1939 transport-protocol reassembly (`session tp`)
- [x] J1939 NAME / Address Claim → asset identity mapping (`session nodes`, `asset node`)
- [x] Read-only MCP session/research tools (`mcp serve`, `mcp tools`)
- [x] Live CANsub.2 MCP research controls (passive observation, capture, events, comparison)
- [x] Proprietary signal research primitives (candidate evidence, repeat consistency, correlation)
- [x] Research candidate persistence, review/confirm/reject workflow (CLI)
- [x] Asset research DBC generation (`<asset>_research.dbc`, confirmed signals only)
- [x] Read-only MCP candidate tools + research DBC preview (no MCP confirmation)
- [x] MCP analysis tools (`list_session_events`, `preview_candidate_values`)
- [x] Streamable HTTP MCP transport (`mcp serve --transport streamable-http` → `/mcp`)
- [x] HTTP MCP verifier (`scripts/mcp_verify_http.py`)
- [x] MCP instance identification (`get_instance_info`)
- [x] Multi-instance deployment documentation
- [x] J1939 29-bit identifier parsing
- [x] Import reference PGN/SPN data from user-owned J1939 PDF
- [x] Import ISOBUS DDI data from user-owned PDF
- [x] Windows-first CLI with `uv` workflow
- [x] **Office ChatGPT MCP connector** — live, 32 tools, end-to-end validated
- [x] **CAN Signal Research Skill** — installed in ChatGPT on Office (`can-signal-research`)
- [x] **First passive AI-guided proprietary signal trial** — Office bench, CANsub channel 1
  (15 s / 171 frames / 5 proprietary IDs; passive inferences without hardware manipulation;
  asset-scoped DBC workflow not yet exercised — see [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md))

Verified desk baseline: firmware **02.04.00**, API **04.00**. USB host
`7413f810-usb.local`; Ethernet bench used `192.168.50.39` during testing (not a
permanent address). See [CANSUB_CONNECTION.md](CANSUB_CONNECTION.md).

This is an **early bench validation** of the AI-guided direction — not a finished
autonomous reverse-engineering product.

## Next milestone: asset-scoped guided research trial

Move from a generic bench stream toward the **full intended workflow**:

1. Register / define an asset on the Office installation
2. Associate a capture session with that asset
3. Apply reference-backed standard knowledge (`<asset>_standard.dbc` path)
4. Apply confirmed research knowledge (`<asset>_research.dbc` / candidates)
5. Identify unknown proprietary remainder
6. Use the **can-signal-research** Skill for **passive-first** inference
7. Request a controlled physical experiment **only if** ambiguity remains material
8. Propose a research candidate (CLI add after agent proposal)
9. Confirm via existing CLI workflow (`research candidate review/confirm`)

The first passive trial had **no registered assets** in the Office database, so steps
1–5 and the standard/research DBC baseline were not validated live yet.

Design reference: [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md),
[skills/can-signal-research/SKILL.md](../skills/can-signal-research/SKILL.md).

## In scope (remaining V1)

- [ ] CANsub.2 device discovery (USB + Ethernet scan)
- [ ] Import reference PGN/SPN data from user-provided DBC files (`reference import-dbc` — scaffold only today)

## Explicitly out of scope (V1)

| Item | Reason |
|------|--------|
| GUI / desktop app | CLI-first; defer until core workflows are stable |
| PEAK, Kvaser, Vector, or other adapters | CANsub.2-only for V1 |
| Automated CAN transmission | Research/analysis tool, not a bus simulator |
| NVRAM / ECU programming | Out of scope; legal and safety concerns |
| Autonomous proprietary decoding | Human-in-the-loop + AI-assisted, not black-box decode |
| Automatic research DBC writes | Research DBC only from explicitly confirmed candidates via CLI |
| Cloud sync | Local-first; no account infrastructure in V1 |
| Central MCP routing / multi-laptop shared backend | Each installation is independent; may revisit later |
| Community data sharing | Licensed data stays private per user |
| Bundled SAE J1939 / ISO 11783 database | Copyright; user imports their own licensed sources |
| Raw frames in SQLite | Volume concern on busy J1939 buses; use external store |

## Success criteria

1. Capture a session from CANsub.2 with real bus traffic and persist metadata + frames externally
2. Classify captured frames against the local J1939/ISOBUS reference catalogue
3. List and summarize sessions from CLI and MCP (32 tools including `get_instance_info`)
4. Look up PGNs/SPNs from imported PDF reference data locally (DBC file import remains future work)
5. Generate a draft tractor DBC from session observations (`<asset>_standard.dbc`)
6. All tests pass; CLI and MCP modules import cleanly on Windows

## Post-V1 candidates (not committed)

- Additional adapter backends
- Parquet frame store with DuckDB analysis
- DBC diff and merge tooling
- User-provided DBC reference import (complete `reference import-dbc`)
- Optional cloud backup (user-controlled)
