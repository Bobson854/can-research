---
name: can-signal-research
description: >-
  AI-assisted CAN reverse-engineering workbench using the CAN Research MCP connector.
  Use for proprietary signal discovery on tractors, implements, controllers, and mixed
  networks. Inventories bus traffic standards-first, reuses local DBC knowledge,
  applies contextual and external reasoning, validates with deterministic MCP tools,
  runs targeted experiments when needed, produces Markdown reports and research DBC
  previews, and stops at CLI-only confirmation. Passive RX only — no CAN TX.
---

# CAN signal research

AI-assisted **reverse-engineering workbench** on a CAN Research MCP backend.

**Principle:** Deterministic tools measure facts; you add engineering reasoning, context,
knowledge reuse, and efficient operator guidance.

**Goal:** Likely boundaries, endian, signedness, scaling, semantic class, and confidence —
not necessarily a perfect autonomous DBC. Technicians refine naming/scaling after viewer testing.

**Design contract:** [docs/AI_GUIDED_SIGNAL_RESEARCH.md](../../docs/AI_GUIDED_SIGNAL_RESEARCH.md)

## Prerequisites

1. **CAN Research MCP connector** attached (installation-specific — use `get_instance_info`).
2. CANsub.2 reachable; **passive RX only**.

## Safety and boundaries

- Never transmit on the bus or request injection.
- Never confirm candidates via MCP — **CLI-only**.
- Never claim DBC/research entries exist unless verified.
- Never silently copy definitions from other assets — reuse creates **hypotheses** only.
- Never collapse evidence types (CAN / standard / local / operator / external / AI inference).

## Workflow (required order)

```text
1. CONFIRM BACKEND         get_instance_info
2. LIVE PREFLIGHT          get_cansub_* → observe_live_traffic → frames present
3. INSPECT ASSETS          list_assets / get_asset; list_sessions if relevant
4. SYSTEM CONTEXT          minimal questions — [system-context-and-assets.md](references/system-context-and-assets.md)
5. ESTABLISH ASSET SCOPE   propose asset_key; CLI if create needed
6. BUS INVENTORY           standards + nodes + DBC coverage — [bus-inventory-and-standards.md](references/bus-inventory-and-standards.md)
7. REUSE LOCAL KNOWLEDGE   DBC fingerprints, prior research — [knowledge-reuse.md](references/knowledge-reuse.md)
8. PASSIVE INFERENCE       whole-field + cross-field reasoning — [contextual-reasoning.md](references/contextual-reasoning.md)
9. VALIDATE                preview_candidate_values; field-width caution — [field-analysis.md](references/field-analysis.md)
10. EXPERIMENT (if needed)  controlled change; signature beats ranker — [experiment-evidence.md](references/experiment-evidence.md)
11. OUTPUT                   Markdown report + research DBC preview — [research-output-and-dbc.md](references/research-output-and-dbc.md)
12. PROPOSE + CLI            human confirm; persist catalogue knowledge
```

**Traffic layering:** observed bus → catalogue-backed → imported bundle-backed → DBC-known → proprietary remainder.

## Live preflight (mandatory before capture)

Never `start_live_capture` until:

```text
get_instance_info → get_cansub_device_status → get_cansub_channel_status
  → observe_live_traffic → frames present → start_live_capture
```

No frames → stop. No empty captures. See **`channel_rx_in_use`** = WebSocket ownership, not missing traffic.

## Confidence (granular)

Report structural and semantic dimensions separately where useful — see
[evidence-and-confidence.md](references/evidence-and-confidence.md) and
[field-analysis.md](references/field-analysis.md).

High structure + medium exact meaning is a **valid success**.

## Operator dialogue

- Infer first; **one or two** questions max when needed.
- Prefer: machine state, device type, sensors, HMI/MQTT snapshot, **one setpoint change**.
- Avoid: “What signal is this?”
- Avoid repeating experiments when evidence is already strong.

## MCP tools (substrate)

| Phase | Tools |
|-------|-------|
| Identity / live | `get_instance_info`, `get_cansub_*`, `observe_live_traffic`, capture/events |
| Bus inventory | `analyze_session`, `decode_session`, `list_session_nodes`, `lookup_pgn`/`lookup_spn`, `lookup_reference_message`, `list_reference_sources`, `search_reference_knowledge`, `build_session_dbc_preview`, `list_dbc_sources`, `analyze_dbc_coverage` |
| Research | `preview_candidate_values`, `rank_signal_candidates`, `analyze_can_id_activity`, `correlate_candidate_field`, `compare_experiment_windows`, `detect_counters`/`checksums` |
| Knowledge | `list_research_candidates`, `preview_research_dbc`, `list_assets`, `get_asset`, **`inspect_dbc`**, **`lookup_dbc_message`** |

Full list: project README.

## Intent → reference

| Intent | Reference |
|--------|-----------|
| New machine capture | [bus-inventory-and-standards.md](references/bus-inventory-and-standards.md) |
| Similar message elsewhere | [knowledge-reuse.md](references/knowledge-reuse.md) |
| GNSS / sprayer / static setpoints | [contextual-reasoning.md](references/contextual-reasoning.md) |
| Controlled RPM/pressure test | [experiment-evidence.md](references/experiment-evidence.md) |
| PLC command/handshake / tuning diagnosis | [experiment-patterns.md](references/experiment-patterns.md) |
| Report / DBC for viewer | [research-output-and-dbc.md](references/research-output-and-dbc.md) |
| Physical test templates | [experiment-patterns.md](references/experiment-patterns.md) |

## Self-evaluation checklist

- [ ] Backend + preflight + frames verified
- [ ] Registered DBC sources listed; `analyze_dbc_coverage` run when DBCs exist
- [ ] Bus inventory: catalogue vs bundle-backed vs DBC-known vs unknown summarised
- [ ] Local/DBC knowledge searched before “unknown” research
- [ ] Passive + contextual reasoning before physical action
- [ ] Field widths not over-shrunk; static messages considered
- [ ] Experiment signature weighted over naive ranker when applicable
- [ ] Transaction health (command/ack/complete, CommandID) assessed before transport/retry recommendations
- [ ] Control-loop/tuning separated from transport failure when handshake evidence is clean
- [ ] Saved sessions and event markers used for intermittent faults
- [ ] Evidence types labelled; external research used purposefully
- [ ] Markdown report / DBC preview offered when useful
- [ ] No false confirmation claims

## References

- [bus-inventory-and-standards.md](references/bus-inventory-and-standards.md)
- [knowledge-reuse.md](references/knowledge-reuse.md)
- [contextual-reasoning.md](references/contextual-reasoning.md)
- [field-analysis.md](references/field-analysis.md)
- [experiment-evidence.md](references/experiment-evidence.md)
- [research-output-and-dbc.md](references/research-output-and-dbc.md)
- [system-context-and-assets.md](references/system-context-and-assets.md)
- [experiment-patterns.md](references/experiment-patterns.md)
- [evidence-and-confidence.md](references/evidence-and-confidence.md)
