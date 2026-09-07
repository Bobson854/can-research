# Reference onboarding

Canonical public workflow: [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md)

## Principle

Onboarding is not complete merely because the software runs. Load existing CAN knowledge before researching unknown traffic.

Inventory:

- DBC files
- J1939 / ISOBUS references (catalogue PDFs **or** ISOBUS Parameters CSV/XLSX/ZIP exports)
- OEM / supplier manuals
- signal spreadsheets / CSV
- protocol documents
- previous confirmed reverse engineering

ZIP/CSV/XLSX originals may be registered directly with `reference source add` before bundle conversion.

## Source classification

Keep separate:

`source_type`: `standard`, `oem`, `supplier`, `user_dbc`, `user_document`, `research`, `other`

`visibility`: `public`, `private`, `licensed`

Default uncertain material to `private`. Licensed sources are stored in the private managed folder.

**Never commit** original private/licensed reference documents to the CAN Research repository.

## Supporting document flow (Reference Bundle V1)

Onboarding verifies the pipeline; **can-reference-builder** owns conversion, staging, validate,
and import for each new document. See [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md).

1. Register original (if not already registered):

```powershell
uv run canresearch reference source add path\to\manual.pdf --key my_manual --visibility private
uv run canresearch reference source list
uv run canresearch reference source inspect my_manual
```

2. Hand the original plus exact `source_key` to **can-reference-builder** for bundle
   production, validate, and import.

3. Verify ingest worked:

```powershell
uv run canresearch reference source inspect <source_key>
uv run canresearch reference search "General Purpose Valve" --source <source_key>
```

Success means **non-zero imported counts** (messages, signals, etc.) **and** a known search term returns useful rows — not merely that validate/import exited without error.

MCP verification:

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
