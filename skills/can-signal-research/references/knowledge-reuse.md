# Reusing local knowledge

Existing confirmed DBCs and prior research are **input knowledge**, not only output files.

Search available workspace/project DBCs and confirmed research **before** treating a message
as completely unknown.

## Reuse creates hypotheses — never silent copies

Compare new traffic against existing knowledge using:

- Signal and whole-message layout
- Field width, start bit, byte order, signedness
- Scaling, units, typical ranges, update rate
- Neighbouring signal structure
- Manufacturer / controller / asset family
- Previously observed CAN IDs and PGNs

## Message-layout fingerprints

A known decode may apply when a **similar payload** appears at a different address or CAN ID:

- Same byte lengths and periodicity
- Same static regions and changing regions
- Same factor/endian producing plausible values in new context

Propose: “Layout matches `<source>` — verify before confirming.”

## MCP sources

| Source | Tools |
|--------|-------|
| Confirmed candidates | `list_research_candidates`, `get_research_candidate` |
| Research DBC preview | `preview_research_dbc` |
| Standard DBC preview | `build_session_dbc_preview` |
| Asset context | `get_asset`, `list_asset_nodes` |
| Reference catalogue | `lookup_pgn`, `lookup_spn` |
| **Imported reference bundles** | `list_reference_sources`, `lookup_reference_message`, `search_reference_knowledge`, `inspect_reference_source` |

Also consider DBC files in the workspace (if the host can read them) as **hypothesis
generators** — always validate with MCP on the current session.

## Provenance (always retain)

| Label | Meaning |
|-------|---------|
| Source DBC | Named file or asset DBC that suggested the layout |
| Prior session | Session ID where layout was seen |
| Standard / catalogue | PGN/SPN/DDI from deterministic catalogue importers |
| **Reference bundle** | Normalized bundle import (`lookup_reference_message`, `search_reference_knowledge`) |
| Operator confirmation | CLI-confirmed research candidate |
| Inferred / contextual match | Layout or semantic similarity — not confirmed |

Never merge provenance labels in prose.

## Persisted catalogue (future-facing)

Confirmed results should become searchable **proprietary-signal catalogue** entries (like the
J1939 reference catalogue): asset, CAN ID, layout, semantic class, factor/offset/unit,
range, evidence, review status.

This is explicit persistent research knowledge in the workspace — **not** opaque model training.

MCP today: confirmed candidates + research DBC via CLI. Skill should describe intended
persistence loop even when automation is partial.
