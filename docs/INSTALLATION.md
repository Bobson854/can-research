# Installation

Software installation for CAN Research on Windows.

**Two supported paths:**

| Path | Audience | Start here |
|------|----------|------------|
| **Release ZIP** | Ordinary Windows users | Extract ZIP → `setup.cmd` |
| **Git + uv** | Developers / contributors | Clone → `uv sync` |

You do **not** need Git, Cursor, or an IDE for normal CAN Research use.

After install, connect AI: [AI_INTEGRATION.md](AI_INTEGRATION.md) · CANsub: [CANSUB_SETUP.md](CANSUB_SETUP.md)

---

## Windows prerequisites

| Requirement | Notes |
|-------------|--------|
| **Windows 10/11** | Primary supported platform |
| **[uv](https://docs.astral.sh/uv/)** | Required — manages Python and dependencies |
| **Python 3.11+** | Installed automatically by uv on first sync if missing |
| **CANsub.2** | Optional at install time; required for live CAN work |
| **Git** | **Developers only** — not required for release ZIP install |

CAN Research does **not** install uv or Python for you inside `setup.cmd`. If `uv` is missing,
`setup.cmd` prints a clear message with the official install link.

Linux/macOS may work for development where dependencies are available; the validated
end-user path is **Windows + CANsub.2**.

---

## Release ZIP installation (recommended for users)

Download the latest **`CAN-Research-v<version>-windows.zip`** from
[GitHub Releases](https://github.com/Bobson854/can-research/releases) (when published)
or use a ZIP built locally — [RELEASING.md](RELEASING.md).

### 1. Prerequisites

Install **[uv](https://docs.astral.sh/uv/)** once per machine (CAN Research does not
bundle uv). Windows PowerShell:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Open a **new** terminal after installing uv.

### 2. Extract

Extract to a permanent folder, for example:

```text
C:\CAN Research\CAN-Research-v<version>\
```

The ZIP contains a single top-level folder `CAN-Research-v<version>\`. Open it and read
**`README-FIRST.txt`**.

Recommended location: a dedicated folder under `C:\CAN Research\` — not inside Downloads
long-term (captures and reference data will grow under `data\`).

### 3. Run setup

Double-click **`setup.cmd`** or from Command Prompt:

```cmd
cd /d "C:\CAN Research\CAN-Research-v<version>"
setup.cmd
```

Replace the path with your extracted folder name.

### 4. Configure (first run)

Edit `data\config.toml`:

```toml
[instance]
instance_key = "workshop"
display_name = "CAN Research - Workshop"

[cansub]
host = "your-device-id-usb.local"
```

Or use CLI after setup:

```powershell
uv run canresearch config set-instance --key workshop --name "CAN Research - Workshop"
uv run canresearch config set-host your-device-id-usb.local
```

### 5. Start CAN Research

Run **`start-can-research.cmd`** — starts local MCP and the OpenAI tunnel (if not already running). MCP listens at:

```text
http://127.0.0.1:8765/mcp
```

Leave any started service windows open while using AI. Health check: **`status.cmd`**

### 6. Connect AI and install bundled Skills

[AI_INTEGRATION.md](AI_INTEGRATION.md) · Install pre-built Skills from **`skills\dist\`**
— [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) · [USER_ONBOARDING.md](USER_ONBOARDING.md)

ChatGPT tunnel setup (if used): [MCP_SETUP.md](MCP_SETUP.md) — not included in the ZIP.

---

## Developer installation (Git + uv)

For contributors and anyone working from source control.

### 1. Clone and sync

```powershell
git clone <your-repo-url> can-research
cd can-research
uv sync
```

All CLI examples use:

```powershell
uv run canresearch ...
```

### 2. Configuration

Same as release path — copy `config.toml.example` to `data\config.toml` or run `setup.cmd`
(which performs the same config bootstrap).

### 3. Verify

```powershell
uv run canresearch --help
uv run canresearch config show
uv run pytest
```

Developers start MCP directly or use `start-can-research.cmd`:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

---

## Install directory layout

After setup, expect:

```text
can-research/                 ← install root (extract or clone)
  setup.cmd
  start-can-research.cmd
  status.cmd
  README-FIRST.txt
  data/                       ← local only (gitignored in dev clones)
    config.toml
    references/
    sessions/
    reference_sources/
  docs/
  skills/
  src/
  config.toml.example
```

Local data defaults under `data/` unless overridden in config.

Override data root:

```powershell
uv run canresearch config set-data-dir D:\CANResearch\workshop-data
```

| Purpose | Default path |
|---------|----------------|
| Config | `data/config.toml` |
| SQLite metadata + references | `data/references/canresearch.db` |
| Capture frames (JSONL) | `data/sessions/<session-id>/frames.jsonl` |
| Reference source registry | `data/reference_sources/` |

`data/` must not be committed — machine-specific and may contain private reference material.

Multi-instance examples: `config/examples/workshop.toml.example`, `config/examples/travel.toml.example`

---

## Upgrading

### Release ZIP install

1. Stop MCP (close `start-can-research.cmd` window)
2. Extract the new **`CAN-Research-v<version>-windows.zip`**
3. **Copy your existing `data\` folder** into the new install directory (preserves config,
   captures, reference sources, and SQLite catalogues)
4. Run **`setup.cmd`** in the new folder
5. Run **`status.cmd`**
6. Reinstall ChatGPT Skills from `skills\dist\` if release notes say to

Do **not** overwrite `data\` with an empty folder from an old install backup unless
intentional.

### Developer install

```powershell
git pull
uv sync
uv run pytest
```

Restart MCP after upgrade.

---

## Uninstall / removal

CAN Research is **portable** — no system-wide installer.

To remove:

1. Stop MCP (`start-can-research.cmd` window)
2. Delete the install folder (e.g. `C:\CAN Research\can-research`)
3. Remove ChatGPT connector / tunnel profile / Skills in ChatGPT manually if configured
4. Optionally delete `%USERPROFILE%\.local\bin\uv` only if you installed uv solely for CAN Research

Your **`data\`** folder contains all local research data — back it up before deletion if needed.

---

## Next steps

| Step | Document |
|------|----------|
| Connect CANsub.2 | [CANSUB_SETUP.md](CANSUB_SETUP.md) |
| Connect AI frontend | [AI_INTEGRATION.md](AI_INTEGRATION.md) |
| Install ChatGPT Skills | [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) |
| End-to-end onboarding | [USER_ONBOARDING.md](USER_ONBOARDING.md) |
| ChatGPT tunnel (if used) | [MCP_SETUP.md](MCP_SETUP.md) |
| Multiple machines | [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) |
| Problems | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

---

## Architecture (reference)

```text
CAN bus → CANsub.2 → CAN Research core → MCP → AI client (+ Skills where supported)
```

MCP tool count: verify with `uv run canresearch mcp tools` (baseline 41).

---

## Future: active / TX research

Current live MCP tools are **passive RX only**. Future TX/probing would be a separate
capability with its own safety model — not part of this installation path.
