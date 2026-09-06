# Field analysis — width, static signals, uncertainty

## Do not over-shrink field widths

**Minimum observed width ≠ likely encoded width.**

Example from validation: a true **16-bit speed** field appeared to fit in **8 bits** because
the high byte stayed zero while the device was stationary.

Report both:

```text
Observed values fit in 8 bits under current conditions.
A 16-bit field remains plausible — upper byte not exercised while stationary.
```

Keep wider hypotheses alive until operating conditions exercise upper bits or an experiment
discriminates.

## Test width hypotheses with context

| Condition | Favours wider field |
|-----------|---------------------|
| Stationary / zero-heavy payload | High byte may never change |
| Small numeric changes | May fit multiple widths with different scale |
| Neighbouring 16/32-bit fields in same message | Whole-message layout consistency |
| Manufacturer conventions | Common uint16 RPM, int32 coordinates |

Use `preview_candidate_values` at multiple start/length hypotheses when ambiguity remains.

## Granular confidence (structural vs semantic)

Do not collapse to one all-or-nothing score. Where useful report:

| Dimension | Question |
|-----------|----------|
| Field boundary | Are start bit and length correct? |
| Byte order | Intel vs Motorola |
| Signedness | Signed vs unsigned |
| Factor / offset | Scale correct? |
| Unit | Engineering unit identified? |
| Semantic class | RPM-like, pressure-like, lat-like, … |
| Exact meaning | Fan_RPM vs Pump_RPM vs generic speed |

Example:

> **Structure:** high — 16-bit Intel unsigned, 0–2000 range plausible.
> **Semantics:** medium — rotational-speed-like; Fan vs Pump not yet discriminated.

This is a **successful reverse-engineering result** even without final naming.

See also [evidence-and-confidence.md](evidence-and-confidence.md).

## Report uncertainty usefully

Good output:

> Bits 32–47 appear to be one 16-bit Intel numeric field. Behaviour is altitude-like;
> values ~37–44 m with factor ~0.01 plausible. Structure confidence high; exact
> scaling/name not yet confirmed.

Avoid forcing exact names/scales before evidence supports them. The technician adjusts
naming/scaling after viewer testing.

## Static / setpoint messages

Static bytes are not “uninteresting.” They may encode:

- Application rate, row width, RPM setpoints
- Configuration enums and bitfields
- Calibration constants

Combine with operator context (HMI, MQTT, manual). Flag for **confirmation experiment**
when a single controlled change would validate causality.
