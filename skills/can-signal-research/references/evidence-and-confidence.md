# Evidence and confidence

Language rules for reporting proprietary signal research. All **measurements** come from
CAN Research MCP/core; all **confidence labels** are interpretive and must be honest.

## Granular confidence dimensions

Beyond encoding vs semantic, report **separate dimensions** when they diverge:

| Dimension | Examples |
|-----------|----------|
| Field boundary | Start bit, length |
| Byte order | Intel / Motorola |
| Signedness | Signed / unsigned |
| Factor / offset | Scale plausibility |
| Unit | m, deg, rpm, L/ha |
| Semantic class | altitude-like, RPM-like, rate-like |
| Exact meaning | Fan_RPM vs Pump_RPM |

Example:

> Structure: **high** — 16-bit Intel unsigned, 0–2000 plausible.
> Semantics: **medium** — rotational-speed-like; exact role not discriminated.

A valid reverse-engineering outcome may have **high structure, medium exact meaning**.

## Two confidence axes (summary)

Split every candidate hypothesis into **encoding** and **semantic** confidence.

| Axis | What it judges | Typical evidence |
|------|----------------|----------------|
| **Encoding confidence** | Bit start, length, endian, signedness, factor, offset | `preview_candidate_values`, stable decode across frames, discriminated alternatives |
| **Semantic confidence** | What the decoded quantity *means* (altitude vs pressure vs command) | Physical/contextual plausibility, repeatability, experiment windows, domain fit |

They are **independent**. You can have **high encoding confidence** and **medium semantic
confidence** — e.g. a stable uint16 × 0.01 that decodes to 355.51 (likely course in GNSS
context, but could be another angular quantity without further evidence).

### Example report

```markdown
### Candidate (encoding: high · semantic: medium — not confirmed)

- **CAN ID:** 0x18667117
- **Field:** start bit 32, length 16, little-endian, unsigned
- **Factor:** 0.01
- **Decoded samples:** 355.51, …
- **Encoding confidence:** high — stable width/endian/factor across frames; alternatives tested
- **Semantic hypothesis:** course/heading (degrees)
- **Semantic confidence:** medium — plausible for GNSS bench context; not discriminated from all angular fields
- **Evidence:** preview_candidate_values; contextual plausibility at rest
- **Next test:** short displacement with known heading change (only if ambiguity remains)
- **To confirm:** CLI after your review
```

## Overall confidence levels

Map encoding + semantic evidence to operator-facing overall labels:

| Level | Operator-facing meaning | Agent may do | Agent must not do |
|-------|-------------------------|--------------|-------------------|
| **possible** | One window or weak semantic fit | Suggest passive validation or follow-up test | Call it confirmed |
| **likely** | Repeatable encoding or consistent decode pattern | Propose candidate fields | Write to research DBC |
| **high confidence** | Strong encoding **and/or** strong semantic fit vs alternatives | Strong proposal + CLI path | Skip human review |
| **confirmed** | Durable asset knowledge | Report only after CLI confirm | Assign via MCP |

**Confirmed** requires explicit human approval through CLI:

```text
research candidate review → research candidate confirm
```

MCP tools are read-only for candidates (`list_research_candidates`, `preview_research_dbc`, …).

### Promotion rules

- Do not promote **possible → likely** without a second frame set, repeat cycle, or successful `preview_candidate_values` sweep.
- Do not promote **likely → high confidence** on semantics alone if encoding alternatives remain untested.
- Do not promote any level to **confirmed** without CLI — ever.

## Evidence types (deterministic sources)

Use MCP outputs to support claims:

| Evidence | Typical MCP / core source |
|----------|---------------------------|
| Repeatability | `compare_experiment_windows`, `analyze_repeated_action` |
| Baseline stability | Window compare at unchanged physical state |
| Direction / sign | Opposing experiment windows (left vs right) |
| Monotonicity | Ordered monotonic experiment marks |
| Field boundaries | `correlate_candidate_field`, `preview_candidate_values` |
| Endian / signedness | Value plausibility + `preview_candidate_values` sweeps |
| Scaling | Known anchor points (centre ≈ 0, contextual GPS hint) |
| Timing | Session timestamps; frame ordering in analysis |
| Independence | Unrelated operator action windows unchanged |
| Counter / checksum | `detect_counters`, `detect_checksums` (exclude from primary signal unless target) |

## Passive validation before physical tests

When you hypothesize a field layout:

1. Call **`preview_candidate_values`** on available session or capture data.
2. Check decoded values against **physical and contextual plausibility** (speed near zero at rest, lat/lon near operator hint, etc.).
3. Adjust **encoding confidence** from decode stability; adjust **semantic confidence** from domain fit.
4. Request a physical experiment **only** when passive validation leaves material ambiguity.

Prefer stored-session validation over asking the operator to manipulate the machine.

## Reporting template

When presenting a candidate to the operator:

```markdown
### Candidate (overall: likely | high — not confirmed)

- **Asset:** <asset_key>
- **Intent:** <what we searched for>
- **CAN ID:** 0x… (extended: yes/no)
- **Field:** start bit …, length …, … endian, … signed, factor …
- **Encoding confidence:** <possible | likely | high> — <one line why>
- **Semantic hypothesis:** <plain language name>
- **Semantic confidence:** <possible | likely | high> — <one line why>
- **Observed behaviour:** <plain language>
- **Evidence:** <2–4 bullet points from deterministic tools>
- **Alternatives ruled out:** <brief>
- **Next test (if needed):** <single physical action or passive check>
- **To confirm:** CLI `research candidate confirm …` after your review
```

Keep operator-facing text concise — omit rejected candidates unless asked.

## Label sources distinctly

| Source | How to describe |
|--------|-----------------|
| J1939 / ISOBUS reference | “Documented in reference catalogue (PGN/SPN …)” |
| `<asset>_standard.dbc` | “Reference-backed standard signal” |
| Confirmed research DBC | “Confirmed proprietary signal (CLI confirmed)” |
| MCP candidate / inference | “Proposed candidate — not confirmed” |
| Generative guess | Hypothesis only — needs validation |
| External / web | External evidence — cite purpose |
| AI inference | AI inference — not CAN-measured |

Never merge these labels in prose.

## Field width and ranker caution

- Do not shrink field width because observed values fit a smaller type under current conditions.
- Do not trust activity rankers alone after a clean controlled experiment — see [experiment-evidence.md](experiment-evidence.md).

## Inference guardrails

- Do not infer scale from a single sample unless anchors support it.
- Do not treat correlation as causation across unrelated IDs.
- Do not assume Intel endian because “most DBCs use Intel” — test with `preview_candidate_values`.
- Do not treat operator machine type as proof of signal semantics.
- Do not promote **possible** to **likely** without a second window or repeat cycle.
- Do not promote **likely** to **high confidence** if a plausible alternative was not tested.

## GPS / contextual hints

Geographic hints (city, region, “near Murray Bridge”) and machine-type context are
**ranking aids**, not proof.

Acceptable: “Encoding high — int32 LE × 1e-7 decodes to coordinates within ~15 km of your hint. Semantic: likely lat/lon given GNSS context; not confirmed.”

Not acceptable: “This is definitely the GPS latitude signal” without repeatability and human confirm.

## Stored session caveat

Sessions captured before WebSocket timestamp fixes may have incorrect absolute times.
Prefer **within-session** ordering and window deltas for evidence; do not rely on
1970-era absolute timestamps in old JSONL without checking capture date.

## Self-evaluation (evidence quality)

A strong run typically shows:

- Encoding alternatives tested before semantic commitment
- `preview_candidate_values` used when a field layout is hypothesized
- Semantic claims downgraded when context alone would be the only evidence
- No **confirmed** label without CLI
