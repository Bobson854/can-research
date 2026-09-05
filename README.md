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

**Next major milestone:** MCP session/DBC tools and live CANsub.2 research workflows.

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
canresearch session nodes <session-id> [--refresh] [--source-address 0x80] [--show-raw]
canresearch asset add --key <key> --type tractor --name "..."
canresearch asset list
canresearch asset show <asset-key>
canresearch asset node add <asset-key> <j1939-name>
canresearch asset node list <asset-key>
canresearch asset node remove <asset-key> <j1939-name>
canresearch session asset add <session-id> <asset-key> --role tractor
canresearch session asset list <session-id>
canresearch session dbc <session-id> --asset <asset-key> [--source-address 0x00]
canresearch reference import-j1939 ...
canresearch mcp serve
```

### Agricultural workflow example

```powershell
# Discover ECUs from Address Claim traffic
uv run canresearch session nodes abc123

# Link observed J1939 NAMEs to assets
uv run canresearch asset node add jd_6155r_01 0xAABBCCDDEEFF0011
uv run canresearch asset node add weedit_quadro_01 0x1122334455667788

# Generate asset-specific DBCs (source addresses resolved from linked nodes)
uv run canresearch session dbc abc123 --asset jd_6155r_01
uv run canresearch session dbc abc123 --asset weedit_quadro_01

# Manual override when needed
uv run canresearch session dbc abc123 --asset jd_6155r_01 --source-address 0x00
```

Asset-specific DBC generation resolves source addresses from J1939 NAMEs linked to
the asset when `--source-address` is not supplied. If no linked nodes are observed
in the session, the command fails with a clear message rather than including all
session traffic.

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
