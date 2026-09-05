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
4. Design a **minimal, discriminating** physical experiment plan.
5. Invoke MCP tools to capture deterministic evidence.
6. Interpret evidence, rank candidates, and propose next steps.
7. Stop at **human confirmation** before any signal becomes durable knowledge.

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
│ MCP (32 tools — stable substrate)                               │
│  bounded access to deterministic capabilities                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ thin handlers
┌───────────────────────────────▼─────────────────────────────────┐
│ CAN Research core + cansub                                      │
│  parsing, capture, reference lookup, candidate analysis, DBC    │
└─────────────────────────────────────────────────────────────────┘
```

**Principle:** *Deterministic software measures facts; generative AI decides what
useful experiment to perform next.*

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
  → AI DESIGNS EXPERIMENT
  → MCP CAPTURE / EVENT / ANALYSIS
  → AI INTERPRETS EVIDENCE
  → NEXT EXPERIMENT IF REQUIRED
  → PROPOSE CANDIDATE
  → HUMAN CONFIRMATION
  → RESEARCH DBC
```

### Stage notes

| Stage | Deterministic inputs (MCP / CLI) | Generative role |
|-------|----------------------------------|-----------------|
| CONNECT | `get_cansub_device_status`, `get_cansub_channel_status`, `get_instance_info` | Verify correct backend when multiple connectors exist |
| DEFINE ASSET | `list_assets`, `get_asset`, session/asset association | Choose scope; never mix assets silently |
| OBSERVE TRAFFIC | `observe_live_traffic`, `start_live_capture` / `stop_live_capture` | Decide duration; avoid raw dumps to user |
| APPLY REFERENCE | `lookup_pgn`, `lookup_spn`, `analyze_session`, `decode_session` | Map documented traffic; exclude from proprietary search |
| APPLY CONFIRMED KNOWLEDGE | `list_research_candidates`, `preview_research_dbc`, asset DBC on disk | Exclude confirmed `(can_id, start_bit, …)` from search |
| BUILD KNOWN BASELINE | `build_session_dbc_preview` → `<asset>_standard.dbc` concept | Explain what is already explained |
| INVENTORY UNKNOWN | `analyze_session`, `rank_signal_candidates`, proprietary PGN/ID lists | Prioritize unknown remainder |
| USER REQUEST | — | Classify intent; translate to experiment plan |
| EXPERIMENT | `mark_experiment_event`, `compare_experiment_windows`, capture | One-variable changes; event labels |
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

- Change **one physical variable at a time** where practical.
- **Repeat** cheap experiments (centre → left → centre) to test repeatability.
- Prefer tests that **discriminate competing hypotheses** over broad data collection.
- If two candidates remain, design the **next experiment specifically to separate them**.
- Do **not** ask the operator for unnecessary actions.
- Use **event markers** (`mark_experiment_event`) at stable states before/after transitions.

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

---

## 7. Evidence / confidence model

The Skill uses qualitative confidence — not a hidden numeric score presented as fact.

| Level | Meaning | Typical requirements |
|-------|---------|----------------------|
| **possible** | Hypothesis consistent with one window | Single observation; weak repeatability |
| **likely** | Repeatable across cycles/windows | Direction/sign behaviour; stable field boundaries |
| **high confidence** | Strong discrimination vs alternatives | Independence from unrelated actions; physical plausibility |
| **confirmed** | Accepted into research DBC | **Explicit human CLI confirmation only** |

### Evidence types (deterministic)

- Repeatability across repeated experiment cycles
- Baseline stability when the physical quantity is unchanged
- Direction / sign behaviour under opposing actions
- Monotonicity where expected
- Physical plausibility (range, units, rate limits)
- Candidate field boundaries (start bit, length, endianness, signedness)
- Scaling hints from known anchor values (only when supported by data)
- Timing relationship to related frames
- Independence from unrelated operator actions
- Known contextual anchors (e.g. approximate location for coordinate decoding)

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
3. **Classify** as centred analogue.
4. **Instruct** operator: wheels centred → full left → centred → full right → centred.
   Mark events at each stable state.
5. **Capture** session; `compare_experiment_windows` between baseline and extremes.
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
