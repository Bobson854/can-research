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
uv run pytest tests/test_release_build.py -q
```

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

**Trigger:** push a version tag matching `v*` (e.g. `v0.1.0`)

**Steps:** checkout → install uv → `build-release.ps1` → pytest validation → upload
`dist/releases/CAN-Research-v*-windows.zip` to GitHub Release.

Tag naming should match `pyproject.toml` version (`v0.1.0` ↔ `version = "0.1.0"`).

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
| `scripts/` | `mcp_verify_http.py`, `package_skill.py` only |
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
- `scripts/build_release.py`, `scripts/build-release.ps1` (maintainer-only)
- OpenAI tunnel client (ChatGPT-specific — see [MCP_SETUP.md](MCP_SETUP.md))
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
