# CAN Signal Research Skill — installation

Install and update the **can-signal-research** Skill in ChatGPT (or compatible hosts).

## Three artifacts (keep roles separate)

| Artifact | Role |
|----------|------|
| `skills/can-signal-research/` (repo) | **Source of truth** — edit here |
| `skills/can-signal-research/skill.zip` | **Deployment package** — upload to ChatGPT |
| Installed ChatGPT Skill | **Deployed copy** — runtime in ChatGPT |

Rule:

```text
repo Skill source  →  rebuild skill.zip  →  replace installed Skill in ChatGPT
```

Git history is the version history. Keep the Skill name stable (`can-signal-research`) —
do not create `v2` / `v3` copies in ChatGPT.

## What the Skill does

The Skill is the **generative orchestration layer** above CAN Research MCP:

- Confirms backend via `get_instance_info`
- Runs live preflight before capture
- Establishes system/asset context with minimal questions
- Applies known/reference-backed knowledge first
- Validates passive hypotheses with `preview_candidate_values`
- Requests physical experiments only when needed
- Separates encoding vs semantic confidence
- Stops at CLI-only candidate confirmation

It is **portable** across installations (office, workshop, laptop, travel). It must **not**
assume a specific backend name — always confirm with `get_instance_info`.

Full methodology: [skills/can-signal-research/SKILL.md](../skills/can-signal-research/SKILL.md).

Architecture: [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md).

## Prerequisites

1. CAN Research installed and configured — [INSTALLATION.md](INSTALLATION.md)
2. CANsub connected — [CANSUB_SETUP.md](CANSUB_SETUP.md)
3. MCP server running and reachable from ChatGPT — [MCP_SETUP.md](MCP_SETUP.md)
4. ChatGPT MCP connector attached for **your** CAN Research instance

## Install in ChatGPT

1. Ensure `skills/can-signal-research/skill.zip` is up to date (see rebuild below)
2. In ChatGPT, go to **`/skills`**
3. Upload **`skill.zip`**
4. Do **not** manually unzip before upload
5. Enable the Skill in your workspace/chat as required by the UI

On **update**, remove or replace the previous `can-signal-research` Skill when the UI
requires it, then upload the new `skill.zip`.

## Rebuild skill.zip (from repo root)

After editing repo Skill source:

```powershell
cd skills\can-signal-research
Remove-Item skill.zip -ErrorAction SilentlyContinue
Compress-Archive -Path SKILL.md, agents, references -DestinationPath skill.zip
```

Expected archive contents:

```text
SKILL.md
agents/openai.yaml
references/evidence-and-confidence.md
references/experiment-patterns.md
references/system-context-and-assets.md
```

No Skill packaging validator exists in this repository today — verify file list manually
or compare SHA-256 hashes against source files.

## Update workflow

```text
benchmark / observed weakness
  ↓
edit repo Skill source (skills/can-signal-research/)
  ↓
validate references and SKILL.md consistency
  ↓
rebuild skill.zip
  ↓
replace installed Skill in ChatGPT (/skills)
  ↓
verify installed Skill behaviour
  ↓
run next benchmark
```

## Verify after install

1. **MCP connected** — ChatGPT shows your CAN Research connector enabled
2. **`get_instance_info`** — returns your `instance_key`, schema v8, 32 tools
3. **Skill active** — ask for a passive traffic check; Skill should preflight before capture
4. **Spot-check** — confirm V2 behaviours are present (preflight, `channel_rx_in_use`
   handling, encoding/semantic confidence language)

Optional: compare ChatGPT Skill behaviour against checklist in
[SKILL.md — Self-evaluation](../skills/can-signal-research/SKILL.md).

## Distinction: signal research vs reference builder

| Skill | Purpose | Status |
|-------|---------|--------|
| **can-signal-research** | Proprietary signal discovery on live/stored CAN data | In repo |
| **can-reference-builder** (planned) | Turn user-owned reference material into validated import bundles | **Not yet in repo** |

Do not confuse the two. Reference data policy: [REFERENCE_DATA.md](REFERENCE_DATA.md).

## Related

- [MCP_SETUP.md](MCP_SETUP.md) — MCP + tunnel + connector
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — connector and channel issues
- [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) — same Skill, many machines
