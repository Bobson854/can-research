# CANsub.2 PHY / timing REST API

This document began as an **investigation** into the CANsub PHY write contract. That
contract is now **verified** and **hardware acceptance-tested** on a documented baseline.
It remains the technical reference for PUT schema, implementation notes, and known limits.

## Current status

| Topic | Status |
|-------|--------|
| Read PHY (`GET /api/can/{channel}/phy`) | **Verified** |
| Write PHY (`PUT /api/can/{channel}/phy`) | **Verified** (API **04.00**, FW **02.04.00**) |
| Automatic prepare in capture (`ensure_before_rx`) | **Hardware acceptance-tested** |
| Runtime PHY after full power cycle (tested baseline) | **Did not persist** — see below |
| Applying **250 kbit/s / 1 Mbit/s** as a desired PUT profile | **Not acceptance-tested** |

## Verified baseline (desk / Office hardware)

| Field | Value |
|-------|-------|
| Device | CANsub.2 **7413f810** |
| Hardware | **01.00** |
| Firmware | **02.04.00** |
| API | **04.00** |
| Connection tested | Ethernet (`7413f810-eth.local`) |

Do not assume identical behaviour on other firmware or API versions without re-test.

## Verified PHY write contract

**`PUT /api/can/{channel}/phy`**

- Header: `Content-Type: application/json`
- Success: HTTP **200** (response body may be empty)

Required JSON fields (observed successful webCAN and CAN Research apply):

```json
{
  "listen_only": <bool>,
  "auto_reset": <bool>,
  "error_frames": <bool>,
  "tx_ack_frames": <bool>,
  "timing": { "brp": <int>, "seg1": <int>, "seg2": <int>, "sjw": <int> },
  "timing_data": { "brp": <int>, "seg1": <int>, "seg2": <int>, "sjw": <int> }
}
```

### Verified 500 kbit/s / 1 Mbit/s segment preset (80 MHz)

| Segment | brp | seg1 | seg2 | sjw |
|---------|-----|------|------|-----|
| `timing` | 4 | 31 | 8 | 4 |
| `timing_data` | 4 | 15 | 4 | 4 |

**Read path:** `GET /api/can/{channel}/phy` returns segment objects; CAN Research derives
nominal/data bitrates for preflight comparison.

## Historical investigation (HTTP 400)

Early automated PUT attempts failed with **HTTP 400** because the body omitted
**`tx_ack_frames`** (required on API 04.00). An alternate nominal segment set (`brp=2`)
still mathematically equals 500 kbit/s but was not the webCAN-proven choice.

## CAN Research behaviour (summary)

- Configured `[cansub.channels.N]` supplies desired nominal/data bitrates (and optional
  explicit segments / PHY flags).
- **500000 / 1000000** maps to the verified segment preset above; other pairs need
  explicit `timing` / `timing_data` in config (no arbitrary bitrate auto-derive).
- **`connection_policy = "ensure_before_rx"`** (see [CANSUB_SETUP.md](CANSUB_SETUP.md)):
  inactive/stopped/default-looking PHY → PUT → GET read-back → bounded passive RX proof
  (≥1 frame) → persistent capture. Failures: `timing_put_failed`, `timing_verify_failed`,
  `timing_proof_failed` — **no false capture session**.
- **Active timing mismatch:** fail closed; no silent overwrite (webCAN/vendor remediation
  may still apply).

Implementation flag: `CANSUB_PHY_PUT_VERIFIED` in code (true for this baseline).

## Hardware acceptance (2026-03)

### Power cycle → automatic prepare → live capture (success)

After a **complete CANsub + EDGE101 power cycle**, `device timing-check` showed
**250 kbit/s / 1 Mbit/s** and **inactive_or_ambiguous** (channel **stopped**) — the
stopped/default-looking state, not an active bus mismatch.

With configured **500 kbit/s / 1 Mbit/s** and **`ensure_before_rx`**, `capture start`:

1. Classified **INACTIVE_OR_AMBIGUOUS** (not mismatch)
2. Applied configured **500k/1M** via verified PUT
3. **GET /phy** read-back succeeded
4. Bounded passive RX proof observed real bus traffic
5. Created persistent capture only after proof (**39 frames**, **3 s**, session completed)

No webCAN intervention required.

**Persistence note (this device/FW/API only):** the applied **500k/1M** runtime PHY **did
not survive** the power cycle; timing-check returned to **250k/1M** stopped state until
prepare ran again. Channel **stopped** when idle is expected and does not invalidate a
successful apply during capture.

### Zero-frame failure path (success)

With no visible frames after apply + read-back:

- Passive proof observed **zero frames**
- Raised **`timing_proof_failed`**
- **No** persistent capture row created

### 250 kbit/s preset caution

**Observed:** stopped/default-looking **250k/1M** after power cycle (read-side).

**Verified via PUT acceptance:** recovery **to configured 500k/1M** on the tested baseline.

**Not acceptance-tested:** deliberately configuring **250k/1M** as the desired operating
profile through CAN Research PUT (preset retained from earlier GET examples only).

## Open / re-test after firmware change

- PHY persistence across reboot/power cycle on other devices or firmware
- PUT acceptance for **250k/1M** as a target profile
- API differences outside **04.00** / **02.04.00**

If PUT fails after upgrade, capture one successful webCAN Network request (method, URL,
body, response) and reconcile this document.
