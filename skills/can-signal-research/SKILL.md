---
name: can-signal-research
description: >-
  Guided CAN signal research workflow using the CAN Research MCP connector.
  Use when the operator asks to find, identify, decode, or reverse-engineer a
  proprietary CAN signal (steering angle, PTO, pressure, GPS/coordinates,
  section status, hydraulics, modes, etc.) on a specific machine asset.
  Establishes asset scope, accounts for reference-backed and confirmed DBC
  knowledge first, inventories unknown traffic, designs controlled physical
  experiments, analyzes deterministic MCP evidence, iteratively narrows candidate
  fields, and prepares proposals for explicit human CLI confirmation into an
  asset research DBC. Do not use for generic J1939 reference lookup alone,
  autonomous bus transmission, or automatic candidate confirmation.
---

# CAN signal research

Control plane for AI-assisted **proprietary** CAN signal discovery on a connected
CAN Research backend.

**Design contract:** [docs/AI_GUIDED_SIGNAL_RESEARCH.md](../../docs/AI_GUIDED_SIGNAL_RESEARCH.md)

**Principle:** Deterministic software measures facts; you decide the next useful experiment.

## Prerequisites

1. **CAN Research MCP connector** attached in the host environment (ChatGPT, Codex, etc.).
   The connector URL and instance are **installation-specific** — do not assume a single
   office/workshop name.
2. When backend identity matters (multiple connectors, shared ChatGPT account), call
   **`get_instance_info`** first and confirm with the operator if ambiguous.
3. CANsub.2 reachable on the configured channel; **passive RX only** — no CAN TX tools exist.

## Safety and boundaries

- Never transmit on the bus or request injection.
- Never confirm a research candidate via MCP — confirmation is **CLI-only** today.
- Never claim a signal is in `<asset>_research.dbc` until the operator has run CLI confirm.
- Never apply proprietary findings from one asset to another without explicit scope change.
- Never present generative inference as SAE/reference-backed fact.

## Workflow checklist

Copy and track progress:

```text
- [ ] CONNECT — device/channel healthy (`get_cansub_*`)
- [ ] DEFINE ASSET — scope explicit (`list_assets`, `get_asset`)
- [ ] OBSERVE — bounded traffic snapshot if needed (`observe_live_traffic`)
- [ ] KNOWN-FIRST — reference decode + confirmed candidates + standard/research DBC preview
- [ ] INVENTORY UNKNOWN — prioritize proprietary remainder
- [ ] CLASSIFY INTENT — boolean / centred analogue / monotonic / coordinate / …
- [ ] DESIGN EXPERIMENT — one variable at a time; minimal operator burden
- [ ] CAPTURE + EVENTS — `start_live_capture`, `mark_experiment_event`, `stop_live_capture`
- [ ] ANALYZE — MCP signal research + window comparison (internal detail, concise summary)
- [ ] ITERATE — discriminating follow-up if candidates tie
- [ ] PROPOSE — structured candidate (ID, start, length, endian, signed, scale if justified)
- [ ] HUMAN CONFIRM — operator uses CLI review/confirm; you do not
```

## MCP tools (substrate — do not reimplement)

Use existing tools only. Prefer:

| Need | Tools |
|------|-------|
| Identity | `get_instance_info` |
| Live scope | `get_cansub_device_status`, `get_cansub_channel_status` |
| Quick look | `observe_live_traffic` |
| Experiment session | `start_live_capture`, `mark_experiment_event`, `stop_live_capture` |
| Window diff | `compare_experiment_windows` |
| Session analysis | `analyze_session`, `decode_session`, `list_session_events` |
| Candidate search | `rank_signal_candidates`, `analyze_can_id_activity`, `analyze_repeated_action`, `correlate_candidate_field`, `preview_candidate_values` |
| Known baseline | `lookup_pgn`, `lookup_spn`, `build_session_dbc_preview`, `preview_research_dbc`, `list_research_candidates` |

Full list: project README MCP section.

## Operator dialogue

During experiments, give **short physical instructions** and wait for readiness.

Good: “Centre the steering wheel and reply when stable.”

Bad: dumping hundreds of changing bit candidates.

Report: next action · progress · top candidate(s) · evidence · confidence · follow-up test.

Confidence words: **possible → likely → high confidence → confirmed** (confirmed = human CLI only).

## Intent → experiment (quick map)

| Intent | Start here | Reference |
|--------|------------|-----------|
| On/off, engaged, alarm | Boolean off/on/off | [experiment-patterns.md](references/experiment-patterns.md) |
| Steering, centred joystick | Centre / left / centre / right / centre | same |
| Pressure, level, throttle | Low / medium / high / return | same |
| GPS / lat-lon hint | Stationary + geographic plausibility ranking | same + architecture doc §10 |
| Unknown | `rank_signal_candidates` + cheap baseline | same |

## End-to-end patterns (summary)

**Steering angle:** known-first → centred analogue experiment → window compare → prefer
signed continuous field with repeatable centre and opposing extremes → discriminate ties →
propose → CLI confirm.

**Coordinate hint:** operator gives contextual anchor (region, approximate location) → rank
endian/width/scale hypotheses with plausibility → motion only if needed → propose → CLI confirm.

Do not embed machine-specific encodings in this Skill.

## When stuck

| Problem | Action |
|---------|--------|
| Missing deterministic measurement | Note gap; suggest MCP/core improvement (see architecture doc §12) |
| Poor experiment design | Re-read [experiment-patterns.md](references/experiment-patterns.md) |
| Weak evidence language | Re-read [evidence-and-confidence.md](references/evidence-and-confidence.md) |
| Channel busy / WS in use | Ask operator to close webCAN or stop other capture on that channel |

## References (load when needed)

- [experiment-patterns.md](references/experiment-patterns.md) — physical test templates
- [evidence-and-confidence.md](references/evidence-and-confidence.md) — confidence rules
- [docs/AI_GUIDED_SIGNAL_RESEARCH.md](../../docs/AI_GUIDED_SIGNAL_RESEARCH.md) — full architecture
