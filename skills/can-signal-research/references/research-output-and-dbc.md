# Research output, DBC, and persistence

The workbench produces **useful artifacts**, not only chat text.

## Markdown research report (canonical)

Prefer **Markdown** as the versionable, diffable human record. Offer to produce or update
a report containing:

| Section | Content |
|---------|---------|
| Bus inventory | IDs, nodes, source addresses |
| Coverage | Standards-backed vs local vs unknown counts |
| J1939/ISOBUS | PGN/SPN coverage summary |
| Proprietary targets | IDs requiring research, priority |
| Candidates | Tables: ID, bits, raw/scaled range, confidence dimensions |
| Evidence / provenance | CAN, local, standard, operator, external, AI inference |
| Experiments | Controlled changes and window results |
| Unresolved questions | What would discriminate next |
| Confirmation status | candidate / reviewed / confirmed / operator-adjusted |

PDF may be generated from Markdown when a fixed shareable report is needed.

Keep chat concise; put detail in the report when the operator wants a durable record.

## Asset research DBC loop

Goal: a **working asset DBC** loadable in webCAN / SavvyCAN / CSS tooling for live validation.

```text
capture
  → infer (standards + local + proprietary)
  → preview research DBC (MCP) / CLI research dbc
  → load in viewer
  → visually validate scaling/naming
  → refine
  → CLI confirm
  → persist knowledge
```

### DBC contents (layers)

| Layer | Source | In research DBC? |
|-------|--------|-------------------|
| J1939/ISOBUS standard | Reference catalogue + session | Yes (preview) |
| Confirmed proprietary | CLI-confirmed candidates | Yes |
| High-confidence candidates | Not yet CLI-confirmed | **Provisional only** |

Do not pretend research candidates are confirmed.

### Provisional naming

Use clear non-production names until CLI confirm:

- `Research_0x18FF1234_Field_01`
- `Candidate_HydraulicPressure`
- `Likely_FanSpeed`

MCP: `preview_research_dbc`, `build_session_dbc_preview` (read-only preview).

CLI (operator): `uv run canresearch research dbc <asset-key>` after confirmations.

Separate **confirmed/production** DBC can follow later; research DBC is for iteration.

## Success criteria (practical)

A successful session may deliver:

- Likely signal boundaries, endian, signedness
- Approximate value/scaling and semantic **class**
- Confidence dimensions and evidence
- Viewer-ready provisional DBC

Final naming/scaling may be adjusted by the technician after testing — that is expected.

## Persisting learned knowledge

Confirmed results feed the proprietary-signal catalogue (candidates + research DBC + metadata):

- Asset / controller / manufacturer
- CAN ID, message layout, signal layout
- Semantic class/name, factor/offset/unit, expected range
- Source/evidence, confidence/review status

Explicit, inspectable storage — not “the AI remembered it.”

MCP inspect: `list_research_candidates`. Human boundary: CLI confirm.
