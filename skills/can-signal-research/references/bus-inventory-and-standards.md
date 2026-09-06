# Bus inventory and standards-first analysis

For a new vehicle or machine capture, **do not treat every frame as proprietary**.

Research effort should focus on what remains after standards and local knowledge are applied.

## Traffic layering

```text
Observed bus
  → standards-backed traffic (J1939 / ISOBUS reference catalogue)
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
| Standards-backed messages | Matched reference catalogue (PGN/SPN) |
| Locally recognised messages | Registered DBC exact match + confirmed research / layout match |
| Partially recognised | DBC PGN address-variant, DLC mismatch, or conflicting definitions |
| Unknown / proprietary messages | Research targets |
| High-value unknowns | Periodic, stable layout, operator intent, experiment potential |

Example framing:

> 847 frames, 42 unique IDs — 28 IDs reference-backed J1939, 6 matched prior research,
> **8 proprietary IDs** worth investigation. Top priority: `0x18667217` (operator changed fan RPM).

## ISOBUS / ISO 11783

Where the reference catalogue includes ISOBUS DDI entries, apply the same known-first
discipline as J1939. Do not skip reference lookup because traffic “looks proprietary.”

## When to stop inventory and start research

Move to proprietary hypothesis work when:

- Unknown IDs are identified and prioritised
- Standards-backed traffic is accounted for (not re-discovered experimentally)
- Asset scope is clear
- Operator intent names a signal class or message

Do not rank bit changes on the whole bus before this separation.
