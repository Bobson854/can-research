# CANsub.2 PHY / timing REST API — investigation (2026-03)

## Status summary

| Topic | Status |
|-------|--------|
| Read PHY (`GET /api/can/{channel}/phy`) | **Verified** in project |
| Write PHY (`PUT /api/can/{channel}/phy`) | **Verified** on API **04.00** / FW **02.04.00** (webCAN observation) |
| Automatic PHY apply in capture prepare | **Enabled** when `CANSUB_PHY_PUT_VERIFIED` is true |
| Persistence across power cycle | **Not observed** — do not assume |

## Verified on

- CANsub.2 device **7413f810**
- Firmware **02.04.00**
- API **04.00**

## Verified PHY write

**`PUT /api/can/{channel}/phy`**

- Header: `Content-Type: application/json`
- Success: HTTP **200** (response body may be empty)

### Observed successful JSON body (webCAN)

```json
{
  "listen_only": false,
  "auto_reset": true,
  "error_frames": false,
  "tx_ack_frames": true,
  "timing": {
    "brp": 4,
    "seg1": 31,
    "seg2": 8,
    "sjw": 4
  },
  "timing_data": {
    "brp": 4,
    "seg1": 15,
    "seg2": 4,
    "sjw": 4
  }
}
```

At 80 MHz CAN clock this pair yields **500 kbit/s** nominal and **1 Mbit/s** data.

### Read path (unchanged)

**`GET /api/can/{channel}/phy`** — segment objects `timing` / `timing_data`; bitrates are
derived in CAN Research for preflight comparison.

## Previous HTTP 400 (likely cause)

Earlier automated PUT attempts omitted **`tx_ack_frames`**, which is present on every
successful webCAN PUT observed on API 04.00. The API likely rejected the incomplete body
with HTTP 400. The earlier payload also used a different nominal segment set (`brp=2`) that
still mathematically equals 500 kbit/s but was not the webCAN-proven segment choice.

## CAN Research implementation

- `resolve_apply_phy_payload()` builds the verified schema from config.
- Known bitrate pair **500000 / 1000000** maps to the observed segment preset.
- Other bitrate pairs require explicit `timing` / `timing_data` in `config.toml` or a
  future verified preset — no silent derivation for arbitrary bitrates.
- After PUT: **GET /phy** read-back via `compare_phy_to_expectation()`, then passive RX
  proof (must observe at least one frame before capture when preparation runs).

## Not verified / open questions

- Persistence across CANsub reboot or power cycle
- Whether **250 kbit/s** presets match device-accepted segment tables (bitrate-only preset
  retained from earlier desk GET examples, not re-validated via PUT)
- API differences on firmware or API versions other than 04.00 / 02.04.00

## Manual re-check (optional)

If PUT fails after a firmware upgrade, repeat the webCAN Network capture procedure
(documented in earlier revisions of this file): change timing in webCAN only, record
method/URL/body/response, restore known-good timing.
