# Installation

General installation guide for CAN Research on a new machine.

**Validated path:** Windows-first (desk and bench testing). Linux and macOS may work for
development where dependencies are available, but the primary supported workflow today is
Windows + CANsub.2 + `uv`.

## Architecture (three layers)

```text
CAN bus
   ↓
CANsub.2
   ↓
CAN Research core          ← deterministic capture, parsing, reference lookup, evidence
   ↓
MCP (41 tools — verify with `mcp tools`)  ← bounded access to core capabilities
   ↓
ChatGPT / Codex / other MCP client
   ↓
CAN Research Skills (onboarding, reference-builder, signal-research)
```

Repo source is **canonical**. Installed ChatGPT Skills, tunnel profiles, and connector
configuration are **deployment artifacts** on each machine.

## Requirements

| Item | Notes |
|------|--------|
| Python | 3.11+ |
| [uv](https://docs.astral.sh/uv/) | Environment and dependency management |
| Git | Clone this repository |
| CANsub.2 | Optional at install time; required for live CAN work |

## 1. Clone and install dependencies

```powershell
git clone <your-repo-url> can-research
cd can-research
uv sync
```

All CLI examples in this project use:

```powershell
uv run canresearch ...
```

A bare `canresearch` command only works if the package has been separately installed
on `PATH` — not required for normal use.

## 2. Verify the CLI

```powershell
uv run canresearch --help
uv run canresearch config show
uv run pytest
```

Without a config file, development defaults apply:

```text
instance_key = local
display_name = CAN Research (local)
```

## 3. Create local configuration

Copy the example config and edit for your machine:

```powershell
copy config.toml.example data\config.toml
```

On Linux/macOS:

```bash
mkdir -p data
cp config.toml.example data/config.toml
```

Edit `data/config.toml`:

```toml
[instance]
instance_key = "workshop"
display_name = "CAN Research - Workshop"

[paths]
data_dir = "data"

[cansub]
host = "your-device-id-usb.local"
timeout = 5.0
verify_tls = false
```

Or use the CLI:

```powershell
uv run canresearch config set-instance --key workshop --name "CAN Research - Workshop"
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch config show
```

`data/` is gitignored — do not commit machine-specific settings.

Multi-instance examples: `config/examples/workshop.toml.example`,
`config/examples/travel.toml.example`.

## 4. Local data directory

By default CAN Research stores:

| Purpose | Path |
|---------|------|
| Config | `data/config.toml` |
| SQLite metadata + references | `data/references/canresearch.db` |
| Capture frames (JSONL) | `data/sessions/<session-id>/frames.jsonl` |

Override the root:

```powershell
uv run canresearch config set-data-dir D:\CANResearch\workshop-data
```

## 5. Next steps

| Step | Document |
|------|----------|
| Connect CANsub.2 | [CANSUB_SETUP.md](CANSUB_SETUP.md) |
| Add your CAN knowledge | [REFERENCE_DATA.md](REFERENCE_DATA.md) · [USER_ONBOARDING.md](USER_ONBOARDING.md) |
| Start MCP + ChatGPT connector | [MCP_SETUP.md](MCP_SETUP.md) |
| Install CAN Signal Research Skill | [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) |
| Provide J1939/ISOBUS reference data | [REFERENCE_DATA.md](REFERENCE_DATA.md) |
| Multiple laptops / machines | [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) |
| Problems | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

## First-run smoke test

After CANsub is configured:

```powershell
# 1. Start MCP (separate terminal — see MCP_SETUP.md)
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp

# 2. Local checks
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
uv run canresearch device info
uv run canresearch device channel-info 1
```

In ChatGPT (with MCP connected), run the live preflight sequence:

```text
get_instance_info
get_cansub_device_status
get_cansub_channel_status
observe_live_traffic
```

Confirm frames are present before starting research capture. This aligns with the
[CAN Signal Research Skill](../skills/can-signal-research/SKILL.md) V2 preflight.

## 6. Reference onboarding (second laptop)

After install, follow the **laptop smoke test** in [USER_ONBOARDING.md](USER_ONBOARDING.md)
(register private PDF → validate/import bundle → MCP verify). Bundle format:
[REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md).

## Future: active / TX research

Current CAN Research live tools are **passive RX only** — no CAN transmission through MCP.

Future active probing / TX research would be a **separate capability set** with its own
safety model, likely a separate Skill and possibly a separate application module sharing
common core code. It is **not** part of the current installation path.
