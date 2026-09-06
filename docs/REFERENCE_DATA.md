# Reference data and CAN knowledge model

CAN Research can **use** J1939, ISOBUS, OEM, and proprietary reference knowledge — but
this repository **does not distribute** licensed SAE, ISO, or vendor material.

```text
CAN Research software can use reference data.
Users are responsible for providing material they are authorised to use.
```

**Onboarding principle:** establish the user's **existing CAN knowledge** before treating
every frame as unknown. See [USER_ONBOARDING.md](USER_ONBOARDING.md).

```text
Use existing knowledge first.
Research only what remains unknown.
```

---

## Three knowledge categories

| Category | Examples | Normalized use |
|----------|----------|----------------|
| **A. Structured reference catalogue** | J1939 PGN/SPN, ISOBUS DDI, OEM tables | SQLite `data/references/canresearch.db` |
| **B. Existing DBC knowledge** | OEM/supplier DBC, tuned DBC, `<asset>_standard.dbc`, confirmed `<asset>_research.dbc` | Message/signal definitions, coverage vs traffic |
| **C. Supporting reference documents** | PDF manuals, spreadsheets, CSV, Markdown, protocol notes | Provenance + generative/manual consultation → import |

These are **first-class inputs**, not afterthoughts.

---

## Known-first research workflow

```text
live/stored CAN traffic
        +
reference catalogue (A)
        +
existing DBCs (B)
        +
supporting documents (C)
        ↓
known baseline
        ↓
unknown / proprietary remainder
        ↓
CAN Signal Research Skill
        ↓
confirmed research knowledge (CLI → <asset>_research.dbc)
```

The Skill inventories standards-backed traffic, reuses DBC layout fingerprints, and
focuses proprietary effort on the **remainder**.

---

## A. Structured reference catalogue

### What it is

A local SQLite catalogue (`data/references/canresearch.db` by default) of PGN/SPN/DDI
definitions used for:

- Session classification (`analyze_session`)
- Reference-backed decode (`decode_session`)
- MCP lookup (`lookup_pgn`, `lookup_spn`)
- Standard DBC generation (`build_session_dbc_preview`, `session dbc`)

### Implemented today

**Import licensed PDFs (CLI):**

```powershell
uv run canresearch reference import-j1939 path\to\your-licensed-j1939-71.pdf
uv run canresearch reference import-isobus-pdf path\to\your-licensed-isobus-ddi.pdf
```

**Validate and inspect:**

```powershell
uv run canresearch reference validate
uv run canresearch reference stats
uv run canresearch reference source catalogue
uv run canresearch reference pgn 61444
uv run canresearch reference spn 190
uv run canresearch reference warnings
```

**MCP (read-only):** `lookup_pgn`, `lookup_spn`, `build_session_dbc_preview`.

MCP does **not** import reference data — import is CLI-only today.

### Planned / not implemented

| Capability | Status |
|------------|--------|
| `reference import-dbc` | CLI stub — use `reference dbc register` for DBC library |
| Spreadsheet/CSV direct import | Future — convert via bundle format |
| Automated in-core PDF parsing (non-J1939) | Future — use external can-reference-builder |

---

## A2. Reference source registry + normalized bundles

### What it is

Original reference documents (PDFs, manuals, spreadsheets) registered in a **file-backed
registry** under `{data_dir}/reference_sources/` with `public/` and `private/` storage.
Generative tools (e.g. **can-reference-builder**, external) produce **normalized JSON
bundles**; CAN Research validates and imports deterministic knowledge into SQLite.

```text
reference source add  →  can-reference-builder  →  bundle validate  →  bundle import
```

**Operator workflow:** [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md)  
**JSON contract:** [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md)

### Implemented today

Step-by-step operator guide: [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md).

**Register original sources:**

```powershell
uv run canresearch reference source add path\to\manual.pdf `
  --key motor_driver_manual --type oem --visibility private [--vendor ...]
uv run canresearch reference source list
uv run canresearch reference source inspect motor_driver_manual
```

**Validate and import normalized bundles:**

```powershell
uv run canresearch reference bundle validate motor_driver_reference.json
uv run canresearch reference bundle import motor_driver_reference.json
uv run canresearch reference search "motor speed"
```

**MCP (read-only, metadata/bounded):** `list_reference_sources`, `inspect_reference_source`,
`search_reference_knowledge`, `lookup_reference_message`

**Visibility:** `public`, `private`, `licensed` (metadata — default **private**). Licensed
material must never be committed or exposed via MCP raw download.

### External conversion Skill

| Capability | Status |
|------------|--------|
| **can-reference-builder** Skill | **Implemented** — source under `skills/can-reference-builder/`; outputs Reference Bundle V1 JSON |

Package locally: `uv run python scripts/package_skill.py skills/can-reference-builder` —
see [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md). CAN Research validates/imports bundles;
it does not perform generative PDF/OCR conversion in-core.

### Planned later

| Capability | Status |
|------------|--------|
| Vector/semantic document search | Future |
| Automatic PDF parsing inside CAN Research | Not planned for V1 |
| Mask-aware address-family DBC adaptation | Future |

---

## B. Existing DBC knowledge

### Why DBCs matter

```text
existing tuned DBC
    ↓
identify already-known messages/signals
    ↓
compare against observed traffic
    ↓
proprietary research focuses only on unresolved traffic
```

A DBC encodes message IDs, signal boundaries, scaling, and units — often years of
vendor or field tuning. Reusing DBC knowledge avoids rediscovering what is already known.

### DBC sources

| Source | Typical role |
|--------|--------------|
| OEM / supplier DBC | Factory definitions |
| User-created DBC | Workshop tuning |
| Previously tuned DBC | Field-refined scaling |
| `<asset>_standard.dbc` | CAN Research output — **reference-backed** standard knowledge |
| `<asset>_research.dbc` | CAN Research output — **CLI-confirmed** proprietary knowledge |

### Standard vs research — never merge silently

| File | Contents | Trust level |
|------|----------|-------------|
| `<asset>_standard.dbc` | Reference-backed / J1939 standard signals from sessions | Reference-backed |
| `<asset>_research.dbc` | Human-confirmed proprietary signals only | Confirmed research |

Load both in viewers; no combined DBC is generated by CAN Research.

### Implemented today

**Generate standard DBC from session + reference catalogue:**

```powershell
uv run canresearch session dbc <session-id> --asset <asset-key>
```

**Generate confirmed research DBC (after CLI candidate confirm):**

```powershell
uv run canresearch research dbc <asset-key>
```

**MCP preview (read-only):**

- `build_session_dbc_preview` — standard/reference-backed preview from session
- `preview_research_dbc` — confirmed research candidates only
- `list_research_candidates` — inspect confirmed/candidate state

**DBC library (register, inspect, coverage):**

Register user-owned DBC files into a bounded local library (manifest + copy under
`data/dbc/`):

```powershell
uv run canresearch reference dbc register --key my_oem_dbc path\to\file.dbc `
  --name "OEM baseline" --type user_supplied [--asset my_tractor]
uv run canresearch reference dbc list [--asset my_tractor]
uv run canresearch reference dbc inspect my_oem_dbc
uv run canresearch session dbc-coverage <session-id> [--source my_oem_dbc] [--asset my_tractor]
```

**MCP (read-only, bounded source keys — no arbitrary paths):**

- `list_dbc_sources` — registered DBC knowledge sources (+ asset `*_standard.dbc` / `*_research.dbc` in CWD when present)
- `inspect_dbc` — messages, signals, counts for one source key
- `lookup_dbc_message` / `lookup_dbc_signal` — exact CAN ID or name lookup
- `analyze_dbc_coverage` — session vs registered DBCs; returns `known_first` {known, partial, unknown}

Coverage classes: **covered** (exact ID match), **partially_covered** (conflicting definitions,
payload exceeds DLC, or J1939 PGN address-variant match), **unknown** (no DBC message).

Unique-ID and frame-weighted coverage percentages are reported separately.

**Skill behaviour:** use MCP DBC coverage during KNOWN-FIRST before proprietary research.
Local DBC files on disk remain hypothesis generators with provenance — never silent copy.
See Skill [knowledge-reuse.md](../skills/can-signal-research/references/knowledge-reuse.md).

### Planned / not implemented today

| Capability | Status |
|------------|--------|
| `reference import-dbc` (catalogue import) | Not implemented — use `reference dbc register` for library |
| Generic DBC import/transformation pipeline | Future |
| Vector/semantic document search MCP tools | Future |
| Mask/SavvyCAN-style filter-aware DBC adaptation | Future (PGN address-variant matching is partial) |

Until catalogue import exists: **retain DBC files locally**, register via CLI, and run
`session dbc-coverage` or MCP `analyze_dbc_coverage` against stored sessions.

---

## C. Supporting reference documents

### Purpose

Not all knowledge arrives as a clean PGN/SPN table or DBC. Operators often have PDF
protocol specs, OEM manuals, spreadsheets, CSV signal lists, and Markdown notes.

### Implemented workflow

See [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) for the full operator sequence.

```text
reference source add (retain original, visibility metadata)
        ↓
can-reference-builder Skill (generative — messy → normalized JSON)
        ↓
reference bundle validate → reference bundle import (deterministic)
        ↓
search / lookup via CLI and MCP
```

**Do not discard originals after conversion.** Provenance and re-import depend on them.

**Today:**

- **Source registry** — `{data_dir}/reference_sources/` with `public/` and `private/` storage
- **Reference Bundle V1** — validated/imported per [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md)
- **MCP (read-only):** `list_reference_sources`, `inspect_reference_source`,
  `search_reference_knowledge`, `lookup_reference_message`
- **Generative conversion** — **can-reference-builder** Skill; not in-core PDF parsing
- **J1939/ISOBUS PDFs** — separate catalogue import path (section A), not bundle format

### Future (not V1)

| Capability | Status |
|------------|--------|
| Vector/semantic search over retained documents | Future |
| Automatic in-core PDF parsing (non-J1939) | Not planned for V1 |
| Full provenance metadata on every signal | Partial today |

---

## Public vs private material

CAN Research must **not** distribute licensed SAE/ISO/OEM content without permission.

| Class | Guidance |
|-------|----------|
| **Public / redistributable** | May be committed where licence explicitly permits |
| **Private / licensed** | Keep **outside public Git history**; store locally only |

### Practical storage

These paths are **gitignored** — suitable for private material:

| Path | Intended use |
|------|--------------|
| `data/` | Local config, SQLite catalogue, captures, reference source registry |
| `references/private/` | Private reference extracts |
| `docs/original_docs/` | Original licensed source documents (never commit) |

The **reference source registry** lives under `{data_dir}/reference_sources/` (see section A2).
Register sources with `reference source add`; originals are copied or linked per visibility.

**Never commit:** licensed PDFs, full SAE databases, customer OEM packs, API keys, bundle JSON
containing proprietary signal definitions unless explicitly permitted.

---

## Provenance model

Provenance categories must **never be silently collapsed**:

| Category | Meaning |
|----------|---------|
| **Public / reference-backed** | In imported catalogue from permitted public sources |
| **SAE/ISO / user-supplied reference** | User imported licensed standard PDF into local DB |
| **OEM / vendor-backed** | From vendor documentation user is authorised to use |
| **User-supplied DBC** | External DBC file used as knowledge source |
| **User-supplied reference document** | PDF/spreadsheet/manual — source retained |
| **Confirmed proprietary research** | CLI-confirmed in `<asset>_research.dbc` |
| **Generative hypothesis** | AI/Skill inference — not confirmed |

### Desired provenance metadata (conceptual)

Future imports should record where possible:

- Source name and type
- File / document path (local)
- Version or date if known
- Origin (OEM, SAE, internal, field trial)
- Licensing / private status
- Conversion method (manual, PDF importer, reference-builder)
- Import date

**Today:** `reference source list` and import warnings provide partial source tracking
in the SQLite catalogue. Full provenance on every signal is **not yet implemented**.

---

## Reference conversion architecture

For formats not directly importable via J1939/ISOBUS PDF importers:

```text
user-owned source material (PDF, XLSX, CSV, DBC, Markdown, manual)
        ↓
can-reference-builder Skill (generative interpretation)
        ↓
Reference Bundle V1 JSON
        ↓
reference bundle validate → reference bundle import (deterministic)
        ↓
SQLite reference knowledge + MCP search/lookup
```

**Core principle:**

```text
Generative AI (can-reference-builder) interprets messy source material.
Deterministic CAN Research validates and imports normalized bundles.
```

DBC knowledge remains a **separate first-class path** — register DBCs via
`reference dbc register`, not via bundle import.

Contract: [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md)

---

## CAN Research Skills (reference workflow)

Three Skills ship as source under `skills/` (package locally — not committed as zip):

| Skill | Role |
|-------|------|
| **can-onboarding** | Install, validate, MCP/tunnel, knowledge intake checkpoints |
| **can-reference-builder** | Messy manuals/tables → Reference Bundle V1 JSON |
| **can-signal-research** | Known-first proprietary signal research on traffic remainder |

Install order for new users: onboarding → reference-builder (when material exists) →
signal-research. See [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md).

---

## Future MCP / core capabilities (candidate — not existing)

Based on Skill validation, likely useful **deterministic** capabilities for a future milestone:

| Candidate capability | Purpose |
|---------------------|---------|
| Vector/semantic document search | Operator + Skill retrieval over retained docs |
| Expose full provenance per definition | Trust labelling |
| Mask/filter-aware DBC adaptation | SavvyCAN-style address families |

**Implemented today:** DBC library, reference source registry, bundle import, session DBC
coverage, and reference search/lookup MCP tools. Verify MCP count with
`uv run canresearch mcp tools` — baseline **41 tools** (see README).

---

## MCP reference tools (implemented today)

| Tool | Purpose |
|------|---------|
| `lookup_pgn` | PGN in local catalogue |
| `lookup_spn` | SPN in local catalogue |
| `build_session_dbc_preview` | Standard DBC preview from session + catalogue |
| `preview_research_dbc` | Confirmed research DBC preview |
| `list_research_candidates` | Candidate/evidence inspect |
| `analyze_session` | J1939 classification vs catalogue |
| `decode_session` | Reference-backed decode |
| `list_dbc_sources` | Registered DBC knowledge sources |
| `inspect_dbc` | Message/signal inventory for one source |
| `lookup_dbc_message` / `lookup_dbc_signal` | Exact ID or name lookup |
| `analyze_dbc_coverage` | Session vs DBC known-first summary |
| `list_reference_sources` | Registered reference source metadata |
| `inspect_reference_source` | One source — visibility, import status |
| `search_reference_knowledge` | Bounded search over imported bundle knowledge |
| `lookup_reference_message` | Exact message lookup from imported bundles |

Import remains **CLI-only** (catalogue PDFs, source registration, bundle import, DBC register).

---

## Related

- [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md) — operator workflow (manual → bundle → import)
- [USER_ONBOARDING.md](USER_ONBOARDING.md) — end-to-end new user path
- [INSTALLATION.md](INSTALLATION.md) — software setup
- [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) — all three Skills
- [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) — known-first architecture
