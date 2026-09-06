# CAN Research Skills — installation

Install and update CAN Research **ChatGPT Skills**. MCP connection and frontend setup:
[AI_INTEGRATION.md](AI_INTEGRATION.md) — not duplicated here.

## Canonical source vs deployment package

The repository stores **Skill source only**. Generated `skill.zip` files are local deployment artifacts and are gitignored.

```text
repo Skill source
  → package locally (developers) or use release-provided archives
  → upload skill.zip to ChatGPT
  → installed Skill
```

Keep Skill names stable; do not create `v2` / `v3` copies in ChatGPT.

Current Skills:

| Skill | Purpose |
|------|---------|
| `can-onboarding` | Fresh-machine setup, CANsub, MCP verification, reference checks, smoke tests |
| `can-reference-builder` | Convert user-owned CAN manuals/tables into Reference Bundle V1 JSON |
| `can-signal-research` | Known-first proprietary CAN signal research |

## Build skill.zip locally (developers / maintainers)

From the repository root:

```powershell
uv run python scripts/package_skill.py skills/can-onboarding
uv run python scripts/package_skill.py skills/can-reference-builder
uv run python scripts/package_skill.py skills/can-signal-research
```

Or all three:

```powershell
uv run python scripts/package_skill.py skills/can-onboarding skills/can-reference-builder skills/can-signal-research
```

Each command writes `skills/<skill-name>/skill.zip`. Release ZIPs may include pre-built archives — check your release notes.

## Install in ChatGPT

1. Obtain `skill.zip` (build locally or from release).
2. Open ChatGPT **Skills** (`/skills`).
3. Upload **one `skill.zip` at a time**.
4. Do not manually unzip before upload.
5. Enable the Skill as required by the UI.

For an update, replace/reinstall using a newly built archive.

## Recommended install order

```text
1. CAN Research installed (setup.cmd) and MCP running (start-can-research.cmd)
2. ChatGPT MCP connector connected — AI_INTEGRATION.md
3. can-onboarding
4. can-reference-builder (when reference material exists)
5. can-signal-research (before proprietary research)
```

Start **can-onboarding** after MCP is connected. Parallel human path: [USER_ONBOARDING.md](USER_ONBOARDING.md).

## Verification after install

### `can-onboarding`

Ask it to continue setup from the current machine state. It should verify rather than assume.

### `can-reference-builder`

Provide a user-owned document and registered `source_key`. Output should match Reference Bundle V1; hand off to [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md).

### `can-signal-research`

With MCP attached: confirm `get_instance_info`, run live preflight, inventory known references/DBCs before experiments.

## Update workflow

```text
edit skills/<name>/ source
  → uv run python scripts/package_skill.py skills/<name>
  → replace installed Skill in ChatGPT
```

## Private/reference material

Do not bundle SAE/ISO/OEM licensed source documents into Skills.

## Related

- [AI_INTEGRATION.md](AI_INTEGRATION.md) — MCP + frontend connection (ChatGPT primary)
- [INSTALLATION.md](INSTALLATION.md) — software install
- [USER_ONBOARDING.md](USER_ONBOARDING.md) — end-to-end path
- [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) — reference bundle workflow
