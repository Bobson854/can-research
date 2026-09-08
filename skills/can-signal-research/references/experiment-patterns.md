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
2. **One parameter change per capture** — when tuning or validating control behaviour, change only one setpoint, gain, timeout, or scan-related setting between marked captures. Multiple simultaneous changes obscure causality.
3. **Stable before mark** — wait for the operator to confirm the machine state has settled.
4. **Repeat cheap cycles** — centre → left → centre costs little and tests repeatability.
5. **Discriminate, don't collect** — prefer the smallest next test that splits two hypotheses.
6. **Name events consistently** — e.g. `baseline_start`, `left_full`, `centre_return`, `right_full`.
7. **Baseline first** — always capture a neutral/idle window when applicable.
8. **Mark known physical disturbances** — place event markers immediately before/after operator-visible movement, valve travel, pressure change, or HMI setpoint edits so offline windows align with ground truth.

## Local capture marker companion

During **live capture**, the operator may use the Windows **marker companion**
(`marker-companion.cmd` / `uv run canresearch session marker-companion`) to record precise
local annotations without chat or MCP timing:

| Label | Typical use |
|-------|-------------|
| `baseline` | Stable idle / neutral state |
| `page_opened` | Operator opened a screen or panel |
| `node_selected` | Tree/list selection changed |
| `save_pressed` | Save/commit action started |
| `save_complete` | Save/commit finished |
| `action` | General deliberate physical or UI action |

Companion markers set `origin=local_companion` and are stored in the same `session_events`
table as MCP `mark_experiment_event` markers. Prefer the companion when operator timing
must be precise; prefer MCP markers when the agent orchestrates the experiment remotely.

See [MARKER_COMPANION.md](../../../docs/MARKER_COMPANION.md).
9. **Prefer measured cadence** — use observed frame period and effective movement resolution from the capture; do not assume PLC scan time, tick interval, or configured cycle time equals endpoint timing on the bus.

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

**Use for:** Command frame vs measured response; PLC-to-PLC command/status handshakes.

**Pattern:**

```text
no command / idle → mark
operator performs single commanded action → mark
settle → mark
```

Compare windows around command vs idle; look for correlated response IDs (not assumed PGN).

**Before proposing software changes**, compare command and status IDs and transaction health:

| Check | Healthy transaction signs | Not a transport problem |
|-------|---------------------------|-------------------------|
| Handshake | command → acknowledge → complete present | Missing ACK/complete, StopRequest, remote fault |
| Correlation | matching **CommandID** (or equivalent) across command/status | Relying only on short pulse edges when ID matching is available |
| Duplication | repeated cyclic command frames do **not** imply duplicate movement events | One level-held transaction re-sent each scan |
| Faults | no ACK timeout, completion timeout, or remote fault counters rising | Transaction layer already proven |

When handshake evidence is clean but motion/position still wrong, treat the problem as **control-loop or tuning** (gains, limits, setpoint mapping, endpoint resolution) — not missing retries or broken transport.

## Cyclic / held transactions (PLC-style)

**Use for:** Controllers that re-transmit the same command every scan while a level or position is held.

**Interpretation:**

- Repeated identical (or slowly changing) command frames may represent **one sustained transaction**, not one movement per frame.
- Match **CommandID** (or protocol-equivalent correlation key) between command, acknowledge, status, and complete messages before counting “events.”
- Measure **effective movement resolution** and **observed CAN cadence** from the capture; configured PLC scan/tick settings are hints only.

**Pattern:**

```text
idle (no active command) → mark
single operator setpoint change → mark
hold at new level until motion settles → mark
return to idle/baseline → mark
```

**Analysis bias:** one physical movement despite many command frames; status/complete tied to CommandID; tune loop only after transaction health is confirmed.

## Saved sessions for intermittent faults

**Use for:** Faults that disappear after shutdown, power cycle, or operator leave/return.

Saved sessions remain a **first-class** analysis path:

```text
start_live_capture + event marks during fault
  → stop capture / save session
  → analyze_session / compare_experiment_windows / decode_session offline
  → revisit after laptop or machine restart without requiring live reproduction
```

Do not discard a saved capture because the machine state changed afterward — event markers and session metadata often preserve the only evidence of a transient fault.

## Transaction health vs control-loop tuning

Separate these diagnosis layers explicitly in reports:

```text
Layer 1 — Transport / transaction:  ACK, complete, CommandID match, faults, timeouts
Layer 2 — Timing / cadence:         observed frame period vs configured scan assumptions
Layer 3 — Control loop / tuning:    overshoot, hunting, wrong endpoint, gain/limit issues
```

**Do not recommend retry logic, watchdog, or transport changes** when Layer 1 evidence already shows a healthy command/acknowledge/complete path. Direct further work to Layer 3 (one parameter change per test capture).

Example outcome (motor-valve PLC pair): handshake working, no remote faults, no duplicate movement from cyclic commands, measurable cadence — remaining issue is tuning, not retry software.

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
- Changing multiple PLC/HMI parameters in one capture when tuning is the goal.
- Assuming configured scan/tick time equals observed CAN cadence or movement timing.
- Counting one movement per cyclic command frame when CommandID shows a single held transaction.
- Re-running full bus ranking when a targeted follow-up test would suffice.
- Ignoring confirmed asset DBC and rediscovering known signals.
- Trusting `rank_signal_candidates` over a clean experiment window on the target ID.
- Proposing retry/transport fixes when command/acknowledge/complete and CommandID correlation already look healthy.
- Discarding saved sessions because the fault is no longer live on the bench.
