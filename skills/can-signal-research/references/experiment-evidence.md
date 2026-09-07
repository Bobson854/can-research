# Experiment-aware evidence

When the operator performs a **controlled change**, experimental correlation should
**dominate** unrelated background activity.

Generic activity rankers may elevate noisy periodic traffic (e.g. GNSS) over the true
response. The Skill must apply engineering judgement on top of deterministic tools.

## Strong experiment signature

Treat as **very strong evidence** when all apply:

1. Field was **stable** before the action
2. Field changed by the **exact requested numeric delta** (or clear physical correlate)
3. **No unrelated neighbouring fields** changed spuriously
4. Field **returned to baseline** on return-to-setpoint

Example (validation session): Fan RPM 1000 → 1200 → 1000 — only bytes 4–5 of `0x18667217`
followed exactly. Generic ranker wrongly prioritised noisier GNSS IDs.

**Your ranking should override naive activity rank** when experiment signature is this clean.

## Transaction health before software recommendations

For command/status or PLC-to-PLC protocols, establish transaction health **before** suggesting logic changes:

```text
Compare command vs status/ack/complete IDs
  → verify CommandID (or equivalent) correlation
  → check for remote faults, StopRequest, ACK timeout, completion timeout
  → note whether cyclic command frames repeat without new movement events
  → measure observed cadence and effective endpoint resolution
```

| Finding | Likely layer | Next step |
|---------|--------------|-----------|
| Missing ACK/complete, fault bits, timeout counters | Transport / transaction | Trace handshake fields and fault semantics |
| Clean handshake, matching CommandID, no faults | Control loop / tuning | One setpoint/gain/limit change per capture |
| Many identical command frames, one physical move | Held transaction | Do not treat each frame as a separate event |

**Do not recommend retry, watchdog, or transport rewrites** when the capture already shows a healthy command → acknowledge → complete path with consistent CommandID matching.

## Cyclic commands vs movement events

Repeated cyclic command frames often mean the controller is **holding one transaction level**, not issuing duplicate movements.

Prefer **CommandID correlation** over inferring events from short pulse edges alone.

When cyclic traffic is present, compare:

- command CommandID vs acknowledge/status/complete CommandID
- whether status/position fields change once per operator action despite many command frames
- observed inter-frame period on the bus (not configured PLC scan time alone)

## Saved-session analysis

Intermittent faults may only appear in a saved capture after the machine or laptop has shut down.

Treat **`analyze_session`**, **`compare_experiment_windows`**, and event-marked offline review as first-class — not a fallback when live capture is unavailable.

Event markers around known physical disturbances (valve move, pressure step, setpoint edit) make offline windows usable days later.

## Minimal operator burden

One clean change + return-to-baseline is often **enough** when evidence is strong.

Do not ask the operator to repeat actions unnecessarily. Request another experiment only
when it **materially discriminates** remaining hypotheses (e.g. Fan vs Pump RPM, 8 vs 16 bit).

## Workflow

```text
capture with event marks (baseline → action → return)
  → compare_experiment_windows
  → correlate_candidate_field on targeted ID/field hypothesis
  → rank by experiment signature strength, not raw change count alone
  → preview_candidate_values for scaled plausibility
```

## MCP tools

| Purpose | Tool |
|---------|------|
| Window diff | `compare_experiment_windows` |
| Repeat cycles | `analyze_repeated_action` |
| Field correlation | `correlate_candidate_field` |
| Activity (secondary) | `analyze_can_id_activity`, `rank_signal_candidates` |
| Decode check | `preview_candidate_values` |

Use rankers to **suggest** candidates; use experiment windows to **confirm** causality.

## Event labelling

Consistent labels: `baseline_start`, `fan_1200`, `fan_1000_return`, etc.

Stable state before each mark — see [experiment-patterns.md](experiment-patterns.md).

## Anti-patterns

- Trusting `rank_signal_candidates` alone after a controlled experiment
- Ignoring static/setpoint messages pre-experiment
- Asking for a second RPM sweep when first already matched exact deltas
- Failing to compare return-to-baseline window
- Proposing retry/transport changes when handshake and CommandID evidence already look healthy
- Assuming PLC scan/tick configuration equals measured CAN cadence
- Treating every cyclic command frame as a separate movement event
- Changing multiple tuning parameters in one capture without isolated event marks
- Abandoning saved sessions because the fault cannot be reproduced live
