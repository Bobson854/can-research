# V1 scope

## Completed (desk bench testing — no CAN bus yet)

- [x] CANsub.2 direct REST connection (configured hostname)
- [x] Persistent local host config (`data/config.toml`)
- [x] Read-only channel status (channels 1 and 2)
- [x] WebSocket RX (idle verified; zero frames expected without bus)
- [x] Live capture with session metadata in SQLite
- [x] JSONL `CaptureStore` for raw frames (`data/sessions/`)
- [x] J1939 29-bit identifier parsing
- [x] Import reference PGN/SPN data from user-owned J1939 PDF
- [x] Import ISOBUS DDI data from user-owned PDF
- [x] Windows-first CLI with `uv` workflow

Verified desk baseline: firmware **02.04.00**, API **04.00**, host
`7413f810-usb.local`. See [CANSUB_CONNECTION.md](CANSUB_CONNECTION.md).

## In scope (remaining V1)

- [ ] Real CAN bus capture (non-zero frames)
- [ ] Offline J1939/ISOBUS classification of saved sessions
- [ ] Build base machine/tractor DBC from capture session observations
- [ ] Session summary (observed PGNs, source addresses, rates)
- [ ] Basic correlation analysis and findings storage
- [ ] MCP server exposing sessions, references, and DBC tools
- [ ] CANsub.2 device discovery (USB + Ethernet scan)
- [ ] Import reference PGN/SPN data from user-provided DBC files

## Explicitly out of scope (V1)

| Item | Reason |
|------|--------|
| GUI / desktop app | CLI-first; defer until core workflows are stable |
| PEAK, Kvaser, Vector, or other adapters | CANsub.2-only for V1 |
| Automated CAN transmission | Research/analysis tool, not a bus simulator |
| NVRAM / ECU programming | Out of scope; legal and safety concerns |
| Autonomous proprietary decoding | Human-in-the-loop + AI-assisted, not black-box decode |
| Cloud sync | Local-first; no account infrastructure in V1 |
| Community data sharing | Licensed data stays private per user |
| Bundled SAE J1939 / ISO 11783 database | Copyright; user imports their own licensed sources |
| Raw frames in SQLite | Volume concern on busy J1939 buses; use external store |

## Success criteria

1. Capture a session from CANsub.2 with real bus traffic and persist metadata + frames externally
2. Classify captured frames against the local J1939/ISOBUS reference catalogue
3. List and summarize sessions from CLI and MCP
4. Import a reference DBC and look up PGNs/SPNs locally
5. Generate a draft tractor DBC from session observations
6. All tests pass; CLI and MCP modules import cleanly on Windows

## Post-V1 candidates (not committed)

- Additional adapter backends
- Parquet frame store with DuckDB analysis
- DBC diff and merge tooling
- HTTP/SSE MCP transport
- Optional cloud backup (user-controlled)
