# Reference data policy

CAN Research can **use** J1939/ISOBUS reference data for lookup, session classification,
and standard DBC generation — but this repository **does not distribute** licensed SAE,
ISO, or other proprietary standards content.

```text
CAN Research software can use reference data.
Users are responsible for providing material they are authorised to use.
```

**Do not commit** licensed PDFs, full SAE databases, or vendor OEM documentation to the
repository. Parsed reference data built from your own sources belongs under `data/` or
other gitignored paths (see `.gitignore`).

---

## Your options today

### A. Use an existing local reference database

If you already have a CAN Research-compatible SQLite reference catalogue at
`data/references/canresearch.db` (from a prior import on that machine), CAN Research
will use it for `lookup_pgn`, `lookup_spn`, session analysis, and standard DBC preview.

Check status:

```powershell
uv run canresearch reference stats
uv run canresearch reference validate
uv run canresearch reference pgn 61444
uv run canresearch reference spn 190
```

### B. Import from user-owned PDF sources (implemented)

If you hold a **licence** to use specific source documents, the CLI can import into the
local private catalogue:

**J1939-71 PDF** (user-provided, licensed):

```powershell
uv run canresearch reference import-j1939 path\to\your-licensed-j1939-71.pdf
```

**ISOBUS DDI PDF** (user-provided, licensed):

```powershell
uv run canresearch reference import-isobus-pdf path\to\your-licensed-isobus-ddi.pdf
```

After import:

```powershell
uv run canresearch reference validate
uv run canresearch reference stats
uv run canresearch reference source list
```

These commands write to **your local** `data/references/canresearch.db` only.

### C. Import from DBC (planned — not implemented)

```powershell
uv run canresearch reference import-dbc path\to\file.dbc
```

Currently prints **“not yet implemented”**. Only import DBCs you are licensed to use.
When implemented, this will follow the same local-private storage model.

### D. Build a private reference bundle (future workflow)

**Planned / future** — no finished “import bundle” CLI exists yet.

Intended architecture:

```text
user-owned reference documents (PDF, spreadsheet, DBC, CSV, OEM manuals)
        ↓
generative extraction / reference-builder workflow
        ↓
deterministic validation
        ↓
CAN Research reference import format
        ↓
local private reference database
```

**Principle:**

```text
Generative AI interprets messy source material.
Deterministic CAN Research tooling validates and imports it.
```

Deterministic validation should cover (conceptually):

- PGN, SPN, bit positions, bit lengths
- Endian, signedness, factor, offset, units, enums
- Duplicates, overlaps, provenance

### Planned companion Skill: can-reference-builder

**Not yet part of this repository.**

Intended job: help turn **user-owned** reference material into a CAN Research-compatible,
**validated** reference bundle for local import.

Distinct from **can-signal-research**, which researches **unknown/proprietary** signals
on live or stored CAN traffic.

---

## Provenance categories (do not collapse)

| Category | Meaning |
|----------|---------|
| **Public / reference-backed** | Documented in your imported reference catalogue (PGN/SPN) |
| **User-supplied reference** | Imported from your licensed PDF/DBC sources |
| **Vendor / OEM-backed** | From OEM documentation you are authorised to use |
| **Confirmed proprietary research** | CLI-confirmed entries in `<asset>_research.dbc` |
| **Generative hypothesis** | AI/MCP inference — not confirmed, not reference fact |

The CAN Signal Research Skill must label these distinctly. MCP inference is **never**
reference-backed fact until human CLI confirmation for proprietary candidates.

---

## Standard vs research DBC

Per asset:

| File | Contents |
|------|----------|
| `<asset>_standard.dbc` | Reference-backed / standard signals from sessions |
| `<asset>_research.dbc` | Human-confirmed proprietary signals only |

No combined DBC is generated. Research candidates require explicit CLI review/confirm.

---

## MCP reference tools (read-only)

| Tool | Purpose |
|------|---------|
| `lookup_pgn` | Reference catalogue PGN lookup |
| `lookup_spn` | Reference catalogue SPN lookup |
| `build_session_dbc_preview` | Preview standard DBC from session + reference |

MCP does not import reference data — import is CLI-only today.

---

## Related

- [INSTALLATION.md](INSTALLATION.md) — setup
- [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) — can-signal-research Skill
- [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) — known-first workflow
