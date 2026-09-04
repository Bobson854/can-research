# V1 scope

## In scope (V1)

- [ ] CANsub.2 device discovery (USB + Ethernet)
- [ ] Live capture with session metadata in SQLite
- [ ] Pluggable `CaptureStore` for raw frames (format TBD after hardware testing)
- [ ] J1939 29-bit identifier parsing
- [ ] Import reference PGN/SPN data from user-provided DBC files
- [ ] Build base machine/tractor DBC from capture session observations
- [ ] Session summary (observed PGNs, source addresses, rates)
- [ ] Basic correlation analysis and findings storage
- [ ] MCP server exposing sessions, references, and DBC tools
- [ ] Windows-first CLI with `uv` workflow

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

1. Capture a session from CANsub.2 and persist metadata + frames externally
2. List and summarize sessions from CLI and MCP
3. Import a reference DBC and look up PGNs/SPNs locally
4. Generate a draft tractor DBC from session observations
5. All tests pass; CLI and MCP modules import cleanly on Windows

## Post-V1 candidates (not committed)

- Additional adapter backends
- Parquet frame store with DuckDB analysis
- DBC diff and merge tooling
- HTTP/SSE MCP transport
- Optional cloud backup (user-controlled)
