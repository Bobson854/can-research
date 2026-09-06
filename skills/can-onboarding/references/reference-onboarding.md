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

## Supporting document flow (Reference Bundle V1)

Follow [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md).

1. Register original:

```powershell
uv run canresearch reference source add path\to\manual.pdf --key my_manual --visibility private
uv run canresearch reference source list
uv run canresearch reference source inspect my_manual
```

2. Hand the original document plus exact `source_key` to **can-reference-builder**.

3. Validate and import its output (`<source_key>_reference.json`):

```powershell
uv run canresearch reference bundle validate my_manual_reference.json
uv run canresearch reference bundle import my_manual_reference.json
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
