# User onboarding

End-to-end guide for a new CAN Research installation — from software setup through
**establishing your existing CAN knowledge** to researching only what remains unknown.

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
| 1 | Install CAN Research | [INSTALLATION.md](INSTALLATION.md) |
| 2 | Configure local instance | [INSTALLATION.md](INSTALLATION.md) — `data/config.toml`, `instance_key` |
| 3 | Connect CANsub.2 | [CANSUB_SETUP.md](CANSUB_SETUP.md) |
| 4 | Validate CAN traffic | [CANSUB_SETUP.md](CANSUB_SETUP.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| 5 | Inventory existing CAN knowledge | [REFERENCE_DATA.md](REFERENCE_DATA.md) — three categories below |
| 6 | Add/import structured reference data | [REFERENCE_DATA.md](REFERENCE_DATA.md) — **implemented** import paths |
| 7 | Add existing DBC files | [REFERENCE_DATA.md](REFERENCE_DATA.md) — **partial / planned** automation |
| 8 | Add supporting reference documents | [REFERENCE_DATA.md](REFERENCE_DATA.md) — retention model |
| 9 | Convert unsupported formats (if needed) | [REFERENCE_DATA.md](REFERENCE_DATA.md) — **planned** `can-reference-builder` |
| 10 | Validate local reference knowledge | [REFERENCE_DATA.md](REFERENCE_DATA.md) — `reference validate` |
| 11 | Install CAN Signal Research Skill | [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) |
| 12 | Establish first asset | [INSTALLATION.md](INSTALLATION.md) — `asset add` |
| 13 | Run known-first analysis | Below + [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) |
| 14 | Research unknown remainder only | Skill + MCP passive workflow |

**Multiple machines?** Repeat per installation — [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md).

---

## Three knowledge categories

CAN Research treats these as **first-class** inputs:

### 1. Structured reference data

J1939, ISOBUS, OEM PGN/SPN tables — normalized into the local reference catalogue
(`data/references/canresearch.db`).

**Today:** import licensed J1939-71 and ISOBUS DDI PDFs via CLI. Lookup via MCP
`lookup_pgn` / `lookup_spn`.

### 2. Existing DBC knowledge

Supplier, OEM, user-created, tuned, `<asset>_standard.dbc`, confirmed `<asset>_research.dbc`.

**Today:** generate/preview standard DBC from sessions + reference catalogue; confirmed
research DBC from CLI-confirmed candidates. **Automated DBC import/inspection is not yet
implemented** — retain files locally and use Skill/host consultation until core support
exists.

### 3. Supporting reference documents

PDFs, spreadsheets, CSV, Markdown, OEM manuals — retained for provenance and
generative/manual consultation; normalized forms feed deterministic tools when imported.

See [REFERENCE_DATA.md](REFERENCE_DATA.md) for the full model.

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

### DBC files (today)

- Keep DBCs in a **local private area** (not in public Git) — see [REFERENCE_DATA.md](REFERENCE_DATA.md)
- Generate reference-backed standard DBC from a capture:

```powershell
uv run canresearch session dbc <session-id> --asset <asset-key>
```

- Preview via MCP: `build_session_dbc_preview`, `preview_research_dbc`
- **`reference import-dbc` is not implemented yet** — do not assume automated DBC ingest

### Supporting documents (today)

- Retain originals locally for provenance (`references/private/`, `docs/original_docs/`, or
  your own ignored folder — all gitignored patterns in `.gitignore`)
- Use generative tools (future **can-reference-builder** Skill) or manual import paths for
  structured extraction

Full detail: [REFERENCE_DATA.md](REFERENCE_DATA.md).

---

## Step 11 — MCP + Skill

1. Start MCP — [MCP_SETUP.md](MCP_SETUP.md)
2. Connect ChatGPT connector
3. Upload `skills/can-signal-research/skill.zip` — [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md)

The Skill is **portable** — confirm backend with `get_instance_info`.

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
existing DBCs (manual / future automated)
        +
relevant supporting documents
        ↓
known baseline
        ↓
unknown / proprietary remainder
        ↓
CAN Signal Research Skill
        ↓
confirmed research knowledge (CLI)
```

### Known-first checklist (MCP / CLI)

| Action | Tool / command |
|--------|----------------|
| Capture or select session | `capture start` / `list_sessions` |
| Classify J1939 traffic | `analyze_session` |
| Decode reference-backed values | `decode_session`, `lookup_pgn`, `lookup_spn` |
| List nodes | `list_session_nodes` |
| Preview standard DBC | `build_session_dbc_preview` |
| List confirmed proprietary | `list_research_candidates`, `preview_research_dbc` |
| Isolate unknown IDs | Skill bus inventory — compare analysis to DBC/reference |
| Research remainder | Skill passive inference → experiment if needed |

**Do not** experimentally rediscover signals already in your reference catalogue or
confirmed DBC.

Passive preflight before capture is required — see Skill V2/V3 workflow.

---

## What success looks like

After onboarding you should have:

- [ ] CAN Research running with validated CANsub path
- [ ] MCP + Skill connected (`get_instance_info` correct)
- [ ] Local reference catalogue populated **or** a plan to add it
- [ ] DBC files and source documents **retained locally** with provenance understood
- [ ] At least one asset defined
- [ ] A capture with known vs unknown traffic separated
- [ ] Proprietary research targeting **remainder only**

---

## Related documents

| Document | When |
|----------|------|
| [REFERENCE_DATA.md](REFERENCE_DATA.md) | Knowledge model, licensing, conversion, future tools |
| [INSTALLATION.md](INSTALLATION.md) | Software install |
| [CANSUB_SETUP.md](CANSUB_SETUP.md) | Hardware |
| [MCP_SETUP.md](MCP_SETUP.md) | ChatGPT connector |
| [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) | Skill package |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Failures |
| [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) | Architecture contract |
