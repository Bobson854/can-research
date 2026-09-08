# AI-guided proprietary CAN signal research

Design contract for using generative AI + MCP + a reusable Skill to make **proprietary
signal discovery** substantially easier than repeatedly writing one-off Python scripts.

**Differentiation:** The project does not compete on decoding documented J1939/ISOBUS
traffic. Reference-backed standard signals are a **known baseline**. The value is
guided discovery of **asset-specific proprietary remainder** with human-confirmed
research DBC output.

Related: [ARCHITECTURE.md](ARCHITECTURE.md) (module boundaries), [MCP_CONNECTION.md](MCP_CONNECTION.md)
(connector setup), Skill scaffold at `skills/can-signal-research/`.

---

## 1. Product objective

The target operator experience supports natural requests such as:

- “Find steering angle.”
- “Find PTO engaged.”
- “Find hydraulic pressure.”
- “Find the section status.”
- “This message contains latitude/longitude; determine the encoding.”

The operator should **not** need to know which MCP analysis tools to run, which CLI
commands to chain, or how to interpret raw bit-change dumps.

The generative agent should:

1. Understand the research intent.
2. Establish asset and session scope.
3. Account for existing reference and confirmed asset knowledge first.
4. Extract **passive and contextual evidence** from live or captured traffic.
5. Form ranked hypotheses; request a **physical experiment only when ambiguity remains material**.
6. Invoke MCP tools to capture deterministic evidence.
7. Interpret evidence, refine hypotheses, and propose candidates.
8. Stop at **human confirmation** before any signal becomes durable knowledge.

**Design rule:** *Passive inference first. Physical experiment second.*

---

## 2. Architecture boundary

```text
┌─────────────────────────────────────────────────────────────────┐
│ Human operator                                                  │
│  physical machine actions, safety, contextual hints, confirmation │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│ Generative model                                                │
│  hypothesis generation, physical reasoning, experiment planning,│
│  next-step selection, concise operator dialogue                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ uses Skill methodology
┌───────────────────────────────▼─────────────────────────────────┐
│ CAN research Skill (`skills/can-signal-research/`)              │
│  workflow orchestration, experiment patterns, evidence language │
└───────────────────────────────┬─────────────────────────────────┘
                                │ calls MCP tools
┌───────────────────────────────▼─────────────────────────────────┐
│ MCP (41 tools baseline — verify with `mcp tools`)               │
│  bounded access to deterministic capabilities                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ thin handlers
┌───────────────────────────────▼─────────────────────────────────┐
│ CAN Research core + cansub                                      │
│  parsing, capture, reference lookup, candidate analysis, DBC    │
└─────────────────────────────────────────────────────────────────┘
```

**Principle:** *Deterministic software measures facts; generative AI decides what
useful evidence to gather next — preferring passive analysis before physical experiments.*

| Layer | Responsibility | Must not |
|-------|----------------|----------|
| **Core / cansub** | Facts: frames, timestamps, decode, evidence metrics | Guess signal meaning; write research DBC without confirmation |
| **MCP** | Stable, bounded tool surface | CAN TX; autonomous confirmation; unbounded raw streams |
| **Skill** | Methodology, experiment design, dialogue style | Replace deterministic measurement; bypass human confirm |
| **Generative model** | Reasoning, planning, interpretation | Present inference as reference fact; auto-confirm candidates |
| **Human** | Physical actions, safety, final acceptance | Required to confirm candidates (CLI today) |

---

## 3. Known-first / unknown-second workflow

Required order — do **not** experimentally rediscover signals already accounted for by
trusted reference data or confirmed asset research DBC.

```text
CONNECT
  → DEFINE ASSET
  → OBSERVE TRAFFIC
  → APPLY REFERENCE DATA
  → APPLY EXISTING CONFIRMED ASSET KNOWLEDGE
  → BUILD KNOWN BASELINE
  → INVENTORY UNKNOWN REMAINDER
  → USER REQUESTS DATAPOINT
  → PASSIVE / CONTEXTUAL INFERENCE (MCP observation + reasoning)
  → RANKED HYPOTHESES
  → ENOUGH CONFIDENCE?
        yes → PROPOSE CANDIDATE
        no  → DESIGN SMALLEST DISCRIMINATING EXPERIMENT
  → MCP CAPTURE / EVENT / ANALYSIS (if experiment needed)
  → AI INTERPRETS EVIDENCE / REFINES HYPOTHESIS
  → PROPOSE CANDIDATE
  → HUMAN CONFIRMATION
  → RESEARCH DBC
```

Physical experiments are a **discriminating fallback**, not the default first step.
This matters especially on bench setups, stationary machinery, partially assembled
machines, unsafe/inconvenient-to-operate equipment, and passive historical captures.

### Passive evidence (before requesting operator action)

Exploit all available passive evidence first:

- Update rate and frame timing
- Byte/bit activity and field-width candidates
- Endian and signedness alternatives
- Common engineering scales (e.g. 0.01, 1e-7)
- Plausible physical ranges
- Static vs dynamic behaviour across samples
- Relationships between fields within a frame
- Relationships between related CAN IDs
- Known asset context
- Approximate location or state hints from the operator

Only request a physical experiment when it is expected to **materially reduce ambiguity**.

### Stage notes

| Stage | Deterministic inputs (MCP / CLI) | Generative role |
|-------|----------------------------------|-----------------|
| CONNECT | `get_cansub_device_status`, `get_cansub_channel_status`, `get_instance_info` | Verify correct backend when multiple connectors exist |
| DEFINE ASSET | `list_assets`, `get_asset`, session/asset association | Choose scope; never mix assets silently |
| OBSERVE TRAFFIC | `observe_live_traffic`, `start_live_capture` / `stop_live_capture` | Decide duration; avoid raw dumps to user |
| APPLY REFERENCE | `lookup_pgn`, `lookup_spn`, `analyze_session`, `decode_session` | Map documented traffic; exclude from proprietary search |
| APPLY CONFIRMED KNOWLEDGE | `list_research_candidates`, `preview_research_dbc`, asset DBC on disk | Exclude confirmed `(can_id, start_bit, …)` from search |
| APPLY DBC LIBRARY | `list_dbc_sources`, `inspect_dbc`, `analyze_dbc_coverage`, `lookup_dbc_message` | Known-first: quantify covered / partial / unknown IDs before proprietary work |
| BUILD KNOWN BASELINE | `build_session_dbc_preview`, DBC coverage summary | Explain what is already explained |
| INVENTORY UNKNOWN | `analyze_session`, `rank_signal_candidates`, proprietary PGN/ID lists | Prioritize unknown remainder |
| USER REQUEST | — | Classify intent; passive inference before experiment plan |
| PASSIVE INFERENCE | `observe_live_traffic`, payload inspection, contextual hints | Rank hypotheses; avoid unnecessary operator actions |
| EXPERIMENT (if needed) | `mark_experiment_event`, `compare_experiment_windows`, capture | Smallest discriminating test only |
| INTERPRET | `analyze_repeated_action`, `correlate_candidate_field`, `preview_candidate_values` | Rank hypotheses; never overclaim |
| PROPOSE | CLI `research candidate add` guidance (MCP read-only for candidates) | Structured candidate proposal |
| CONFIRM | **CLI only:** `research candidate review/confirm/reject` | Operator accepts/rejects |
| RESEARCH DBC | CLI `research dbc generate` | Only after confirmed candidates |

---

## 4. Asset scope and provenance

Keep **tractor / implement / controller** assets distinct.

- Proprietary knowledge from asset A must **not** silently apply to asset B.
- Candidates are asset-scoped in SQLite; frame identity is `(is_extended, can_id)`.
- Sessions link to assets explicitly (`session asset` / MCP asset tools).

### DBC model (unchanged)

| File | Contents | Source of truth |
|------|----------|-----------------|
| `<asset>_standard.dbc` | Reference-backed J1939 / ISOBUS signals | Imported catalogue + session observation |
| `<asset>_research.dbc` | Confirmed proprietary / reverse-engineered signals | **CLI-confirmed** candidates only |

A generative inference — even at “high confidence” — is **never** sufficient alone to
become a confirmed signal. MCP may **preview** research DBC; it does **not** write files
or confirm candidates.

---

## 5. Research intent classification

Initial **strategy classes** (not rigid protocol types). Used to select experiments and
interpretation heuristics.

| Class | Examples | Typical experiment bias |
|-------|----------|-------------------------|
| **boolean / discrete** | PTO engaged, switch, alarm bit | off → on → off |
| **centred analogue** | Steering angle, joystick neutral-centre | centre → left → centre → right → centre |
| **monotonic analogue** | Pressure, fill level, throttle | low → medium → high → return |
| **cyclic / rotational** | Wheel angle wrap, encoder | known positions, repeatable rotation |
| **position / coordinate** | GPS lat/lon, implement position | stationary baseline + known geography hint |
| **motion / speed** | Ground speed, RPM proxy | stationary → move → stop |
| **status / mode enumeration** | Section state, ECU mode | traverse modes systematically |
| **command** | Setpoint, request | observe response traffic after commanded action |
| **feedback** | Acknowledgement, measured response | pair with known command window |
| **unknown / general** | Unclassified request | start with ID ranking + cheap baseline |

The agent may blend classes (e.g. boolean PTO + monotonic hydraulic pressure) but should
**separate experiments** when one physical variable would confound another.

---

## 6. Experiment patterns

### General rules

- **Passive inference first** — exploit observation and context before moving machinery.
- Change **one physical variable at a time** where practical (when an experiment is needed).
- **Repeat** cheap experiments (centre → left → centre) to test repeatability.
- Prefer tests that **discriminate competing hypotheses** over broad data collection.
- If two candidates remain, design the **next experiment specifically to separate them**.
- Do **not** ask the operator for unnecessary actions.
- Use **event markers** (`mark_experiment_event`) at stable states before/after transitions.
- Operators may also use the **local capture marker companion** (`marker-companion.cmd`) during live capture for precise host-side timestamps without MCP round-trips. Companion markers set `origin=local_companion` and appear in the same `session_events` store. See [MARKER_COMPANION.md](MARKER_COMPANION.md).

### Pattern catalogue

**Boolean:** off → on → off (repeat when practical).

**Centred analogue:** centre → negative/left extreme → centre → positive/right extreme → centre.

**Monotonic analogue:** low → medium → high → return low.

**Rotational:** known positions or repeatable angular changes; note wrap behaviour.

**Motion:** stationary baseline → move → stop; compare windows.

**Coordinate / GPS:** stationary baseline → operator hint (e.g. approximate region) → motion
in useful directions if ambiguity remains. Contextual geography can collapse signedness,
scale, and field-width hypotheses **without** the operator supplying the exact encoding.

### MCP experiment control (passive)

Typical sequence:

1. `start_live_capture` (or use existing session).
2. Operator performs physical steps; agent requests “tell me when ready” at each stable state.
3. `mark_experiment_event` at each labelled state (`baseline_start`, `left_full`, …).
4. `stop_live_capture`.
5. `compare_experiment_windows` between labelled events.
6. Signal research tools on the resulting session.

**No CAN TX.** No bus injection. No autonomous machinery control.

### Failed and inconclusive experiments are still evidence

An experiment that **does not** confirm a hypothesis is not a wasted session. Record it.

| Outcome | What to preserve |
|---------|------------------|
| **Null result** | Baseline stable; candidate field did not change as predicted — narrows search space |
| **Ambiguous result** | Multiple fields moved; confounding action — informs next discriminating test |
| **Failed capture / setup** | Channel busy, wrong asset scope, missing markers — fix process, do not discard context |
| **Inconclusive ranking** | Tie between candidates — documents why another experiment is needed |

Use `mark_experiment_event` and session notes so later review can distinguish “not yet
known” from “tested and ruled out”. Do not discard sessions or omit negative results from
research reports — they prevent repeated dead ends and support recovery planning.

Label inconclusive outcomes as **hypothesis not supported** or **insufficient evidence**,
not as confirmed findings. See [PRODUCT_POSITIONING.md](PRODUCT_POSITIONING.md) for the
broader engineering culture around learning from failure.

---

## 7. Evidence / confidence model

The Skill uses qualitative confidence — not a hidden numeric score presented as fact.

| Level | Meaning | Typical requirements |
|-------|---------|----------------------|
| **possible** | Hypothesis consistent with one window | Single observation; weak repeatability |
| **likely** | Repeatable across cycles/windows | Direction/sign behaviour; stable field boundaries |
| **high confidence** | Strong discrimination vs alternatives | Independence from unrelated actions; physical plausibility |
| **confirmed** | Accepted into research DBC | **Explicit human CLI confirmation only** |

### Evidence types (deterministic and passive)

- Repeatability across repeated experiment cycles (when experiments are run)
- Baseline stability when the physical quantity is unchanged
- Direction / sign behaviour under opposing actions
- Monotonicity where expected
- Physical plausibility (range, units, rate limits)
- Candidate field boundaries (start bit, length, endianness, signedness)
- Scaling hints from known anchor values (only when supported by data)
- Timing relationship to related frames
- Independence from unrelated operator actions
- Known contextual anchors (e.g. approximate location for coordinate decoding)
- **Passive-only:** update rate, static payloads, cross-field structure, geographic plausibility

The Skill and agent must **never** disguise inference as reference-backed fact. Label
reference decode, confirmed DBC, and candidate inference distinctly in operator-facing text.

---

## 8. Agent interaction style

During an active experiment, **avoid long CAN-analysis dumps**.

Prefer:

> “Keep the wheels centred and tell me when ready.”

Over:

> “Here are 143 changing bit candidates…”

Run detailed analysis through MCP **internally**. Present to the operator:

- The **next useful physical instruction**
- Concise progress (what was learned, what remains ambiguous)
- Best candidate(s) with evidence summary
- Confidence level (possible / likely / high confidence — not “confirmed” until human says so)
- Any required follow-up test

When reporting candidates, use structured summaries (CAN ID, start bit, length, endian,
signedness, observed behaviour) — not raw hex walls unless the operator asks.

---

## 9. Canonical example: steering angle

**User:** “Find steering angle.”

**Agent workflow:**

1. **Known-first:** `get_instance_info` if needed; identify asset. Check reference decode
   and `<asset>_research.dbc` / confirmed candidates for existing steering-related signals.
2. If unknown, **observe** proprietary traffic (`observe_live_traffic` or capture while idle).
3. Attempt **passive inference** on stable traffic before asking the operator to move the wheel.
4. **Classify** as centred analogue; if passive evidence is insufficient, **instruct**
   operator: wheels centred → full left → centred → full right → centred. Mark events at
   each stable state.
5. **Capture** session (if experiment needed); `compare_experiment_windows` between baseline and extremes.
6. **Analyze** with `rank_signal_candidates`, `analyze_repeated_action`,
   `correlate_candidate_field`, `preview_candidate_values` as needed.
7. **Prefer** continuous signed fields with repeatable centre and opposing direction response.
8. If two candidates remain (e.g. 16-bit vs 32-bit, or adjacent IDs), design a **narrower
   position test** (e.g. half-left vs full-left) to discriminate.
9. **Propose** final CAN ID, start bit, length, endian, signedness; infer scale **only**
   when evidence supports it (known centre ≈ 0, known left/right sign).
10. **Human acceptance:** operator runs CLI `research candidate review` / `confirm` — not MCP.
11. After confirmation, research DBC generation is a normal CLI workflow.

---

## 10. Canonical example: GPS hint

**User:** “This frame contains latitude/longitude. Receiver is around Murray Bridge.”

**Agent workflow:**

1. Confirm frame is **not** already fully explained by reference or confirmed DBC.
2. Use contextual hint: Murray Bridge coordinates are **plausible anchors** for ranking
   decode hypotheses (signedness, field width, endian alternatives, common 1e-7 / 1e-6 scales).
3. Compare stationary vs motion windows if needed.
4. Rank candidates by geographic plausibility + temporal behaviour + repeatability.
5. Propose encoding; request human confirmation before research DBC.

This demonstrates that **contextual hints collapse the hypothesis space** without the
operator supplying the exact bit layout. Do **not** hard-code machine-specific answers
into the generic Skill — teach the **method**, not one bench result.

---

## 11. Scope controls (explicit exclusions)

Not in scope for this workflow milestone:

- Autonomous CAN transmission
- Arbitrary bus injection
- Automatic control of machinery
- Automatic confirmation of candidates (MCP or otherwise)
- Universal cross-asset knowledge sharing without explicit scope
- Central multi-instance routing
- Large new ML pipelines inside CAN Research core
- GUI development

The Skill orchestrates **passive research** and **human-guided physical experiments** only.

---

## 12. Development rule

When capability is missing, fix the **lowest correct layer**:

> If the Skill knows what experiment it wants to perform but cannot obtain the required
> deterministic evidence cleanly, **improve MCP/core**.

> If MCP already exposes the evidence but the agent chooses poor experiments or
> explanations, **improve the Skill**.

Examples:

| Symptom | Likely layer |
|---------|--------------|
| Cannot compare labelled windows reliably | Core / MCP (`compare_experiment_windows`) |
| Cannot preview candidate values over events | MCP (`preview_candidate_values`) |
| Agent asks for redundant physical steps | Skill (experiment patterns) |
| Agent presents 200 bit changes to the user | Skill (interaction style) |
| Agent confirms without human | Skill + process (forbidden) |

Do **not** add MCP tools in every milestone. Extend the 32-tool substrate only when a
deterministic measurement is genuinely missing and repeatedly needed.

---

## MCP substrate reference (current)

**Identity:** `get_instance_info`

**Live (passive):** `get_cansub_device_status`, `get_cansub_channel_status`,
`start_live_capture`, `stop_live_capture`, `observe_live_traffic`,
`mark_experiment_event`, `compare_experiment_windows`

**Sessions / reference:** `list_sessions`, `get_session`, `analyze_session`, `decode_session`,
`lookup_pgn`, `lookup_spn`, `list_assets`, `get_asset`, …

**Signal research:** `rank_signal_candidates`, `analyze_can_id_activity`,
`analyze_repeated_action`, `detect_counters`, `detect_checksums`, `correlate_candidate_field`

**Candidates (read-only):** `list_research_candidates`, `get_research_candidate`,
`list_candidate_evidence`, `preview_research_dbc`, `preview_candidate_values`,
`list_session_events`

**Human-only today:** candidate create/review/confirm/reject, research DBC file write.

See [README.md](../README.md) for the full tool list and CLI equivalents.

---

## First live bench validation

Early successful trial on the **Office** installation (September 2026). This validates
the **architecture direction** — not a finished autonomous reverse-engineering product.

### Environment

| Item | Value |
|------|-------|
| Installation | CAN Research - Office (`instance_key = office`) |
| Host OS | Windows |
| CANsub.2 | Channel 1 (Ethernet bench) |
| ChatGPT | `can-signal-research` Skill installed and available |
| MCP | CAN Research connector live; verify tool count with `mcp tools` (baseline **41**) |
| Mode | Passive observation only |
| CAN TX | None |
| Candidate confirmation | Not via MCP (CLI boundary preserved) |

### Initial live observation

| Metric | Result |
|--------|--------|
| Duration | 15 seconds |
| Frames | 171 |
| Unique CAN IDs | 5 |
| Traffic type | Proprietary PDU1-style |
| Reference catalogue | No matching entries for observed proprietary PGNs |

**Observed CAN IDs:**

- `0x18667017`
- `0x18667117`
- `0x18667217`
- `0x18667317`
- `0x18173201`

**Scope note:** The Office database had **no registered assets** during this trial, so
the full asset-scoped baseline / standard+research DBC workflow was **not** exercised.

### Important result

The Skill and model made **useful passive inferences** from traffic and operator context
**without** requiring hardware manipulation. This supports the **passive inference first**
design rule.

All findings below are **hypotheses** — high-confidence research inferences, **not yet
confirmed** candidates or DBC definitions.

### Passive inference example 1: GPS coordinates (hypothesis)

**CAN ID:** `0x18667017`

Observed 8-byte payloads were **consistent with** this **hypothesis**:

| Field | Hypothesis |
|-------|------------|
| Bytes 0–3 | Signed little-endian 32-bit latitude |
| Bytes 4–7 | Signed little-endian 32-bit longitude |
| Factor | 1e-7 degrees |
| Offset | 0 |

Example decodes were **geographically plausible** around Murray Bridge when the operator
supplied approximate regional context.

**Important distinctions:**

- Inference from payload structure + geographic context — **not** a lookup from the local
  standard reference catalogue
- Confidence assessed as **high** for the field layout and scale hypothesis
- Still **research knowledge** until explicit CLI candidate confirmation

### Passive inference example 2: GNSS companion frame (hypothesis)

**CAN ID:** `0x18667117`

Example payloads observed:

```text
10004957BE0F0705
32004857AE100705
31003955AE100705
```

**Best current passive hypothesis** (not confirmed):

| Bytes | Likely role | Confidence |
|-------|-------------|------------|
| 0–1 | Ground speed, little-endian uint16, factor ~0.01 m/s | **High** |
| 2–3 | Heading, little-endian uint16, factor ~0.01 degrees | **High** |
| 4–5 | Altitude or related GNSS analogue | **Medium** |
| 6 | Satellite count or GNSS quality | **Medium** |
| 7 | Fix / status enum | **Medium** |

These are **plausible** interpretations from passive samples and cross-frame context —
not confirmed signal definitions.

---

## Lessons from the first trial

- **MCP already exposes enough capability** for useful generative reasoning on proprietary traffic.
- The main current value is **orchestration and interpretation**, not adding more MCP tools.
- **Passive contextual inference** can identify useful proprietary field structure without operator action.
- **Physical experiments should be a discriminating fallback**, not the default first step.
- **Asset registration and scoping** remain important before the full known-baseline / DBC workflow can be validated end-to-end.
- **Concise operator interaction** remains a key design goal — the trial succeeded partly because the operator was not asked to move machinery unnecessarily.
- Inferred results must stay labelled as **hypothesis / likely / high confidence** until CLI confirmation; never as reference-backed fact or confirmed DBC content.

---

## Benchmark-driven Skill improvements

The first **asset-scoped** benchmark of the installed `can-signal-research` Skill against
the working Office MCP connector (September 2026) validated the architecture direction and
identified concrete Skill workflow improvements — implemented in `skills/can-signal-research/`.

| Gap observed | Skill improvement |
|--------------|-------------------|
| Capture started before channel health proven | **Mandatory live preflight** — `get_instance_info` → `get_cansub_*` → `observe_live_traffic` → frames confirmed before `start_live_capture` |
| WebSocket ownership confused with missing traffic | Explicit **`channel_rx_in_use`** handling — free the channel (e.g. webCAN on another channel), not “no bus traffic” |
| Weak asset/system framing at session start | **System-context intake** — short questions about what is connected; context as prior, not proof |
| Asset scope unclear on first scoped run | **Asset-scope assistance** — propose `asset_key` / type / display_name; MCP inspect only; CLI for create |
| Physical action requested too early | **Passive hypothesis validation** — `preview_candidate_values` on hypothesized fields before physical tests |
| Single confidence label too coarse | **Encoding vs semantic confidence** — separate bit/layout certainty from meaning certainty |
| Operator overload | Reinforced **concise interaction** — one context question, one physical step, concise evidence summary |

The benchmark methodology example (bench GNSS controller, proprietary IDs `0x18667017` /
`0x18667117`) is documented in the Skill as an **illustration only** — not portable CAN
knowledge for other controllers.

Skill self-evaluation checklist: see `skills/can-signal-research/SKILL.md` (self-evaluation section).

---

## CANsub.2 validation session — Skill V3 workbench behaviours

A subsequent real-world validation session (September 2026) refined the Skill toward an
**AI-assisted reverse-engineering workbench** — still passive-only, still CLI confirm boundary.

Key behaviours now in `skills/can-signal-research/` references:

| Theme | Skill guidance |
|-------|----------------|
| Standards-first | Bus inventory before proprietary bit-hunting; J1939/ISOBUS coverage summaries |
| Knowledge reuse | DBC/layout fingerprints; hypotheses with provenance — never silent copy |
| Contextual reasoning | Whole-field GNSS/sprayer interpretations; cross-field coherence; static setpoints |
| Field width | Do not over-shrink (16-bit speed looked 8-bit when stationary) |
| Granular confidence | Boundary, endian, signedness, class, exact meaning, factor — separate dimensions |
| Experiment evidence | Controlled fan RPM change outranked noisy GNSS in ranker; one cycle often enough |
| External research | Elevation, manuals, specs — labelled external evidence, purpose-driven only |
| Outputs | Markdown research report + provisional research DBC for viewer validation loop |
| Persistence | Confirmed catalogue as explicit workspace knowledge, not model memory |

Deterministic MCP/core unchanged; generative layer adds reasoning the rankers alone do not provide.
