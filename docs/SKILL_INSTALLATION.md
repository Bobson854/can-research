# CAN Research Skills — installation

Install and update CAN Research **ChatGPT Skills**. MCP connection:
[AI_INTEGRATION.md](AI_INTEGRATION.md) — not duplicated here.

## Release install (recommended for users)

Windows release ZIPs include **ready-to-upload** Skill packages:

```text
skills/dist/can-onboarding.skill.zip
skills/dist/can-reference-builder.skill.zip
skills/dist/can-signal-research.skill.zip
```

No packaging commands required.

### Install in ChatGPT

1. Complete [INSTALLATION.md](INSTALLATION.md) — `setup.cmd`, `start-can-research.cmd`
2. Connect MCP — [AI_INTEGRATION.md](AI_INTEGRATION.md)
3. Open ChatGPT **Skills** (`/skills`)
4. Upload **one `.skill.zip` at a time** from `skills\dist\`
5. Do not manually unzip before upload
6. Enable each Skill in the UI

### Recommended order

```text
1. can-onboarding.skill.zip
2. can-reference-builder.skill.zip   (when you have reference material)
3. can-signal-research.skill.zip     (before proprietary research)
```

Start **can-onboarding** after MCP is connected. Human-readable path:
[USER_ONBOARDING.md](USER_ONBOARDING.md)

---

## Developer / maintainer packaging

Repository source under `skills/<name>/` is canonical. Build locally when working
from Git:

```powershell
uv run python scripts/package_skill.py skills/can-onboarding
uv run python scripts/package_skill.py skills/can-reference-builder
uv run python scripts/package_skill.py skills/can-signal-research
```

Or build the full Windows release (includes Skill packages):

```powershell
./scripts/build-release.ps1
```

Release maintainer docs: [RELEASING.md](RELEASING.md)

Generated `skills/<name>/skill.zip` and release output under `dist/releases/` are
gitignored local artifacts.

---

## Skill roles

| Skill | Purpose |
|------|---------|
| `can-onboarding` | Setup, CANsub, MCP verification, reference checks, smoke tests |
| `can-reference-builder` | Manuals/tables → Reference Bundle V1 JSON |
| `can-signal-research` | Known-first proprietary CAN signal research |

---

## Verification after install

### `can-onboarding`

Ask it to continue setup from the current machine state. It should verify rather than assume.

### `can-reference-builder`

Provide a user-owned document and registered `source_key`. Hand off to
[REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md).

### `can-signal-research`

With MCP attached: `get_instance_info`, live preflight, known-first inventory before experiments.

---

## Update workflow

Replace the installed Skill in ChatGPT with a newly built `.skill.zip` from a release
or from `scripts/package_skill.py`.

---

## Private/reference material

Do not bundle SAE/ISO/OEM licensed source documents into Skills.

---

## Related

- [AI_INTEGRATION.md](AI_INTEGRATION.md) — MCP + ChatGPT connector
- [INSTALLATION.md](INSTALLATION.md) — software install
- [USER_ONBOARDING.md](USER_ONBOARDING.md) — end-to-end path
- [RELEASING.md](RELEASING.md) — release build (maintainers)
