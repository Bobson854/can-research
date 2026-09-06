# Reference onboarding — operator workflow

Practical guide: **I have an OEM manual, supplier PDF, spreadsheet, or protocol notes — what do I actually do?**

CAN Research does **not** expect you to manually transcribe useful documentation into Python
or SQLite. The workflow is:

```text
keep original
    → register reference source
    → can-reference-builder interprets it
    → validate Reference Bundle V1 JSON
    → import deterministically
    → verify via CLI / MCP
    → use in known-first research
```

**Trust boundary:**

```text
AI interprets (can-reference-builder).
CAN Research validates and imports (CLI).
Human/operator remains in control.
```

The Skill must **not** directly modify the CAN Research database. All writes go through
`reference bundle import` on the CLI.

**Related docs (do not duplicate here):**

| Document | Owns |
|----------|------|
| [REFERENCE_DATA.md](REFERENCE_DATA.md) | Knowledge model, licensing, DBC vs bundle vs catalogue |
| [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md) | Exact JSON contract and field rules |
| [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) | Packaging and installing **can-reference-builder** |

---

## End-to-end workflow

```text
ORIGINAL DOCUMENT (user-owned, retained locally)
        ↓
reference source registry          ← CLI: reference source add/list/inspect
        ↓
can-reference-builder Skill        ← generative interpretation (ChatGPT)
        ↓
Reference Bundle V1 JSON           ← <source_key>_reference.json
        ↓
reference bundle validate          ← deterministic structural checks
        ↓
reference bundle import            ← SQLite reference knowledge
        ↓
CLI reference search  +  MCP search/lookup
        ↓
known-first signal research        ← can-signal-research
```

The **original source** remains the provenance anchor. The bundle carries normalized facts
and `source_location` pointers — not a copy of the entire document.

---

## 1. Decide which intake path applies

| Material | Path | CLI entry point |
|----------|------|-----------------|
| SAE J1939-71 PDF (licensed, supported importer) | Structured J1939/ISOBUS **catalogue** | `reference import-j1939` |
| ISOBUS DDI PDF (licensed, supported importer) | Structured J1939/ISOBUS **catalogue** | `reference import-isobus-pdf` |
| Existing DBC file | **DBC knowledge** (separate path) | `reference dbc register` |
| OEM manual / supplier PDF / XLSX / CSV / Markdown / protocol notes | **Reference source** → bundle | `reference source add` → **can-reference-builder** → bundle validate/import |

**Important:** DBC registration and Reference Bundle import are **deliberately separate**.
Do not put DBC layout knowledge into a bundle unless you are normalizing manual tables;
register finished DBCs with `reference dbc register` instead.

For J1939/ISOBUS standards PDFs, use the deterministic catalogue importers — not
can-reference-builder — unless the document shape is unsupported.

---

## 2. Register the original reference source

Copy the original into the managed registry under `{data_dir}/reference_sources/` and record
metadata in `manifest.toml`.

```powershell
uv run canresearch reference source add path\to\manual.pdf `
  --key motor_driver_manual `
  --type oem `
  --visibility private `
  --vendor "Example Vendor" `
  --version "Rev C" `
  --date "2024-03"
```

Then confirm registration:

```powershell
uv run canresearch reference source list
uv run canresearch reference source inspect motor_driver_manual
```

`reference source inspect` shows registry metadata and **imported knowledge counts** for
that `source_key` (zero until a bundle is imported).

### `source_key` — durable identity

The `source_key` is the stable join between:

- the retained original document in the registry
- the Reference Bundle V1 `source_key` field
- imported SQLite rows (`reference_knowledge_*` tables)

Rules (enforced by the registry):

- Must start with a letter or digit
- Only `[A-Za-z0-9_-]` thereafter
- **Choose once** and reuse for revisions of the same logical source
- Use the **exact same key** in the bundle JSON

Re-registering with the same key **updates** the manifest entry and replaces the stored
copy of the original file.

### `source_type` vs `visibility`

These are separate axes:

| Axis | Values | Meaning |
|------|--------|---------|
| **source_type** | `standard`, `oem`, `supplier`, `user_dbc`, `user_document`, `research`, `other` | What kind of document it is |
| **visibility** | `public`, `private`, `licensed` | Licensing/redistribution class (default **`private`**) |

`licensed` and `private` originals are stored under the registry's `private/` folder.
Visibility is metadata for provenance — it does **not** expose raw files through MCP.

Optional registry fields: `--name`, `--vendor`, `--version`, `--date`, `--notes`.

---

## 3. Give the source to can-reference-builder

Install the Skill first — [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md).

Provide the Skill with:

- the **original document** (upload or path in the host environment)
- the exact **`source_key`** already registered (`motor_driver_manual`)
- useful context: manufacturer, device family, protocol name, bus bitrate if known
- **do not** ask the operator to pre-extract tables unless the Skill cannot read the format

The Skill should return a single JSON file, conventionally:

```text
motor_driver_manual_reference.json
```

The bundle should contain **only normalized facts supported by the source**. The Skill must
preserve uncertainty and provenance rather than inventing missing:

- CAN IDs · PGNs · bit positions · endianness · scale · units · timing · enum meanings

If a field is unknown, omit it or mark incomplete — validation may emit **warnings** for
missing scale/unit, but must not be “filled in” with guesses.

Contract details: [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md)

Safe synthetic examples in the repo (for structure only):

- `tests/fixtures/reference_bundles/db_series_driver_synthetic.json`
- `tests/fixtures/reference_bundles/smartec_mownet_synthetic.json`

---

## 4. Validate before import

```powershell
uv run canresearch reference bundle validate motor_driver_manual_reference.json
```

Validation checks schema version, registered `source_key`, duplicate IDs, signal overlap,
enum references, mask/pattern shape, and related structural rules.

| Result | Meaning | Action |
|--------|---------|--------|
| **ERROR** | Import will fail | Fix the **normalized JSON**; do not alter source facts to satisfy the validator |
| **WARNING** | Incomplete metadata | Review; import may still proceed if there are zero errors |

Exit code: non-zero when any error exists. On success you will see `Validation passed.`

Advanced: `--allow-unregistered` skips the registered-source check (normally you should
register first).

**If validation fails:** repair the bundle representation or re-run can-reference-builder.
Escalate contract gaps to `protocol_notes` rather than lossy mappings — see section 11.

---

## 5. Import

```powershell
uv run canresearch reference bundle import motor_driver_manual_reference.json
```

Import **re-runs validation** and refuses to proceed if any errors remain. Warnings are
printed to the terminal but do not block import.

### Re-import / idempotency (current behaviour)

For a given `source_key`, import **replaces** all previously imported bundle knowledge:

1. Deletes existing rows in `reference_knowledge_*` tables for that `source_key`
2. Inserts rows from the new bundle
3. Records a fingerprint in `reference_knowledge_imports`

Re-importing the **same** bundle content is safe (idempotent outcome). Re-importing a
**revised** bundle is the normal way to update normalized knowledge for the same source.

There is **no** CLI merge/patch mode — the full bundle is the unit of import.

### What is stored

**Stored** (deterministic SQLite reference knowledge):

- messages, signals, message families, enums, registers, fault codes, protocol notes
- provenance fields supported by V1 (`source_location`, confidence, etc.)
- import metadata (`generated_by`, `generated_at`, content fingerprint)

**Not stored** as MCP-readable raw content:

- entire private PDFs or spreadsheets
- unrestricted original document bytes
- arbitrary file download endpoints

MCP exposes **metadata** (`list_reference_sources`, `inspect_reference_source`) and
**normalized imported knowledge** (`search_reference_knowledge`, `lookup_reference_message`) only.

---

## 6. Verify the import

### CLI

```powershell
uv run canresearch reference source inspect motor_driver_manual
uv run canresearch reference search "motor speed"
uv run canresearch reference search "target rpm" --source motor_driver_manual --limit 10
```

`reference search` scans imported message names, signal names, descriptions, register names,
fault codes, and protocol notes. There is **no** separate CLI command for exact CAN-ID
lookup — use MCP `lookup_reference_message` for that.

### MCP (with connector running)

```text
list_reference_sources
inspect_reference_source(source_key="motor_driver_manual")
search_reference_knowledge(query="motor speed", source_key="motor_driver_manual")
lookup_reference_message(can_id=0x18705501, is_extended=true, source_key="motor_driver_manual")
```

`lookup_reference_message` accepts **`can_id`** (with optional `is_extended`) **or** **`pgn`**.
It returns exact message matches (with nested signals) and message-family pattern matches.

### Success checklist

- [ ] Original source registered (`reference source list`)
- [ ] `source_key` in bundle matches registry key exactly
- [ ] `reference bundle validate` — zero errors
- [ ] `reference bundle import` succeeds; `reference source inspect` shows non-zero counts
- [ ] `reference search` finds an expected term from the manual
- [ ] MCP `search_reference_knowledge` / `lookup_reference_message` return expected rows

---

## 7. What happens next — known-first research

Imported reference knowledge is not an isolated archive. It joins the known baseline:

```text
J1939 / ISOBUS catalogue          (reference import-j1939 / import-isobus-pdf)
        +
imported Reference Bundle knowledge
        +
registered DBC knowledge          (reference dbc register)
        +
confirmed local research          (<asset>_research.dbc)
        ↓
known baseline
        ↓
unknown / proprietary remainder
        ↓
can-signal-research Skill
```

During bus inventory, prefer MCP/CLI coverage and lookup tools before experimental
signal hunting. Details: [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md).

---

## 8. Example end-to-end session

Generic example — no licensed document contents.

```powershell
# 1. Register original (keep your real PDF local / gitignored)
uv run canresearch reference source add docs\private\db_series_manual.pdf `
  --key db_series_motor `
  --type oem `
  --visibility private `
  --vendor "Example Drives"

uv run canresearch reference source inspect db_series_motor

# 2. In ChatGPT with can-reference-builder:
#    - upload db_series_manual.pdf
#    - source_key: db_series_motor
#    - produce: db_series_motor_reference.json

# 3. Validate and import
uv run canresearch reference bundle validate db_series_motor_reference.json
uv run canresearch reference bundle import db_series_motor_reference.json

# 4. CLI verify
uv run canresearch reference search "target rpm"
uv run canresearch reference source inspect db_series_motor
```

MCP verify (ChatGPT with CAN Research connector):

```text
inspect_reference_source(source_key="db_series_motor")
search_reference_knowledge(query="target rpm", source_key="db_series_motor")
lookup_reference_message(can_id=<id from bundle>, is_extended=true, source_key="db_series_motor")
```

Optional: compare structure against `tests/fixtures/reference_bundles/db_series_driver_synthetic.json`.

---

## 9. Updating an existing source

| Situation | Recommended approach |
|-----------|---------------------|
| Newer revision of **same** manual | Keep **same `source_key`**; `reference source add` again (replaces stored original); new bundle; validate; import (replaces knowledge) |
| Corrected extraction / fixed normalized field | Same `source_key`; new bundle JSON; validate; re-import |
| **Different** document lineage (different OEM pack) | **New `source_key`**; register separately |
| Parallel variants you must keep simultaneously | Distinct keys (e.g. `motor_manual_2022`, `motor_manual_2025`) |

Record document revision in registry `--version` / `--date` and in bundle `generated_at` /
`generated_by`. Re-import **replaces** all normalized rows for that key — there is no
partial row-level update CLI.

If the original file path changes, re-run `reference source add` with the same key — the
registry stores a managed copy under `{data_dir}/reference_sources/`.

---

## 10. Failure and recovery

| Problem | Typical cause | Recovery |
|---------|---------------|----------|
| `source_key ... is not registered` | Bundle validated before `reference source add` | Register source first, or use `--allow-unregistered` only for dry-run |
| `source_key` mismatch | Bundle key ≠ registry key | Fix bundle `source_key` to match registration exactly |
| Invalid bundle schema | Malformed JSON / wrong `schema_version` | Fix JSON; must be `schema_version: 1` |
| `signal_overlap` error | Overlapping bit ranges in one message | Fix bundle; do not silently merge signals |
| `enum_reference` error | `enum_key` missing from `enums` | Add enum definition or remove reference |
| `duplicate_can_id` error | Two messages claim same ID | Split sources or fix extraction |
| Uncertain Motorola / DBC bit layout | Source uses DBC notation ambiguously | Omit `start_bit` or flag in protocol note; do not guess |
| Missing scale/unit warnings | Source incomplete | Import may proceed; note uncertainty in research |
| Manual describes **ID family** not exact ID | Patterned addresses | Use `message_families` with `pattern` + `mask` — see [REFERENCE_BUNDLE_FORMAT.md](REFERENCE_BUNDLE_FORMAT.md) |
| Construct not representable in V1 | Tables the contract cannot model faithfully | Preserve fact in `protocol_notes`; report gap — **no lossy mapping** |

**Validator discipline:** if validation fails, fix the normalized representation or
re-run can-reference-builder. **Do not alter source facts** merely to pass validation.

---

## 11. Privacy and licensing

- Default uncertain material to **`private`** visibility
- Licensed SAE/ISO/OEM **originals** stay local — never commit to Git or Skill packages
- Private raw documents are **not** exposed through MCP (metadata and normalized knowledge only)
- Bundle JSON containing proprietary definitions is also **private** unless you explicitly
  have rights to redistribute it
- Public/redistributable material may use `public` visibility where licence permits

Full policy context: [REFERENCE_DATA.md](REFERENCE_DATA.md#public-vs-private-material).

---

## Quick command reference

```powershell
uv run canresearch reference source add <file> --key <key> [--type oem] [--visibility private]
uv run canresearch reference source list
uv run canresearch reference source inspect <key>
uv run canresearch reference bundle validate <bundle.json>
uv run canresearch reference bundle import <bundle.json>
uv run canresearch reference search "<query>" [--source <key>]
```

Discover all reference commands:

```powershell
uv run canresearch reference --help
```
