---
name: can-signal-research
description: >-
  Guided CAN signal research workflow using the CAN Research MCP connector.
  Use when the operator asks to find, identify, decode, or reverse-engineer a
  proprietary CAN signal (steering angle, PTO, pressure, GPS/coordinates,
  section status, hydraulics, modes, etc.) on a specific machine asset.
  Confirms backend and live CAN path, establishes system/asset context, accounts
  for reference-backed and confirmed DBC knowledge first, inventories unknown
  traffic, validates passive hypotheses with deterministic MCP tools, designs
  controlled physical experiments only when needed, and prepares proposals for
  explicit human CLI confirmation into an asset research DBC. Do not use for
  generic J1939 reference lookup alone, autonomous bus transmission, or
  automatic candidate confirmation.
---

# CAN signal research

Control plane for AI-assisted **proprietary** CAN signal discovery on a connected
CAN Research backend.

**Design contract:** [docs/AI_GUIDED_SIGNAL_RESEARCH.md](../../docs/AI_GUIDED_SIGNAL_RESEARCH.md)

**Principle:** Deterministic software measures facts; you decide what those facts likely
mean and what to test next.

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
- Never claim an asset was created unless MCP/CLI actually created it.
- Never apply proprietary findings from one asset to another without explicit scope change.
- Never present generative inference as SAE/reference-backed fact.
- Never treat operator machine context as deterministic proof of signal meaning.

## Workflow (required order)

Do **not** jump to capture or signal ranking when basic context and the live path are
unknown. Follow this sequence:

```text
1. CONFIRM BACKEND        get_instance_info
2. LIVE PREFLIGHT         get_cansub_device_status → get_cansub_channel_status
                          → observe_live_traffic (short, bounded)
                          → verify frames present before any capture
3. INSPECT ASSETS         list_assets / get_asset (if any exist)
4. SYSTEM CONTEXT         understand what the operator believes is connected
5. ESTABLISH ASSET SCOPE  propose asset_key / type / display_name; operator confirms
6. KNOWN-FIRST            reference decode + confirmed candidates + DBC preview
7. INVENTORY UNKNOWN      prioritize proprietary remainder for the request
8. PASSIVE INFERENCE      structure hypotheses; preview_candidate_values on stored/live data
9. PHYSICAL EXPERIMENT    only if passive evidence leaves material ambiguity
10. PROPOSE + CLI PATH    structured candidate; human confirm via CLI
```

Track progress internally; expose only concise operator-facing summaries.

## Live preflight (mandatory before capture)

**Never** call `start_live_capture` until preflight succeeds.

```text
get_instance_info
  → get_cansub_device_status
  → get_cansub_channel_status
  → observe_live_traffic (default ~3 s, max 15 s)
  → confirm frames are present on the intended channel
  → only then start_live_capture
```

Preflight must establish:

- CAN Research backend reachable and correct instance
- CANsub reachable
- Requested channel exists
- Channel not obviously bus-off / erroring (from channel status)
- Live observation returns frames
- Research channel available for MCP (no `channel_rx_in_use`)

If **no frames** appear in observation, report succinctly and **stop** the research
workflow until the physical/network issue is resolved. Do not create an empty capture
session when observation already shows no usable traffic.

## System context intake

When system context is not already known from assets, sessions, or the operator's opening
message, ask **at most one or two** high-value questions at a time.

**Primary question (when useful):**

> What are we connected to?

Possible categories (infer when obvious; do not read out the full list unless helpful):

- tractor · implement · controller/module · GPS/GNSS device · mower · sprayer
- vehicle/machine · multiple devices / whole CAN network · not sure

**Follow-up only when it materially narrows hypotheses:**

- Single device on a bench, or part of a larger machine/network?
- Known make/model/controller family?
- Tractor and implement traffic both present?
- What is the machine doing right now? (stationary · ignition only · operating · GPS fix · engine running · …)

**Interaction rule:** Infer what can be inferred from MCP traffic and existing assets.
Ask only what the operator is likely to know better than the data.

**Do not ask for** serial number, year, every ECU, full network parameters, or exhaustive
metadata unless specifically relevant.

Use context as a **prior to narrow hypotheses**, not as proof. See
[system-context-and-assets.md](references/system-context-and-assets.md).

## Asset scope assistance

Help the operator define scope before deep research. MCP can **inspect** assets
(`list_assets`, `get_asset`) but **cannot create** them.

When scope is clear, propose:

```text
asset_key:   <filename-safe key>
type:        tractor | implement | controller | …
display_name: <human label>
```

Ask: **Use this asset?** If creation is needed, give the exact CLI path and do not
claim the asset exists until verified.

When tractor **and** implement traffic may both be visible, recognise **separate asset
scopes** — do not silently mix tractor standard traffic with implement proprietary research.

Details: [system-context-and-assets.md](references/system-context-and-assets.md).

## Passive hypothesis validation (before physical tests)

When you form a plausible field hypothesis, **validate with deterministic MCP** before
asking the operator to move hardware.

```text
observed payload structure
  → hypothesis (start, length, endian, signed, factor, offset)
  → preview_candidate_values (on session data when available)
  → evaluate decoded values for physical/contextual plausibility
  → adjust encoding and semantic confidence separately
  → physical experiment only if ambiguity remains
```

Apply to endian alternatives, signed vs unsigned, field widths, factors, and offsets.

**Passive inference first. Physical experiment second.**

## Encoding vs semantic confidence

Report two axes — see [evidence-and-confidence.md](references/evidence-and-confidence.md):

| Axis | Question |
|------|----------|
| **Encoding confidence** | Are bit boundaries, endian, signedness, and scale correct? |
| **Semantic confidence** | Does the decoded value mean what we think (altitude vs pressure vs command)? |

Overall labels remain: **possible → likely → high confidence → confirmed** (confirmed =
human CLI only). High encoding confidence does **not** imply confirmed semantics.

## Operator dialogue (keep short)

During active research, the operator should usually see only:

- one short context question when necessary
- the next physical instruction when necessary
- a concise hypothesis/result with evidence and confidence
- one follow-up test only if it materially helps

**Avoid exposing** unless explicitly asked:

- full MCP call sequences
- huge bit-change tables
- every rejected candidate
- every intermediate hypothesis

Good physical instruction: “Centre the steering wheel and reply when stable.”

Bad: dumping hundreds of changing bit candidates.

Report: next action · progress · top candidate(s) · encoding/semantic confidence · follow-up test.

## Handle `channel_rx_in_use`

If MCP returns **`channel_rx_in_use`**, interpret as:

> Another WebSocket client currently owns that CANsub channel.

**Not:** “the CAN bus has no traffic.”

Common owners: webCAN, another MCP capture, another live observer, another application.

Tell the operator to **free only the intended research channel**. Example:

> Channel 1 is already owned by another WebSocket client. If webCAN is open, leave your
> monitoring display on channel 2 and disconnect channel 1 so MCP can use it.

Do not instruct a full system restart unless the socket is genuinely stuck.

If a capture fails to stop and remains marked recording, warn that the local MCP process
may still own the WebSocket and that restarting the local MCP server may be the cleanest
recovery.

## MCP tools (substrate — do not reimplement)

Use existing tools only. Prefer:

| Need | Tools |
|------|-------|
| Identity | `get_instance_info` |
| Live preflight | `get_cansub_device_status`, `get_cansub_channel_status`, `observe_live_traffic` |
| Experiment session | `start_live_capture`, `mark_experiment_event`, `stop_live_capture` |
| Window diff | `compare_experiment_windows` |
| Session analysis | `analyze_session`, `decode_session`, `list_session_events` |
| Passive validation | `preview_candidate_values`, `rank_signal_candidates`, `analyze_can_id_activity`, `correlate_candidate_field`, `analyze_repeated_action`, `detect_counters`, `detect_checksums` |
| Known baseline | `lookup_pgn`, `lookup_spn`, `build_session_dbc_preview`, `preview_research_dbc`, `list_research_candidates` |
| Assets | `list_assets`, `get_asset` |

Full list: project README MCP section.

## Intent → approach (quick map)

| Intent | Start here | Reference |
|--------|------------|-----------|
| On/off, engaged, alarm | Passive bit/enum scan → boolean experiment if needed | [experiment-patterns.md](references/experiment-patterns.md) |
| Steering, centred joystick | Known-first → centre/left/right experiment | same |
| Pressure, level, throttle | Monotonic passive hints → staged experiment | same |
| GPS / GNSS / coordinates | Context + `preview_candidate_values` → geographic plausibility | [system-context-and-assets.md](references/system-context-and-assets.md) |
| Unknown | Known-first → inventory → passive validation → targeted experiment | same |

## Benchmark methodology example (not universal CAN knowledge)

The first Office asset-scoped benchmark (September 2026) demonstrated the workflow above.
Do **not** treat these IDs or scales as generic definitions for other controllers.

**Pattern observed** on a bench controller with GNSS context:

- Frame `0x18667017` (8 bytes): passive hypothesis bytes 0–3 and 4–7 as signed LE int32 × 1e-7
  decoded to geographically plausible coordinates near the operator's stated location → raised
  **encoding and semantic** confidence without hardware movement.
- Companion frame `0x18667117`: `preview_candidate_values` produced values resembling plausible
  speed (~0.07–0.10 m/s), course (~355°), altitude-like (~60.5), and small status/count bytes —
  GNSS context made speed/course/altitude/satellite/fix interpretations more plausible, but
  semantics remained **hypothesis** until CLI confirm.

Use this as a **methodology example** only: contextual narrowing, passive candidate validation,
separate encoding/semantic confidence.

## Self-evaluation checklist (future trials)

After a guided research run, check:

- [ ] Confirmed the correct backend (`get_instance_info`)
- [ ] Understood or established asset/system context
- [ ] Checked known/reference-backed knowledge first
- [ ] Verified live traffic before starting capture
- [ ] Avoided unnecessary physical actions
- [ ] Used passive context to narrow hypotheses
- [ ] Validated candidate encodings with deterministic tools (`preview_candidate_values`, …)
- [ ] Separated encoding confidence from semantic confidence
- [ ] Kept asset provenance strict
- [ ] Avoided claiming inference was confirmed
- [ ] Kept operator interaction concise

## When stuck

| Problem | Action |
|---------|--------|
| No frames in preflight | Stop; fix wiring/channel/CANsub — do not capture empty sessions |
| `channel_rx_in_use` | Free WebSocket on that channel (see above) |
| Missing deterministic measurement | Note gap; suggest MCP/core improvement (architecture doc §12) |
| Poor experiment design | Re-read [experiment-patterns.md](references/experiment-patterns.md) |
| Weak evidence language | Re-read [evidence-and-confidence.md](references/evidence-and-confidence.md) |
| Asset scope unclear | Re-read [system-context-and-assets.md](references/system-context-and-assets.md) |

## References (load when needed)

- [system-context-and-assets.md](references/system-context-and-assets.md) — context intake, asset scope, context-as-prior
- [experiment-patterns.md](references/experiment-patterns.md) — physical test templates
- [evidence-and-confidence.md](references/evidence-and-confidence.md) — encoding/semantic confidence rules
- [docs/AI_GUIDED_SIGNAL_RESEARCH.md](../../docs/AI_GUIDED_SIGNAL_RESEARCH.md) — full architecture
