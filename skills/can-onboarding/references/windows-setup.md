# Windows setup

## Requirements

- Python 3.11+
- `uv`
- Git
- CANsub.2 only required for live work

## Fresh clone

```powershell
git clone <repo-url> can-research
cd can-research
uv sync
uv run canresearch --help
uv run canresearch config show
```

All project commands should use `uv run canresearch ...`.

## Local config

```powershell
copy config.toml.example data\config.toml
```

Example:

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

Or:

```powershell
uv run canresearch config set-instance --key workshop --name "CAN Research - Workshop"
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch config show
```

`data/` is local and gitignored.

## Shell distinction

PowerShell can change drives with ordinary `cd`.

Command Prompt needs `/d` when changing drives:

```cmd
cd /d K:\path\to\directory
```

Never give CMD `/d` syntax as PowerShell syntax.

## Local storage

Typical default paths:

- config: `data/config.toml`
- SQLite/reference DB: `data/references/canresearch.db`
- sessions: `data/sessions/<session-id>/frames.jsonl`
- reference source registry: `data/reference_sources/`
- DBC library: `data/dbc/`

Data root can be overridden with:

```powershell
uv run canresearch config set-data-dir D:\CANResearch\workshop-data
```
