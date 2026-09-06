# User onboarding

End-to-end guide for a new CAN Research installation — from software setup through
**establishing your existing CAN knowledge** to researching only what remains unknown.

**Recommended:** install the **can-onboarding** Skill and follow its checkpoints. This
document is the canonical human-readable sequence if you prefer not to use the Skill.

**Principle:**

```text
Use existing knowledge first.
Research only what remains unknown.
```

Onboarding is **not complete** when the software installs. A useful installation also
loads the CAN knowledge you already possess.

---

## Before you start — inventory your knowledge

Many reverse-engineering hours can be avoided if you already have:

| Do you have…? | Examples |
|---------------|----------|
| **DBC files** | OEM, supplier, tuned, previously confirmed research DBCs |
| **J1939 / ISOBUS references** | Licensed PDFs, structured tables, PGN/SPN lists |
| **OEM / vendor manuals** | Protocol specs, implementation notes |
| **Signal spreadsheets** | CSV/XLSX with bit positions, factors, units |
| **Previously reverse-engineered definitions** | Confirmed candidates, internal docs |
| **Protocol documents** | Markdown, text, PDF appendices |

If yes → plan to add them during steps 5–10 below. Details: [REFERENCE_DATA.md](REFERENCE_DATA.md).

---

## Onboarding flow

| Step | Task | Guide |
|------|------|-------|
| 0 | Guided setup (optional) | **can-onboarding** Skill — [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) |
| 1 | Install CAN Research | [INSTALLATION.md](INSTALLATION.md) — **`setup.cmd`** (Windows) or developer clone |
| 2 | Configure local instance | [INSTALLATION.md](INSTALLATION.md) — `data/config.toml`, `instance_key` |
| 3 | Connect CANsub.2 | [CANSUB_SETUP.md](CANSUB_SETUP.md) |
| 4 | Validate CAN traffic | [CANSUB_SETUP.md](CANSUB_SETUP.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| 5 | Inventory existing CAN knowledge | [REFERENCE_DATA.md](REFERENCE_DATA.md) — three knowledge paths |
| 6 | Add/import structured reference data | [REFERENCE_DATA.md](REFERENCE_DATA.md) — catalogue import |
| 7 | Add existing DBC files | [REFERENCE_DATA.md](REFERENCE_DATA.md) — **`reference dbc register`** |
| 8 | Register supporting reference documents | [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) — source registry |
| 9 | Convert messy formats (if needed) | [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) · **can-reference-builder** |
| 10 | Validate and import reference bundles | [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) — validate / import / verify |
| 11 | Install Skills + MCP | [MCP_SETUP.md](MCP_SETUP.md) · [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) |
| 12 | Establish first asset | [INSTALLATION.md](INSTALLATION.md) — `asset add` |
| 13 | Run known-first analysis | Below + [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) |
| 14 | Research unknown remainder only | **can-signal-research** + MCP passive workflow |

**Multiple machines?** Repeat per installation — [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md).

---

## Three knowledge paths

CAN Research treats these as **first-class, separate** inputs (see [REFERENCE_DATA.md](REFERENCE_DATA.md)):

### 1. Structured reference catalogue

J1939, ISOBUS, OEM PGN/SPN tables — normalized into the local reference catalogue
(`data/references/canresearch.db`).

**Today:** import licensed J1939-71 and ISOBUS DDI PDFs via CLI. Lookup via MCP
`lookup_pgn` / `lookup_spn`.

### 2. Registered DBC knowledge

Supplier, OEM, user-created, tuned, `<asset>_standard.dbc`, confirmed `<asset>_research.dbc`.

**Today:** register DBCs into the local library, inspect them, and run session coverage
analysis. Generate/preview `<asset>_standard.dbc` from sessions + reference catalogue;
confirmed research DBC from CLI-confirmed candidates. Asset-scoped `*_standard.dbc` /
`*_research.dbc` in the working directory are auto-discovered when listed.

```powershell
uv run canresearch reference dbc register --key supplier_baseline path\to\file.dbc
uv run canresearch reference dbc list
uv run canresearch session dbc-coverage <session-id>
```

### 3. Supporting reference sources + Reference Bundle V1

PDFs, spreadsheets, CSV, Markdown, OEM manuals — follow the operator workflow in
[REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) (register → can-reference-builder →
validate → import → verify).

Messy source conversion is handled by the **can-reference-builder** Skill (generative);
CAN Research core does not parse arbitrary PDFs.

---

## Step 4 — Validate CAN traffic (quick)

```powershell
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch device info
uv run canresearch device channel-info 1
uv run canresearch device rx 1 --duration 5
```

With MCP running, preflight in ChatGPT:

```text
get_instance_info → get_cansub_device_status → get_cansub_channel_status → observe_live_traffic
```

Confirm frames before capture. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if not.

---

## Steps 6–10 — Add your knowledge (summary)

### Structured reference (implemented)

```powershell
uv run canresearch reference import-j1939 path\to\licensed-j1939-71.pdf
uv run canresearch reference import-isobus-pdf path\to\licensed-isobus-ddi.pdf
uv run canresearch reference validate
uv run canresearch reference stats
```

### DBC files (implemented)

- Keep originals in a **local private area** (not in public Git) — see [REFERENCE_DATA.md](REFERENCE_DATA.md)
- Register into the bounded DBC library:

```powershell
uv run canresearch reference dbc register --key my_dbc path\to\file.dbc `
  --name "Supplier baseline" --type user_supplied [--asset my_tractor]
uv run canresearch reference dbc list [--asset my_tractor]
uv run canresearch reference dbc inspect my_dbc
```

- Compare a stored session against registered DBCs:

```powershell
uv run canresearch session dbc-coverage <session-id> [--source my_dbc] [--asset my_tractor]
```

- MCP (Skill KNOWN-FIRST): `list_dbc_sources`, `inspect_dbc`, `analyze_dbc_coverage`
- Generate reference-backed standard DBC from a capture:

```powershell
uv run canresearch session dbc <session-id> --asset <asset-key>
```

- **`reference import-dbc`** (catalogue import) is not implemented — use **`reference dbc register`** for the DBC library

### Supporting documents (implemented registry + bundle import)

Full step-by-step: [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md).

Summary:

```powershell
uv run canresearch reference source add path\to\manual.pdf --key my_manual --visibility private
# … can-reference-builder produces my_manual_reference.json …
uv run canresearch reference bundle validate my_manual_reference.json
uv run canresearch reference bundle import my_manual_reference.json
uv run canresearch reference search "motor speed"
```

See [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md). Retain originals locally
(gitignored) — see [REFERENCE_DATA.md](REFERENCE_DATA.md).

---

## Step 11 — MCP + Skills

1. Start MCP — [MCP_SETUP.md](MCP_SETUP.md)
2. Connect ChatGPT connector (if used)
3. Package and install Skills — [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md):

```powershell
uv run python scripts/package_skill.py skills/can-onboarding
# upload skills/can-onboarding/skill.zip to ChatGPT

# when reference material exists:
uv run python scripts/package_skill.py skills/can-reference-builder

# for proprietary research:
uv run python scripts/package_skill.py skills/can-signal-research
```

Generated `skill.zip` files are **local deployment artifacts** (gitignored) — build on
each machine after clone. Typical order: **can-onboarding** → **can-reference-builder**
(when needed) → **can-signal-research**.

Confirm backend with `get_instance_info`. Verify tool count with `uv run canresearch mcp tools`.

---

## Step 12 — First asset

```powershell
uv run canresearch asset add --key my_tractor --name "My Tractor" --type tractor
uv run canresearch asset list
```

MCP: `list_assets`, `get_asset`. Skill may propose scope; CLI creates assets.

---

## Steps 13–14 — Known-first research

Central workflow:

```text
live/stored CAN traffic
        +
reference catalogue
        +
registered DBC library (+ asset *_standard.dbc / *_research.dbc)
        +
imported reference bundles
        ↓
known baseline (reference + DBC + bundle coverage)
        ↓
unknown / proprietary remainder
        ↓
can-signal-research Skill
        ↓
confirmed research knowledge (CLI)
```

Workflow:

```text
existing DBC → register/discover → inspect → compare against session
  → determine known coverage → research unknown remainder
```

### Known-first checklist (MCP / CLI)

| Action | Tool / command |
|--------|----------------|
| Capture or select session | `capture start` / `list_sessions` |
| Classify J1939 traffic | `analyze_session` |
| Decode reference-backed values | `decode_session`, `lookup_pgn`, `lookup_spn` |
| List nodes | `list_session_nodes` |
| Preview standard DBC | `build_session_dbc_preview` |
| List registered reference sources | `list_reference_sources` |
| Search imported reference knowledge | `reference search` / `search_reference_knowledge` |
| Lookup reference message | `lookup_reference_message` |
| List registered DBC sources | `list_dbc_sources` |
| Session vs DBC coverage | `session dbc-coverage` / `analyze_dbc_coverage` |
| List confirmed proprietary | `list_research_candidates`, `preview_research_dbc` |
| Isolate unknown IDs | Skill bus inventory — DBC + reference + bundle analysis |
| Research remainder | can-signal-research — passive inference → experiment if needed |

**Do not** experimentally rediscover signals already in your reference catalogue,
imported bundles, or confirmed DBC.

Passive preflight before capture is required — see can-signal-research workflow.

---

## Laptop onboarding smoke test (manual)

Use this checklist on a **fresh second laptop**:

| Step | Action |
|------|--------|
| A | Clone repo, `uv sync`, copy `config.toml.example` → `data/config.toml`, set `instance_key` |
| B | `uv run canresearch config show` — confirm `resolved_data_dir` |
| C | `uv run canresearch reference source add path\to\private.pdf --key trial_manual --visibility private` |
| D | `uv run canresearch reference source list` and `reference source inspect trial_manual` |
| E | Create a bundle from [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md) (or synthetic fixture) with matching `source_key` |
| F | `uv run canresearch reference bundle validate trial_manual.json` |
| G | `uv run canresearch reference bundle import trial_manual.json` |
| H | `uv run canresearch reference search "<signal name>"` |
| I | `uv run canresearch reference dbc register --key trial_dbc path\to\file.dbc` |
| J | `uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp` |
| K | MCP: `list_reference_sources`, `search_reference_knowledge`, `list_dbc_sources` |
| L | CANsub connect + known-first: `analyze_session`, `analyze_dbc_coverage`, can-signal-research workflow |

Do **not** commit private PDFs or proprietary bundle content.

---

## What success looks like

After onboarding you should have:

- [ ] CAN Research running with validated CANsub path
- [ ] MCP + Skills connected (`get_instance_info` correct)
- [ ] Local reference catalogue populated **or** a plan to add it
- [ ] DBC files and source documents **retained locally** with provenance understood
- [ ] Reference bundles imported where supporting documents exist
- [ ] At least one asset defined
- [ ] A capture with known vs unknown traffic separated
- [ ] Proprietary research targeting **remainder only**

---

## Related documents

| Document | When |
|----------|------|
| [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) | Manual/PDF → bundle operator workflow |
| [REFERENCE_DATA.md](REFERENCE_DATA.md) | Knowledge model, licensing, three paths |
| [INSTALLATION.md](INSTALLATION.md) | Software install |
| [CANSUB_SETUP.md](CANSUB_SETUP.md) | Hardware |
| [MCP_SETUP.md](MCP_SETUP.md) | ChatGPT connector |
| [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) | Skill packaging and install |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Failures |
| [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) | Architecture contract |
