---
name: can-reference-builder
description: >-
  Convert user-owned CAN/J1939/ISOBUS/OEM reference material into CAN Research Reference Bundle V1 JSON. Use when the user provides PDFs, manuals, spreadsheets, CSV, DBC-derived notes, protocol tables, screenshots, or other manufacturer documentation and wants that knowledge structured for CAN Research, validated for provenance, or prepared for reference bundle import. Preserve source facts and uncertainty; never invent missing protocol details or redistribute licensed source material.
---

# CAN reference builder

Convert messy reference material into the stable CAN Research normalized reference contract.

**Boundary:** interpret source material generatively; do not redesign CAN Research storage. The output contract is the integration point.

## Required workflow

```text
1. IDENTIFY SOURCE       establish source_key + source type/visibility if known
2. READ SOURCE           inspect text, tables, diagrams and page context
3. MAP KNOWLEDGE         messages / signals / families / registers / faults / notes / enums
4. PRESERVE PROVENANCE   source_location on every object where supported
5. MARK UNCERTAINTY      omit unknown fields; use confidence only when useful
6. CHECK STRUCTURE       apply Reference Bundle V1 rules
7. OUTPUT BUNDLE         valid JSON, schema_version=1, matching source_key
8. HANDOFF               validate/import through CAN Research CLI or onboarding workflow
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

Default uncertain material to **private**. Licensed material belongs in the private managed area even though visibility metadata remains `licensed`.

## Extraction model

Use the object that best fits the source. Do not force all knowledge into PGN/SPN form.

- **messages** — exact CAN identifiers or J1939 messages.
- **signals** — bit/byte fields inside exact messages.
- **message_families** — masked/patterned IDs such as `0x187055??`.
- **enums** — value-to-meaning mappings used by signals/registers.
- **registers** — vendor parameter/register protocols.
- **fault_codes** — diagnostic/status code tables.
- **protocol_notes** — bitrate, periods, timeouts, checksum rules, heartbeat behaviour, command/feedback relationships, operational notes.

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

After bundle creation, guide the user to run:

```powershell
uv run canresearch reference bundle validate <bundle.json>
uv run canresearch reference bundle import <bundle.json>
uv run canresearch reference search "<known term>"
```

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

- [reference-bundle-v1.md](references/reference-bundle-v1.md) — normalized contract and validation guidance
- [reference-bundle-v1.schema.json](references/reference-bundle-v1.schema.json) — current machine-readable schema snapshot
- [extraction-patterns.md](references/extraction-patterns.md) — how to map common document shapes
- [quality-and-provenance.md](references/quality-and-provenance.md) — uncertainty, licensing and source-trust rules
