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

**Next major milestone:** Live CANsub.2 MCP research controls.

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

Repository/development examples use `uv run canresearch ...`, which runs the CLI
inside the project's uv-managed environment. A bare `canresearch ...` command only
works if the package has separately been installed so its console script is
available on PATH.

## CLI commands

```text
uv run canresearch --help
uv run canresearch config show
uv run canresearch device info
uv run canresearch device channel-info <channel>
uv run canresearch device rx <channel>
uv run canresearch capture start --channel <n>
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
uv run canresearch session dbc <session-id> --asset <asset-key> [--source-address 0x00]
uv run canresearch reference import-j1939 ...
uv run canresearch mcp serve
uv run canresearch mcp tools
```

### MCP (read-only)

The MCP server exposes **read-only** tools for stored sessions, reference lookups,
transport inspection, J1939 node identity, and in-memory DBC preview. It does not
control live capture, mutate assets, or write DBC files.

Suggested agent workflow:

1. `list_sessions` → `get_session`
2. `analyze_session` → `list_session_nodes`
3. `lookup_pgn` / `lookup_spn`
4. `decode_session` → `inspect_transport` (if needed)
5. `get_asset` / `list_asset_nodes`
6. `build_session_dbc_preview`

Responses are bounded (default limits on decode rows, observed traffic, DBC preview
lines). Live CANsub.2 MCP controls are planned for a later milestone.

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
