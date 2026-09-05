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

**Next major milestone:** J1939 NAME → asset mapping,
MCP session/DBC tools, and proprietary signal research workflows.

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
| DBC | Import reference DBCs; generate asset-specific DBC from sessions |
| Assets | Registry of tractor/implement/controller devices with session links |
| Capture | Session metadata in SQLite; raw frames in JSONL under `data/sessions/` |
| MCP | Tools for sessions, references, and DBC operations |
| Storage | SQLite for metadata, references, findings, DBC revisions |

## Licensed / private data

**Do not commit** SAE J1939, ISO 11783, or other licensed standards content. Parsed reference data built from your own licensed sources belongs under `references/private/` or `data/` (both gitignored). This repository ships **no** comprehensive J1939/ISOBUS database.

## Requirements

- Windows (primary target; Linux/macOS may work for development)
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- Python 3.11+

## Quick start

```powershell
uv sync
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch device info
uv run pytest
```

## CLI commands

```text
canresearch --help
canresearch config show
canresearch device info
canresearch device channel-info <channel>
canresearch device rx <channel>
canresearch capture start --channel <n>
canresearch session list
canresearch session summary <session-id>
canresearch session analyze <session-id>
canresearch session decode <session-id>
canresearch session tp <session-id>
canresearch asset add --key <key> --type tractor --name "..."
canresearch asset list
canresearch asset show <asset-key>
canresearch session asset add <session-id> <asset-key> --role tractor
canresearch session asset list <session-id>
canresearch session dbc <session-id> --asset <asset-key> [--source-address 0x00]
canresearch reference import-j1939 ...
canresearch mcp serve
```

## Project layout

```text
src/canresearch/
  cli.py              CLI entry point
  core/               J1939, DBC, references, sessions, analysis
  cansub/             CANsub.2 API, WebSocket RX, capture
  mcp/                MCP server
  storage/            SQLite metadata and migrations
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/V1_SCOPE.md](docs/V1_SCOPE.md).

## License

MIT — see [LICENSE](LICENSE).
