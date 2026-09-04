# can-research

Windows-first, CLI-first CAN research tool focused on **CSS Electronics CANsub.2** hardware, **J1939/ISOBUS** reference handling, capture/session analysis, machine-specific DBC generation, and an **MCP server** for AI-assisted interrogation (ChatGPT, Claude, etc.).

## V1 goal

1. **Build or import** a parsed local PGN/SPN reference database (from user-owned sources).
2. **Build a base tractor DBC** from a CANsub.2 logging session.
3. **Expose** sessions, reference lookups, correlation analysis, and DBC refinement through MCP.

No GUI in V1. No bundled SAE J1939 database.

## Features (scaffold / planned)

| Area | Description |
|------|-------------|
| Hardware | CANsub.2 via USB or Ethernet |
| Protocol | J1939/ISOBUS 29-bit identifier parsing and reference catalogue |
| DBC | Import reference DBCs; generate machine-specific DBC from sessions |
| Capture | Session metadata + pluggable raw-frame storage (not SQLite blobs) |
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
uv run canresearch --help
uv run pytest
```

## CLI commands

```text
canresearch --help
canresearch device list
canresearch capture start
canresearch capture stop
canresearch session list
canresearch session summary
canresearch dbc build
canresearch reference import-dbc
canresearch mcp serve
```

## Project layout

```text
src/canresearch/
  cli.py              CLI entry point
  core/               J1939, DBC, references, sessions, analysis
  cansub/             CANsub.2 discovery, API, capture
  mcp/                MCP server
  storage/            SQLite metadata and migrations
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/V1_SCOPE.md](docs/V1_SCOPE.md).

## License

MIT — see [LICENSE](LICENSE).
