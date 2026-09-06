# Contextual reasoning and external research

The AI layer adds engineering reasoning beyond deterministic rankers. Do more than list
changing bytes.

## Use real-world context actively

| Context type | Examples |
|--------------|----------|
| Machine purpose | Tractor, sprayer, GNSS bench, implement |
| Physical state | Stationary, engine on, GPS fix, operating |
| Specifications | RPM limits, row width, tank size |
| Geography | City/region for lat/lon/altitude plausibility |
| Connected sensors | GNSS, pressure, flow |
| Parallel data | MQTT, API, serial, HMI screenshot **without** showing DBC |
| Documentation | Service manual, manufacturer conventions |
| Prior confirmed signals | Same controller family |

Before fragmenting a payload into small bitfields, test **common whole-field interpretations**
where context suggests them (e.g. int32 lat/lon pair, uint16 RPM block).

## Cross-field coherence

Score **complete message layouts** above unrelated per-field guesses.

A GNSS companion frame where speed, course, altitude, satellite count, and fix bits all fit
together should outrank a layout that decodes one field plausibly but breaks neighbours.

## Validation-session patterns (methodology — not universal CAN knowledge)

**GNSS bench (Murray Bridge region):**

- Signed LE int32 × 1e-7 → lat/lon near -35.1276, 139.2718 (geographic plausibility)
- uint16 × 0.01 → ~3700–4400 consistent with local altitude during GNSS settle
- Byte values 9–11 → satellite-count-like (not enum value 11 alone)
- Status byte `0x05` → validity + fix-type **bitfield** more plausible than “enum 5”

**Sprayer / application context:**

- Static values 150 / 0 / 1000 / 420 became meaningful as application rate, row width,
  fan RPM, pump RPM once machine context was supplied — not from byte activity alone.

Do not hard-code these IDs/scales for other machines. Reuse the **reasoning method**.

## Static signals are valid targets

Do not discard messages because no bytes changed. Configuration and setpoint frames may be
highly informative.

Use engineering plausibility, UI values, machine limits, neighbouring fields, and DBC
patterns. Mark: “Needs changed operating state for experimental confirmation” when values
are static under current conditions.

## External / web research

Use web or external sources **when they can materially confirm or reject a hypothesis**:

- Map/elevation for GPS altitude
- Manufacturer RPM/product ranges
- Manual status-bit definitions
- Known sensor output formats
- Public protocol documentation

Distinguish evidence types:

| Type | Label in reports |
|------|------------------|
| Observed CAN (MCP) | CAN evidence |
| Local learned / DBC | Local learned evidence |
| Reference catalogue | Standards-backed |
| Operator statement | Operator-provided |
| Web/manual lookup | External evidence |
| Model inference | AI inference |

Do not search the web without purpose. One targeted lookup beats broad browsing.

## Field width caution

Observed value range ≠ encoded width. See [field-analysis.md](field-analysis.md).

## Better operator questions

Avoid: “What signal is this?”

Prefer:

- Is the machine stationary?
- What device generates this traffic?
- What sensors are attached?
- What operating ranges are physically possible?
- Can you show the controller/HMI (without the DBC)?
- Can you provide an MQTT/API/serial snapshot?
- Can you change **one** setpoint and hold it?

Cheapest highest-information question or experiment first.
