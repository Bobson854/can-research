# Reference onboarding

Canonical public workflow: [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md)

## Principle

Onboarding is not complete merely because the software runs. Load existing CAN knowledge before researching unknown traffic.

Inventory:

- DBC files
- J1939 / ISOBUS references
- OEM / supplier manuals
- signal spreadsheets / CSV
- protocol documents
- previous confirmed reverse engineering

## Source classification

Keep separate:

`source_type`: `standard`, `oem`, `supplier`, `user_dbc`, `user_document`, `research`, `other`

`visibility`: `public`, `private`, `licensed`

Default uncertain material to `private`. Licensed sources are stored in the private managed folder.

**Never commit** original private/licensed reference documents to the CAN Research repository.

## Reference ingest staging (Windows — recommended)

When the user is about to onboard a new OEM/supplier/manual reference on Windows, suggest
this **default staging workflow** before register/validate/import:

1. Place the **original** reference document in the user's **Downloads** folder.
2. Generate or save the normalized **Reference Bundle V1 JSON** (`<source_key>_reference.json`)
   into the **same Downloads** folder (via can-reference-builder).
3. Run **validate** and **import** while both files are together there — short, explicit
   paths are easy to paste into PowerShell.

```text
Reference ingest staging:
For simplicity on Windows, place both the original reference document and the generated
normalized JSON file in your Downloads folder before validation/import. Keeping them
together makes CLI paths predictable and easy to paste. The original document does not
need to be moved into the CAN Research repository after ingest.
```

This is the **recommended default**, not a hard technical requirement — another folder works
if paths are kept explicit. After successful ingest, `reference source add` retains a managed
copy under `{data_dir}/reference_sources/`; the Downloads copy can stay or be archived locally.
Do not add originals to the repo or Skill packages.

### Example commands (Downloads staging)

PowerShell (preferred — use `$env:USERPROFILE\Downloads`):

```powershell
uv run canresearch reference source add "$env:USERPROFILE\Downloads\db_series_manual.pdf" `
  --key db_series_motor --type oem --visibility private

# … can-reference-builder writes db_series_motor_reference.json to Downloads …

uv run canresearch reference bundle validate "$env:USERPROFILE\Downloads\db_series_motor_reference.json"
uv run canresearch reference bundle import "$env:USERPROFILE\Downloads\db_series_motor_reference.json"
uv run canresearch reference search "target rpm"
```

Explicit path form (when helpful):

```powershell
uv run canresearch reference source add C:\Users\Office\Downloads\db_series_manual.pdf `
  --key db_series_motor --type oem --visibility private
```

Command Prompt — use `%USERPROFILE%\Downloads` and `cd /d` when changing drives to the repo.

## Supporting document flow (Reference Bundle V1)

Follow [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md). On Windows, apply
**Reference ingest staging** (above) unless the user already has a deliberate layout.

1. Register original (from Downloads if using staging convention):

```powershell
uv run canresearch reference source add "$env:USERPROFILE\Downloads\my_manual.pdf" `
  --key my_manual --visibility private
uv run canresearch reference source list
uv run canresearch reference source inspect my_manual
```

2. Hand the original document plus exact `source_key` to **can-reference-builder** (save
   output JSON to the same Downloads folder).

3. Validate and import its output (`<source_key>_reference.json`):

```powershell
uv run canresearch reference bundle validate "$env:USERPROFILE\Downloads\my_manual_reference.json"
uv run canresearch reference bundle import "$env:USERPROFILE\Downloads\my_manual_reference.json"
uv run canresearch reference search "motor speed"
```

4. MCP verification:

- `list_reference_sources`
- `inspect_reference_source`
- `search_reference_knowledge`
- `lookup_reference_message`

The Skill must not write to the CAN Research database directly.

## Existing DBC (separate path)

```powershell
uv run canresearch reference dbc register --key supplier_baseline path\to\file.dbc [--asset my_asset]
uv run canresearch reference dbc list [--asset my_asset]
uv run canresearch reference dbc inspect supplier_baseline
uv run canresearch session dbc-coverage <session-id> [--asset my_asset]
```

MCP:

- `list_dbc_sources`
- `inspect_dbc`
- `lookup_dbc_message`
- `lookup_dbc_signal`
- `analyze_dbc_coverage`

## Structured J1939 / ISOBUS imports (catalogue path)

When the source matches the existing deterministic importers:

```powershell
uv run canresearch reference import-j1939 path\to\licensed-j1939-71.pdf
uv run canresearch reference import-isobus-pdf path\to\licensed-isobus-ddi.pdf
uv run canresearch reference validate
uv run canresearch reference stats
```

Keep licensed originals local; do not commit them.

## Known-first outcome

The desired state before signal research:

```text
observed traffic
+ J1939/ISOBUS catalogue
+ normalized reference bundles
+ registered DBCs
+ confirmed local research
→ known baseline
→ unknown remainder only
```
