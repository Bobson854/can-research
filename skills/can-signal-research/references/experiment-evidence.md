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
