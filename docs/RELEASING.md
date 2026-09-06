# Releasing CAN Research

Maintainer guide for building and publishing Windows release ZIPs.

End-user install: [INSTALLATION.md](INSTALLATION.md) · First-run cheat sheet: `README-FIRST.txt`

---

## Version source

**Single source of truth:** `pyproject.toml` → `[project].version`

Release artifact names derive from this version only:

```text
CAN-Research-v<version>-windows.zip
  └── CAN-Research-v<version>/
```

Do not maintain a separate version file.

---

## Local release build

From repository root (requires **uv** on PATH):

```powershell
./scripts/build-release.ps1
```

Equivalent:

```powershell
uv run python scripts/build_release.py
```

Options:

```powershell
uv run python scripts/build_release.py --output-dir dist/releases --keep-staging
```

Output:

```text
dist/releases/CAN-Research-v<version>-windows.zip
```

Staging (optional inspection): `dist/release-staging/CAN-Research-v<version>/`

The build script:

1. Validates required source files exist
2. Stages a clean runtime tree
3. Packages all three Skills into `skills/dist/*.skill.zip`
4. Creates the versioned ZIP with a top-level folder
5. Validates ZIP contents and Skill package integrity

It does **not** modify your local `data/` or `data/config.toml`.

---

## Recommended publish path (semi-automatic)

From **`main`** with a **clean working tree** and **CAN Research MCP stopped**:

```powershell
./scripts/publish-release.ps1 -Version X.Y.Z
```

From Command Prompt:

```cmd
powershell -ExecutionPolicy Bypass -File .\scripts\publish-release.ps1 -Version X.Y.Z
```

Preview without committing, tagging, or pushing:

```powershell
./scripts/publish-release.ps1 -Version X.Y.Z -DryRun
```

From Command Prompt:

```cmd
powershell -ExecutionPolicy Bypass -File .\scripts\publish-release.ps1 -Version X.Y.Z -DryRun
```

The script:

1. Verifies **git** and **uv** are on PATH
2. **Refuses if `canresearch.exe` is running** — checked **before** any version bump or `uv.lock` change. Stop MCP / close `start-can-research.cmd` windows first. A running CAN Research server can hold files or process state during release work; aborting early avoids partial release edits.
3. Validates semver format
4. Requires branch **`main`**
5. Requires a **clean working tree** (or `-AllowDirty`)
6. Fetches **`origin`** and refuses if local `main` is behind **`origin/main`**
7. Refuses if tag **`vX.Y.Z`** already exists locally or on **`origin`**
8. Refuses if **`pyproject.toml`** already equals the requested version
9. Updates **`[project].version`** in `pyproject.toml` only
10. Runs **`uv lock`**
11. Runs **`./scripts/build-release.ps1`**
12. Runs **`uv run pytest tests/test_release_build.py -q`**
13. Verifies **`dist/releases/CAN-Research-vX.Y.Z-windows.zip`** exists
14. Shows a release summary and requires **Enter** before irreversible Git operations
15. Commits **`Release vX.Y.Z`**, creates annotated tag **`vX.Y.Z`**, pushes **`main`** and the tag

**Tag ↔ version must match:**

```toml
version = "X.Y.Z"
```

```text
git tag vX.Y.Z
```

Pushing `v*` triggers GitHub Actions (see below). The script does **not** call the GitHub API or embed tokens.

Override dirty tree (emergency only): `-AllowDirty`

Office quick reference: [Commands_Register.md](Commands_Register.md)

---

## Manual publish path

1. Stop CAN Research MCP (`canresearch.exe` / `start-can-research.cmd` windows)
2. Edit `[project].version` in `pyproject.toml`
3. Run `uv lock` if the lockfile needs refreshing
4. `./scripts/build-release.ps1`
5. `uv run pytest tests/test_release_build.py -q`
6. Commit: `Release vX.Y.Z`
7. Annotated tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
8. `git push origin main`
9. `git push origin vX.Y.Z`

GitHub Actions publishes the Release asset when the tag arrives.

---

## Skill packaging

Skills are built with `scripts/package_skill.py` during release staging.

Release filenames:

```text
skills/dist/can-onboarding.skill.zip
skills/dist/can-reference-builder.skill.zip
skills/dist/can-signal-research.skill.zip
```

Each inner archive contains `{skill-name}/SKILL.md`, `agents/openai.yaml`, and references.

---

## Validation

Automated:

```powershell
uv run pytest tests/test_publish_release.py tests/test_release_build.py -q
```

The publish tests include a Windows PowerShell parser check when `powershell.exe` is available, and require `publish-release.ps1` to remain ASCII-safe.

Manual checklist before publishing:

- [ ] Extract ZIP to a temp folder
- [ ] Run `setup.cmd` on a machine **without** an existing dev checkout
- [ ] Run `start-can-research.cmd` and `status.cmd`
- [ ] Upload each `skills/dist/*.skill.zip` to ChatGPT
- [ ] Run can-onboarding smoke test

Built-in release validation rejects ZIPs containing:

- `tests/`, `.git/`, `.venv/`, `__pycache__/`
- `data/config.toml`, `docs/original_docs/`, `references/private/`

And requires root runtime files, core docs, and all three Skill packages.

---

## GitHub Release workflow

File: `.github/workflows/release.yml`

**Trigger:** push a version tag matching `v*` (e.g. `vX.Y.Z`)

**Steps:** checkout → install uv → `uv sync --extra dev` → `build-release.ps1` → verify artifact →
`pytest tests/test_release_build.py` → upload `dist/releases/CAN-Research-v*-windows.zip` to GitHub Release.

Tag naming must match `pyproject.toml` version (`vX.Y.Z` ↔ `version = "X.Y.Z"`).

Maintainer entry point: `./scripts/publish-release.ps1 -Version X.Y.Z` (see above).

You can build and publish manually without GitHub Actions by running the local build
and attaching the ZIP to a release yourself.

---

## Files included in the Windows release

**Root:** `README-FIRST.txt`, `README.md`, `LICENSE`, `setup.cmd`, `start-can-research.cmd`,
`status.cmd`, `pyproject.toml`, `uv.lock`, `config.toml.example`

**Directories:**

| Path | Purpose |
|------|---------|
| `src/` | CAN Research application source |
| `docs/` | User and operator documentation |
| `skills/` | Skill source + `skills/dist/*.skill.zip` |
| `scripts/` | `mcp_verify_http.py`, `package_skill.py`, `tunnel_windows.py` |
| `schemas/` | Reference bundle JSON schema |
| `config/examples/` | Multi-instance config examples |

---

## Deliberately excluded

- `.git/`, `.github/`
- `tests/`, development tooling configs
- `.venv/`, `__pycache__/`, pytest/ruff caches
- `data/` (runtime — created by `setup.cmd`)
- `dist/` from developer builds (release output is rebuilt fresh)
- `docs/original_docs/`, licensed/private reference material
- `scripts/build_release.py`, `scripts/build-release.ps1`, `scripts/publish_release.py`, `scripts/publish-release.ps1` (maintainer-only)
- OpenAI **`tunnel-client.exe`** binary (not bundled — installed to `%LOCALAPPDATA%\CAN Research\tunnel-client\` via `setup.cmd`; see [MCP_SETUP.md](MCP_SETUP.md)). **`scripts/tunnel_windows.py` is included** in the release ZIP as a runtime helper.
- Pre-built `skills/*/skill.zip` dev artifacts (release uses `skills/dist/` only)

---

## Upgrade path for ZIP users

1. Stop MCP (`start-can-research.cmd` window)
2. Extract new release **or** copy new files over install folder
3. **Preserve `data\`** (config, captures, reference knowledge)
4. Run `setup.cmd`
5. Run `status.cmd`
6. Reinstall Skills if release notes require it

---

## Remaining manual steps (V1)

- Install **uv** before first `setup.cmd`
- Install **OpenAI tunnel client** for ChatGPT remote MCP ([MCP_SETUP.md](MCP_SETUP.md))
- Configure CANsub.2 hostname in `data/config.toml`
- Upload Skills to ChatGPT manually

No MSI, Windows Service, GUI launcher, or auto-updater in V1.
