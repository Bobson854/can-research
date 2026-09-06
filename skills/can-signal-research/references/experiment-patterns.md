# Experiment patterns

Physical test templates for proprietary CAN signal research. Pair each stable state with
`mark_experiment_event` labels before calling `compare_experiment_windows` or offline
signal research tools on the captured session.

## Passive first

Complete **live preflight** and **passive hypothesis validation** before any capture or
physical experiment:

1. `get_instance_info` → `get_cansub_*` → `observe_live_traffic` — confirm frames exist.
2. Known-first baseline (reference + confirmed DBC).
3. Form hypotheses; run **`preview_candidate_values`** on session data when available.
4. Use operator context as a **prior**, not proof (see [system-context-and-assets.md](system-context-and-assets.md)).
5. Design a physical experiment **only** when passive evidence leaves material ambiguity.

Do not start `start_live_capture` when observation shows no traffic or when
`channel_rx_in_use` blocks the channel.

## Universal rules

1. **One variable at a time** — do not steer and rev PTO in the same window unless testing coupling is the explicit goal.
2. **Stable before mark** — wait for the operator to confirm the machine state has settled.
3. **Repeat cheap cycles** — centre → left → centre costs little and tests repeatability.
4. **Discriminate, don't collect** — prefer the smallest next test that splits two hypotheses.
5. **Name events consistently** — e.g. `baseline_start`, `left_full`, `centre_return`, `right_full`.
6. **Baseline first** — always capture a neutral/idle window when applicable.

## Boolean / discrete

**Use for:** PTO engaged, switches, alarms, clutch states, section on/off.

**Pattern:**

```text
off (stable) → mark baseline
on  (stable) → mark active
off (stable) → mark return
[repeat once if practical]
```

**Analysis bias:** bits or small enums that flip with state; stable in baseline windows.

## Centred analogue

**Use for:** Steering angle, neutral-centre joysticks, bidirectional proportional controls.

**Pattern:**

```text
centre → mark
full left (or negative extreme) → mark
centre → mark
full right (or positive extreme) → mark
centre → mark
```

**Analysis bias:** signed continuous fields; centre repeatable; opposing extremes opposite sign;
magnitude grows with deflection.

**Tie-break:** half-deflection vs full-deflection to separate scale or duplicate candidates.

## Monotonic analogue

**Use for:** Pressure, tank level, throttle, hydraulic demand.

**Pattern:**

```text
low / empty / idle → mark
medium → mark
high / full → mark
return low → mark
```

**Analysis bias:** mostly monotonic within a session; may not return to exact baseline (hysteresis).

## Cyclic / rotational

**Use for:** Angles with wrap, encoder counts, rotating implement position.

**Pattern:**

```text
known position A → mark
rotate Δθ (operator-known if possible) → mark
return A → mark
[optional second Δθ to detect wrap or direction]
```

**Analysis bias:** modulo/wrap behaviour; direction consistency.

## Motion / speed

**Use for:** Ground speed proxies, motion-detected states.

**Pattern:**

```text
stationary (engine on if relevant) → mark
move straight (operator describes) → mark
stop → mark
```

**Analysis bias:** fields zero or stable when stationary; change during motion.

## Coordinate / GPS-style

**Use for:** Lat/lon in proprietary frames when operator hints geography.

**Pattern:**

```text
stationary baseline → mark
[optional short displacement in known direction] → mark
```

**Without exact encoding**, use contextual anchors and **`preview_candidate_values`**:

- Approximate region (city, farm, depot) narrows plausible lat/lon ranges.
- Rank signed/unsigned, endian, and scale candidates by geographic plausibility.
- Validate decodes deterministically before asking for motion.
- Motion helps only when stationary ranking leaves multiple viable encodings.

Do not hard-code answers from past bench machines in this reference.

## Status / mode enumeration

**Use for:** Section control states, ECU modes, implement configuration.

**Pattern:**

```text
mode A (stable) → mark
mode B (stable) → mark
...
return A → mark
```

Traverse modes **slowly**; one mode change between marks when possible.

## Command / feedback pairs

**Use for:** Command frame vs measured response.

**Pattern:**

```text
no command / idle → mark
operator performs single commanded action → mark
settle → mark
```

Compare windows around command vs idle; look for correlated response IDs (not assumed PGN).

## Experiment-aware ranking

After a controlled operator change, **experiment signature** beats raw activity rank:

- Stable → exact requested change → return to baseline → no spurious neighbour changes

See [experiment-evidence.md](experiment-evidence.md). Do not ask the operator to repeat
when one clean cycle already proves causality.

## When two candidates remain

Design the **smallest** test that splits them:

| Ambiguity | Discriminating test |
|-----------|---------------------|
| Bit vs byte field | Small physical change vs large change |
| 16 vs 32 bit | Partial deflection vs full deflection magnitude |
| Two CAN IDs | Hold physical state; check which ID stabilizes first |
| Signed vs unsigned | Cross centre in both directions |
| Scale factor | Use contextual anchor (centre ≈ 0, known approximate value) |

## Anti-patterns

- Starting capture before live preflight shows frames on the channel.
- Treating `channel_rx_in_use` as “no traffic on the bus.”
- Skipping `preview_candidate_values` when a field layout is already hypothesized.
- Long captures with no event labels.
- Asking the operator to sweep every control at once.
- Re-running full bus ranking when a targeted follow-up test would suffice.
- Ignoring confirmed asset DBC and rediscovering known signals.
- Trusting `rank_signal_candidates` over a clean experiment window on the target ID.
