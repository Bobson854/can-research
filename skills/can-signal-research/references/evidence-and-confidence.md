# Evidence and confidence

Language rules for reporting proprietary signal research. All **measurements** come from
CAN Research MCP/core; all **confidence labels** are interpretive and must be honest.

## Confidence levels

| Level | Operator-facing meaning | Agent may do | Agent must not do |
|-------|-------------------------|--------------|-------------------|
| **possible** | One window consistent with hypothesis | Suggest follow-up test | Call it confirmed |
| **likely** | Repeatable pattern across cycles/windows | Propose candidate fields | Write to research DBC |
| **high confidence** | Strong vs alternatives; physically plausible | Strong proposal + CLI path | Skip human review |
| **confirmed** | Durable asset knowledge | Report only after CLI confirm | Assign via MCP |

**Confirmed** requires explicit human approval through CLI:

```text
research candidate review → research candidate confirm
```

MCP tools are read-only for candidates (`list_research_candidates`, `preview_research_dbc`, …).

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

## Reporting template

When presenting a candidate to the operator:

```markdown
### Candidate (likely | high confidence — not confirmed)

- **Asset:** <asset_key>
- **Intent:** <what we searched for>
- **CAN ID:** 0x… (extended: yes/no)
- **Field:** start bit …, length …, … endian, … signed
- **Observed behaviour:** <plain language>
- **Evidence:** <2–4 bullet points from deterministic tools>
- **Alternatives ruled out:** <brief>
- **Next test (if needed):** <single physical action>
- **To confirm:** CLI `research candidate confirm …` after your review
```

## Label sources distinctly

| Source | How to describe |
|--------|-----------------|
| J1939 / ISOBUS reference | “Documented in reference catalogue (PGN/SPN …)” |
| `<asset>_standard.dbc` | “Reference-backed standard signal” |
| Confirmed research DBC | “Confirmed proprietary signal (CLI confirmed)” |
| MCP candidate / inference | “Proposed candidate — not confirmed” |
| Generative guess | “Hypothesis only — needs experiment” |

Never merge these labels in prose.

## Inference guardrails

- Do not infer scale from a single sample unless anchors support it.
- Do not treat correlation as causation across unrelated IDs.
- Do not assume Intel endian because “most DBCs use Intel” — test.
- Do not promote **possible** to **likely** without a second window or repeat cycle.
- Do not promote **likely** to **high confidence** if a plausible alternative was not tested.

## GPS / contextual hints

Geographic hints (city, region, “near Murray Bridge”) are **ranking aids**, not proof.

Acceptable: “This 32-bit big-endian microdegree interpretation places the receiver within ~15 km of your hint at rest.”

Not acceptable: “This is definitely the GPS encoding” without repeatability and human confirm.

## Stored session caveat

Sessions captured before WebSocket timestamp fixes may have incorrect absolute times.
Prefer **within-session** ordering and window deltas for evidence; do not rely on
1970-era absolute timestamps in old JSONL without checking capture date.
