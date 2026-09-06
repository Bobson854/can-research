# System context and assets

Guidance for understanding what is connected, narrowing hypotheses responsibly, and
establishing asset scope before proprietary signal research.

## System context intake

Before deep signal work, build a working mental model:

1. **Backend** — `get_instance_info` confirms which CAN Research installation is active.
2. **Live path** — preflight (device status, channel status, bounded `observe_live_traffic`).
3. **Existing assets** — `list_assets` / `get_asset` may already define scope.
4. **Operator belief** — what they think is on the bus, only if not inferable.

### High-value questions

Ask **at most one or two at a time**. Prefer inference over interrogation.

| Question | When useful |
|----------|-------------|
| What are we connected to? | Scope unknown; traffic alone is ambiguous |
| Bench single device or part of a larger network? | Separates controller-only vs mixed traffic |
| Known make/model/family? | Narrows plausible signal sets (still not proof) |
| Tractor and implement both present? | May require two asset scopes |
| Machine state right now? | Interprets stationary vs motion-related fields |
| Can you show HMI/controller (no DBC)? | Static setpoints, rates, RPM displays |
| MQTT/API/serial snapshot available? | Cross-check without revealing decode |
| Can you change one setpoint and hold it? | Minimal experiment (e.g. fan 1000→1200→1000) |

### Do not ask unless specifically relevant

Serial numbers, model year, every ECU name, full network topology, baud-rate debates,
or exhaustive machine metadata.

The operator knows **physical reality**; MCP knows **measured traffic**. Ask only where
human context beats the data.

## Context as a prior — not proof

Operator context **narrows plausible hypotheses**. It must **never** alone justify
reporting a semantic interpretation as confirmed.

| If context suggests… | More plausible signal families (hypothesis only) |
|----------------------|--------------------------------------------------|
| GPS/GNSS | latitude, longitude, speed, course/heading, altitude, satellite count, fix/status |
| Tractor | engine speed, wheel speed, steering, PTO, hitch, SCV, gear, temperatures |
| Sprayer | application rate, pressure, section states, tank level, pump/fan speed |
| Mower | blade state, deck height, engine/load, ground speed |
| Controller/module (bench) | status, configuration, sensor feeds, GNSS outputs — depends on attached peripherals |
| Whole mixed network | **First** separate source/controller ownership before assigning semantics |

Matching machine type ≠ confirmed signal name. Always validate encoding with
`preview_candidate_values` and plausibility checks; use physical experiments only when
passive evidence leaves material ambiguity.

## Asset scope assistance

Research candidates and DBC output are **asset-scoped**. Proprietary findings on one asset
must not silently apply to another.

### Inspect before inventing

```text
list_assets
get_asset <asset_key>
```

If a suitable asset exists, confirm with the operator and use it.

### Propose when missing

When scope is clear from conversation, propose a concrete definition:

**Example — bench controller with GNSS:**

```text
asset_key:    edge101_bench
type:         controller
display_name: EDGE101 bench GNSS
```

**Example — tractor only:**

```text
asset_key:    jd_6155r
type:         tractor
display_name: John Deere 6155R
```

**Example — implement behind tractor, both networks visible:**

Propose **two** scopes if needed:

```text
asset_key: jd_6155r          type: tractor    — standard/J1939 baseline focus
asset_key: weed_it_implement type: implement   — proprietary research focus
```

Do not merge implement proprietary research into tractor standard DBC work without
explicit operator agreement.

Ask: **Use this asset?** / **Create these two scopes?**

### MCP cannot create assets

The Skill may inspect, propose, and explain CLI creation. It must **not** claim an asset
exists unless verified.

Typical operator path:

```text
uv run canresearch asset add --key <asset_key> --name "<display_name>" --type <type>
```

Valid types: `tractor`, `implement`, `controller`, `other`. Optional: `--manufacturer`, `--model`, `--notes`.

After creation, re-fetch with `get_asset` before attributing sessions or candidates.

## Asset ↔ DBC workflow (reminder)

Per asset:

| File | Role |
|------|------|
| `<asset>_standard.dbc` | Reference-backed / standard signals |
| `<asset>_research.dbc` | Human-confirmed proprietary signals only |

MCP is read-only for candidate confirmation and DBC writes. CLI:

```text
research candidate review
research candidate confirm
```

Never state a signal is in research DBC until the operator has confirmed via CLI.

## Mixed-network discipline

When multiple controllers share a capture:

1. Inventory CAN IDs and periodicity — who likely owns each ID?
2. Apply known-first per **asset** scope, not per bus globally.
3. Attribute proprietary hypotheses to the asset under study.
4. If ownership is unclear, say so — do not force a semantic label.

## Benchmark methodology example (Office, September 2026)

**Not portable CAN knowledge** — illustrates the workflow only.

Operator context: bench controller with GNSS attached.

| Step | What happened |
|------|----------------|
| Context | GNSS/device framing narrowed plausible field types |
| Passive | `0x18667017` — int32 LE × 1e-7 lat/lon hypothesis; decodes geographically plausible near stated location |
| Validation | `preview_candidate_values` on `0x18667117` — speed ~0.07–0.10 m/s, course ~355°, altitude-like ~60.5, small status bytes |
| Confidence | Encoding confidence rose with stable decode; semantic confidence rose with GNSS context but stayed below **confirmed** |
| Physical | Not required for initial narrowing |

Reuse the **method**, not the ID/scale answers, on other machines.
