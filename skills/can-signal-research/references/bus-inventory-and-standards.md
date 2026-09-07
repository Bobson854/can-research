# Bus inventory and standards-first analysis

For a new vehicle or machine capture, **do not treat every frame as proprietary**.

Research effort should focus on what remains after standards and local knowledge are applied.

## Traffic layering

```text
Observed bus
  → standards-backed traffic (J1939 / ISOBUS reference catalogue)
  → imported reference-bundle knowledge (normalized bundles per source_key)
  → locally known traffic (confirmed DBC, prior research, layout fingerprints)
  → genuinely unknown / proprietary traffic
```

On a tractor, much of the bus is often explainable from J1939. Proprietary work targets the
**remainder**.

## First-pass inventory (MCP)

After preflight and capture (or on stored session):

| Step | Tools |
|------|-------|
| Session overview | `get_session`, `analyze_session` |
| J1939 classification | `analyze_session` — observed PGNs, reference matches |
| **Imported bundle lookup** | `lookup_reference_message` (by PGN or CAN ID), `search_reference_knowledge`, `list_reference_sources`, `inspect_reference_source` |
| Node / address picture | `list_session_nodes`, `inspect_transport` if needed |
| Reference decode | `decode_session`, `lookup_pgn`, `lookup_spn` |
| Standard DBC preview | `build_session_dbc_preview` |
| **Registered DBC library** | `list_dbc_sources` — manifest + asset `*_standard.dbc` / `*_research.dbc` |
| **DBC session coverage** | `analyze_dbc_coverage` — covered / partial / unknown + `known_first` lists |
| DBC message lookup | `lookup_dbc_message`, `lookup_dbc_signal` |
| Confirmed proprietary | `list_research_candidates`, `preview_research_dbc` |
| Activity on unknown IDs | `analyze_can_id_activity` |

## Coverage summary (report to operator)

Produce a concise bus picture:

| Metric | Meaning |
|--------|---------|
| Total observed messages / unique CAN IDs | Bus size |
| Standards-backed messages | Matched J1939/ISOBUS **catalogue** (PGN/SPN/DDI) |
| Bundle-backed messages | Matched **imported reference bundle** (`lookup_reference_message`, `search_reference_knowledge`) |
| Locally recognised messages | Registered DBC exact match + confirmed research / layout match |
| Partially recognised | DBC PGN address-variant, DLC mismatch, or conflicting definitions |
| Unknown / proprietary messages | Research targets — only after catalogue **and** imported bundle checks |
| High-value unknowns | Periodic, stable layout, operator intent, experiment potential |

Example framing:

> 847 frames, 42 unique IDs — 28 IDs reference-backed J1939, 6 matched prior research,
> **8 proprietary IDs** worth investigation. Top priority: `0x18667217` (operator changed fan RPM).

## ISOBUS / ISO 11783

Apply known-first discipline for both the **deterministic catalogue** and **imported reference bundles** (PGN-level ISOBUS Parameters exports are common). For each observed PGN:

1. `lookup_pgn` / catalogue decode
2. `lookup_reference_message(pgn=...)` across registered bundle sources
3. `search_reference_knowledge` when semantic names help

Do not label a PGN proprietary until both catalogue and relevant imported bundle sources have been checked.

## When to stop inventory and start research

Move to proprietary hypothesis work when:

- Unknown IDs are identified and prioritised
- Standards-backed traffic is accounted for (not re-discovered experimentally)
- Asset scope is clear
- Operator intent names a signal class or message

Do not rank bit changes on the whole bus before this separation.
