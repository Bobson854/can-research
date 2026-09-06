# CAN Research Skills — installation

Install and update the CAN Research Skills in ChatGPT (or compatible hosts).

## Canonical source vs deployment package

The repository stores **Skill source only**. Generated `skill.zip` files are local deployment artifacts and are gitignored.

```text
repo Skill source
  → package locally
  → upload skill.zip to ChatGPT
  → installed Skill
```

Git history is the version history. Keep Skill names stable; do not create `v2` / `v3` copies in ChatGPT.

Current Skills:

| Skill | Purpose |
|------|---------|
| `can-onboarding` | Fresh-machine setup, CANsub, MCP, Skills, reference onboarding, smoke tests |
| `can-reference-builder` | Convert user-owned CAN manuals/tables into Reference Bundle V1 JSON |
| `can-signal-research` | Known-first proprietary CAN signal research |

## Build skill.zip locally

From the repository root, use the repo packaging script:

```powershell
uv run python scripts/package_skill.py skills/can-onboarding
uv run python scripts/package_skill.py skills/can-reference-builder
uv run python scripts/package_skill.py skills/can-signal-research
```

Or build all three in one command:

```powershell
uv run python scripts/package_skill.py skills/can-onboarding skills/can-reference-builder skills/can-signal-research
```

Each command writes:

```text
skills/<skill-name>/skill.zip
```

The script:

- verifies `SKILL.md` exists
- verifies `agents/openai.yaml` exists
- checks the Skill directory name matches frontmatter `name`
- packages exactly one top-level Skill folder
- excludes generated/local hidden files
- runs ZIP CRC/integrity validation
- checks required archive members
- enforces the 25 MiB upload limit
- prints SHA-256 for the finished archive

`skill.zip` is ignored by Git. If it disappears after a fresh clone, rebuild it locally; that is expected.

## Install in ChatGPT

1. Build the required `skill.zip` locally.
2. Open ChatGPT **Skills** (`/skills`).
3. Upload **one `skill.zip` at a time**.
4. Do not manually unzip it first.
5. Enable the Skill as required by the UI.

For an update, replace/reinstall the existing Skill using a newly built archive.

## Fresh laptop recommended order

```text
1. git clone / git pull
2. uv sync
3. build can-onboarding skill.zip
4. install can-onboarding
5. follow onboarding flow
6. build/install can-reference-builder when reference material is ready
7. build/install can-signal-research before research
```

## Verification after install

### `can-onboarding`

Ask it to continue setup from the current machine state. It should verify rather than assume and should distinguish PowerShell vs CMD where relevant.

### `can-reference-builder`

Give it a user-owned CAN reference document and a registered `source_key`. It should
produce Reference Bundle V1-compatible structured output while preserving provenance and
uncertainty, then hand off to the workflow in [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md).

### `can-signal-research`

With the CAN Research MCP connector attached, it should confirm backend identity, run live preflight, inventory known references/DBCs first, and isolate the proprietary remainder before experiments.

## MCP version check

Do not treat a historical tool count in documentation as permanent. Verify the current local registry with:

```powershell
uv run canresearch mcp tools
```

Then confirm the ChatGPT connector exposes the same intended surface.

## Update workflow

```text
observed weakness / new capability
  ↓
edit canonical source under skills/<name>/
  ↓
review references and SKILL.md
  ↓
package locally with scripts/package_skill.py
  ↓
ZIP integrity check passes
  ↓
replace installed Skill in ChatGPT
  ↓
benchmark again
```

## Private/reference material

Do not bundle SAE/ISO/OEM licensed source documents into Skills. Skills may contain public instructions/schema snapshots, but private/licensed originals stay in the configured local CAN Research reference-source area.

## Related

- [INSTALLATION.md](INSTALLATION.md) — clone, uv, config
- [MCP_SETUP.md](MCP_SETUP.md) — MCP + tunnel + connector
- [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) — manual → bundle operator workflow
- [REFERENCE_DATA.md](REFERENCE_DATA.md) — reference-source and bundle model
- [USER_ONBOARDING.md](USER_ONBOARDING.md) — end-to-end new-user path
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — connector and channel issues
- [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) — independent installations
