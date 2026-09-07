---
name: can-reference-builder
description: >-
  Convert user-owned CAN/J1939/ISOBUS/OEM reference material into CAN Research Reference Bundle V1 JSON. Use when the user provides PDFs, manuals, spreadsheets, CSV, DBC-derived notes, protocol tables, screenshots, or other manufacturer documentation and wants that knowledge structured for CAN Research, validated for provenance, or prepared for reference bundle import. Preserve source facts and uncertainty; never invent missing protocol details or redistribute licensed source material.
---

# CAN reference builder

Convert messy reference material into the stable CAN Research normalized reference contract.

**Boundary:** interpret source material generatively; do not redesign CAN Research storage. The output contract is the integration point.

When starting a **new** reference conversion or import on **Windows**, proactively suggest
the **Downloads staging convention** — see
[reference-ingest-staging.md](references/reference-ingest-staging.md).

## Required workflow

```text
0. STAGE (Windows)      Downloads folder — original + output JSON together (recommended)
1. IDENTIFY SOURCE       establish source_key + source type/visibility if known
2. READ SOURCE           inspect text, tables, diagrams and page context
3. MAP KNOWLEDGE         messages / signals / families / registers / faults / notes / enums
4. PRESERVE PROVENANCE   source_location on every object where supported
5. MARK UNCERTAINTY      omit unknown fields; use confidence only when useful
6. CHECK STRUCTURE       apply Reference Bundle V1 rules
7. OUTPUT BUNDLE         valid JSON, schema_version=1, matching source_key
8. HANDOFF               validate/import through CAN Research CLI — see reference-ingest-staging.md
```

## Source handling rules

- Treat uploaded/source documents as authoritative for extraction. Do not silently correct them with general knowledge.
- Preserve terminology used by the source unless a normalized field requires a canonical representation.
- Never invent CAN IDs, PGNs, bit positions, byte order, scaling, units, enums, register addresses, timing, or provenance.
- If a source is ambiguous, retain partial knowledge and explain the ambiguity separately.
- Prefer native document understanding, including rendered page images/tables, over OCR. Use OCR only as a last resort.
- Never include copyrighted source text beyond what is needed to identify/describe a normalized fact.
- Never package or reproduce licensed/private source documents inside the Skill or bundle.

## Source classification

Keep these axes separate:

**source_type:** `standard`, `oem`, `supplier`, `user_dbc`, `user_document`, `research`, `other`

**visibility:** `public`, `private`, `licensed`

Default uncertain material to **private**. **Public download ≠ public redistribution** — ISO/ISOBUS exports from public websites are often still **licensed** (`source_type: standard`, `visibility: licensed`). Licensed originals and derived bundles stay in the private managed area; do not commit them.

## Extraction model

Use the object that best fits the source. Do not force all knowledge into PGN/SPN form.

- **messages** — exact CAN identifiers or J1939/ISOBUS PGN-level definitions (`can_id` optional when SA/DA is runtime-dependent).
- **signals** — bit/byte fields inside exact messages.
- **message_families** — masked/patterned IDs such as `0x187055??`.
- **enums** — value-to-meaning mappings used by signals/registers.
- **registers** — vendor parameter/register protocols.
- **fault_codes** — diagnostic/status code tables.
- **protocol_notes** — bitrate, periods, timeouts, checksum rules, heartbeat behaviour, command/feedback relationships, operational notes.

**PGN-only standards:** ISO 11783 / J1939 exports often define PGNs without a fixed 29-bit CAN ID. Preserve `pgn`, DLC, priority, timing, and signals where known. **Do not invent** source/destination addresses or synthesize a CAN ID to silence validator warnings. Repeated `no exact CAN ID` warnings on standard PGN-level sources are expected and do not block import.

**Mixed vendor exports:** Inspect source/document/reference columns before grouping rows. Scope deliberately (e.g. ISO 11783 PGN/SPN only from a multi-CSV ZIP). Do not treat J1939DA pointer rows as full signal layouts. State clearly what was included and excluded.

**Auxiliary tables beyond V1:** Manufacturer IDs, NAME functions, industry groups, AEF tables, and similar data may not fit Reference Bundle V1. Do **not** dump thousands of rows into `protocol_notes`. Report the contract gap; note candidate future structured types.

**SQLite storage limits:** Numeric `minimum` / `maximum` / `default` fields must fit signed 64-bit SQLite INTEGER. If the source states a larger value (e.g. `0xFFFFFFFFFFFFFFFF`), omit the numeric field and preserve the fact in `description` or provenance — never clip or invent a smaller range.

Read [reference-bundle-v1.md](references/reference-bundle-v1.md) before producing a bundle. Use [reference-bundle-v1.schema.json](references/reference-bundle-v1.schema.json) as the machine-readable shape.

## Bit-layout discipline

- `start_bit` is a normalized bit index used by CAN Research validation.
- Do not copy DBC Motorola sawtooth start-bit semantics blindly into the bundle. If the source uses DBC notation and the mapping is uncertain, flag it instead of guessing.
- Never create overlapping signals unless the source explicitly defines a multiplexed/overlaid protocol and the current V1 contract can represent it safely. Otherwise record the ambiguity in notes and omit the conflicting normalized field.
- Preserve byte order explicitly when known: `0`/`motorola` or `1`/`intel`.
- Preserve signedness explicitly when known: `signed`, `unsigned`, or `unknown`.

## Message-family discipline

Represent patterned IDs with `pattern` + `mask`; do not expand them into guessed exact IDs.

Example intent:

```json
{
  "key": "status_reply",
  "name": "Status Reply",
  "pattern": "0x18700055",
  "mask": "0xFFFF00FF",
  "variable_field": "node_id",
  "variable_role": "source"
}
```

CAN Research matches deterministically; the AI does not silently rewrite IDs.

## Provenance

Attach `source_location` wherever the source supports it:

```json
{"page": 26, "section": "Status Data", "table": "Motor Status"}
```

Partial provenance is valid. Never fabricate page, section, or table identifiers.

## Confidence and incomplete knowledge

Incomplete but useful knowledge is expected.

Prefer:

```text
known bit position + unknown factor
```

over inventing a factor to make the object look complete.

Use `confidence` only as a qualitative extraction confidence when it helps (`low`, `medium`, `high`). Do not use `confirmed` merely because text was extracted successfully; semantic correctness may still be uncertain.

## Output

Produce a single Reference Bundle V1 JSON object. When the environment supports file creation, prefer a file named `<source_key>_reference.json`; otherwise provide one JSON code block.

Before handing off, check:

- `schema_version` is `1`.
- `source_key` exactly matches the registered source key supplied by the user.
- all object keys are stable and unique within their category.
- exact message CAN IDs are not duplicated.
- signal ranges do not unintentionally overlap.
- enum references exist.
- masks/patterns are valid 29-bit CAN values.
- no source fact has been invented.
- provenance is retained where available.

## CAN Research handoff

After bundle creation, guide the user through validate/import. On Windows, confirm **PowerShell vs CMD** before emitting paths — see [reference-ingest-staging.md](references/reference-ingest-staging.md). Prefer the user's **exact path** (e.g. `K:\Downloads\...`) over `%USERPROFILE%` assumptions.

```powershell
uv run canresearch reference bundle validate "$env:USERPROFILE\Downloads\<source_key>_reference.json"
uv run canresearch reference bundle import "$env:USERPROFILE\Downloads\<source_key>_reference.json"
uv run canresearch reference search "<known term>"
```

Command Prompt equivalent uses `%USERPROFILE%\Downloads\...` — not PowerShell `$env:` syntax.

Public workflow reference: [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md)

The Skill must **not** call import or modify the database directly.

If the CAN Research MCP connector is available, verification may use:

- `list_reference_sources`
- `inspect_reference_source`
- `search_reference_knowledge`
- `lookup_reference_message`

Do not expose raw private document files through MCP.

## Escalation

If validation reports structural errors, repair only the normalized bundle. Do not alter source facts simply to satisfy validation.

If the V1 contract cannot faithfully represent an important source construct, report the gap explicitly and preserve the original fact in a protocol note instead of inventing a lossy mapping.

## References

- [reference-ingest-staging.md](references/reference-ingest-staging.md) — Windows Downloads staging + validate/import
- [REFERENCE_ONBOARDING.md](../../../docs/REFERENCE_ONBOARDING.md) — canonical public operator workflow
- [reference-bundle-v1.md](references/reference-bundle-v1.md) — normalized contract and validation guidance
- [reference-bundle-v1.schema.json](references/reference-bundle-v1.schema.json) — current machine-readable schema snapshot
- [extraction-patterns.md](references/extraction-patterns.md) — how to map common document shapes
- [quality-and-provenance.md](references/quality-and-provenance.md) — uncertainty, licensing and source-trust rules
