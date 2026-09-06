# Office command register

Quick copy/paste commands for the **Office** CAN Research dev checkout.
Canonical user docs: [INSTALLATION.md](INSTALLATION.md) · [MCP_SETUP.md](MCP_SETUP.md) · [RELEASING.md](RELEASING.md)

---

## Normal operation

### Repo root

```cmd
cd /d C:\dev\Can_Research\Can-Research_V1\can-research
```

### One-command AI startup

`start-can-research.cmd` starts **both**:

1. Local MCP (`http://127.0.0.1:8765/mcp`) — in a **CAN Research MCP** window if not already healthy
2. OpenAI tunnel — in an **OpenAI Tunnel** window if not already healthy

The tunnel client lives in the permanent per-user install (default):

```text
%LOCALAPPDATA%\CAN Research\tunnel-client\tunnel-client.exe
```

`setup.cmd` migrates it from Downloads on first run. Do **not** rely on `K:\Downloads\...` paths.

```cmd
start-can-research.cmd
```

After reboot: rerun the command above. **Do not recreate** the ChatGPT connector.

### Status / health

```cmd
status.cmd
```

Checks: uv, config, MCP, OpenAI tunnel health listener, CANsub (if configured).

### MCP verification

```powershell
uv run python scripts/mcp_verify_http.py
```

### MCP tool inventory

```powershell
uv run canresearch mcp tools
```

### Config display

```powershell
uv run canresearch config show
```

### CANsub device check

```powershell
uv run canresearch device info
```

### Tunnel install location / profile

```powershell
uv run python scripts/tunnel_windows.py show
```

---

## Recovery after reboot or failure

1. **Check ports** (MCP **8765**, tunnel health **8081** by default):

   ```powershell
   netstat -ano | findstr ":8765"
   netstat -ano | findstr ":8081"
   ```

2. **Rerun startup** from repo root:

   ```cmd
   start-can-research.cmd
   ```

3. **Run diagnostics**:

   ```cmd
   status.cmd
   ```

4. **Do not recreate** the ChatGPT MCP connector just because Windows rebooted or a terminal closed. Fix MCP/tunnel startup instead — see [MCP_SETUP.md](MCP_SETUP.md).

If `CONTROL_PLANE_API_KEY` was set with `setx`, open a **new** terminal before `start-can-research.cmd`.

---

## Git / development

```powershell
git status
git pull
git fetch origin
git switch main
git pull origin main
git switch -c feature/my-change
git log --oneline -10
```

---

## Tests / validation

### Full test suite

```powershell
uv run pytest
```

### Release-build tests only

```powershell
uv run pytest tests/test_release_build.py -q
```

### Lint (ruff)

```powershell
uv run ruff check src tests
```

### Type check (pyright)

```powershell
uv run pyright
```

Dev dependencies: `uv sync --extra dev`

---

## Release / packaging

**Version source of truth:** `pyproject.toml` → `[project].version` (e.g. `0.1.0` ↔ tag `v0.1.0`)

### Recommended — semi-automatic publish

From repo root on `main`, clean tree:

```powershell
./scripts/publish-release.ps1 -Version 0.1.1
```

Dry run (validate + print Git steps, no commit/tag/push):

```powershell
./scripts/publish-release.ps1 -Version 0.1.1 -DryRun
```

Pushing the `v*` tag triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml) to build and upload the GitHub Release asset.

### Local release build only

```powershell
./scripts/build-release.ps1
```

Equivalent:

```powershell
uv run python scripts/build_release.py
```

Output:

```text
dist/releases/CAN-Research-v<version>-windows.zip
```

Validate:

```powershell
uv run pytest tests/test_release_build.py -q
```

### Manual publish path

See [RELEASING.md](RELEASING.md): edit `pyproject.toml` → build → test → commit → tag `vX.Y.Z` → push commit and tag.
