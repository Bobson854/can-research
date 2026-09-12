# CANsub.2 PHY / timing REST API — investigation (2026-03)

This document records **evidence in the can-research repository** about configuring
CAN channel PHY/timing on CANsub.2 **API 04.00**. It does **not** define a verified
write contract.

## Status summary

| Topic | Status |
|-------|--------|
| Read PHY (`GET /api/can/{channel}/phy`) | **Verified** in project (bench + tests) |
| Write PHY (`PUT /api/can/{channel}/phy`) | **Not verified** — HTTP 400 on desk; no captured response body in repo |
| Automatic PHY apply in capture prepare | **Disabled** (`CANSUB_PHY_PUT_VERIFIED = False`) |
| Official OpenAPI / vendor PHY write spec in repo | **Absent** |

## Repository evidence reviewed

- `docs/CANSUB_CONNECTION.md` — endpoint table lists **GET** `/phy` only (read-only).
- `docs/CANSUB_SETUP.md` — onboarding; previously implied PUT was “documented” (corrected here).
- `src/canresearch/cansub/client.py` — `get_channel_phy`, `set_channel_phy` → PUT.
- `src/canresearch/cansub/timing.py` — GET shape, bitrate derivation, **candidate** PUT payload builder, gate flag.
- `src/canresearch/core/timing_preflight.py`, `capture_prepare.py` — preflight and prepare workflow.
- `src/canresearch/config.py` — `[cansub.channels.N]` profiles.
- `src/canresearch/cli.py` — `device timing-check`, `device apply-phy-timing` (blocked when gate false).
- Tests: `test_timing_preflight.py`, `test_capture_prepare.py`, `test_cansub_client.py`, `test_cansub_channel.py` (GET fixtures; PUT path mocked only).
- Git: commit `30effd2` added timing preflight and PUT client code; no stored 400 response JSON in history.

External package **python-can-cansub** is referenced in code comments (80 MHz clock, segment model) but is **not vendored** in this repository and was **not** used here as proof of the HTTP write schema.

## What is conclusively known (read path)

### Endpoint

- **`GET /api/can/{channel}/phy`** — returns a JSON object.

### Observed GET fields (bench + fixtures)

Documented in `CANSUB_CONNECTION.md` and `tests/test_cansub_channel.py`:

- Boolean flags: `listen_only`, `auto_reset`, `error_frames` (when present).
- Segment objects: `timing`, `timing_data`, each with integer `brp`, `seg1`, `seg2`, `sjw`.
- **No** `nominal_bitrate` / `data_bitrate` fields on the wire.

### Bitrate interpretation (read-side, project convention)

Nominal and data bitrates are **derived** from segments using **80 MHz** CAN clock
(`CANSUB_CAN_CLOCK_HZ` in `timing.py`), aligned with comments citing python-can-cansub /
CSS integration. This derivation is used for **preflight comparison** against
`config.toml` `nominal_bitrate` / `data_bitrate`; it is not a vendor guarantee without
independent confirmation.

### Channel activity

- **`GET /api/can/{channel}`** exposes channel `state` (e.g. `stopped`, `error_active`).
- Stopped/inactive channels often report **default-looking** PHY (commonly derived **250k / 1M**), which must not be treated as an active bus mismatch (`TimingCompatibility.INACTIVE_OR_AMBIGUOUS`).

### Success for GET

- HTTP **200** with JSON object (`CansubClient.get_json`).

## What is NOT proven (write path)

The following remain **unknown or unverified** in this repository:

1. **Whether** API 04.00 supports REST mutation of PHY at all, or only via webCAN / another path.
2. **HTTP method** if mutation exists (project *assumes* PUT; no proof).
3. **Exact JSON body** for a successful write (must not be inferred from GET shape alone).
4. **Required channel state** before write (stopped vs running; WS disconnected or not).
5. **Partial vs full body** (all flags required vs delta; unknown fields rejected?).
6. **Persistence** across channel stop/start, reboot, or power cycle.
7. **CAN FD data timing** — whether `timing_data` alone is sufficient or other enablement exists elsewhere.
8. **Success response** (200 + echo body vs 204 vs redirect).
9. **API version differences** for PHY write between older API versions and 04.00.

### Negative evidence (weak but recorded)

- Desk test: **`PUT /api/can/{channel}/phy`** with the payload built by
  `resolve_apply_phy_payload()` returned **HTTP 400** on API **04.00** (comment in
  `timing.py`; **response body not archived** in the repo).
- Therefore the current payload builder is a **hypothesis**, not a contract.

### Candidate payload (implementation only — not verified)

When `CANSUB_PHY_PUT_VERIFIED` is true, the code would send:

```json
{
  "listen_only": <bool>,
  "auto_reset": <bool>,
  "error_frames": <bool>,
  "timing": { "brp", "seg1", "seg2", "sjw" },
  "timing_data": { "brp", "seg1", "seg2", "sjw" }
}
```

with segments from config tables or from `TIMING_PRESET_BY_BITRATES` for known
(250k/1M) and (500k/1M) pairs. **Do not treat this as API documentation.**

## Planned manual observation (webCAN)

Use this when the write contract must be established without guessing.

**Goal:** Capture the **actual** HTTP request webCAN sends when changing CAN1 timing.

**Preconditions**

- Use the Office unit or a bench CANsub on a **known-good** profile (e.g. 500k / 1M on CAN1).
- Ensure **no other WebSocket client** holds the channel (close MCP capture / CLI `device rx`).
- Prefer Ethernet host already in config (e.g. `7413f810-eth.local`).

**Steps**

1. Open webCAN in **Chrome or Edge** → `F12` → **Network** tab.
2. Enable **Preserve log**. Filter: `phy` or `api/can`.
3. Note baseline: in another terminal,  
   `uv run canresearch device channel-info 1`  
   and optionally save `GET .../phy` JSON from Network (read-only baseline).
4. In webCAN, change **only** CAN1 timing (e.g. switch to a **different preset** you can
   revert, such as 250k/1M if currently 500k/1M). Do **not** change WiFi, other channels,
   or unrelated device settings.
5. In Network, find the request triggered by Apply/Save. Record for that request:
   - URL (path and channel number)
   - Method (PUT, POST, PATCH, …)
   - Request headers (`Content-Type`, …)
   - **Full request payload** (copy as cURL or raw JSON)
   - Status code and **full response body** on success and on failure
6. **Read-back:** run `device channel-info 1` or repeat GET `/phy` and compare segments.
7. **Restore:** set CAN1 back to **500k / 1M** in webCAN using the same UI path; confirm
   GET `/phy` and `device timing-check 1` match config.

**Do not** paste unverified payloads into production automation until one successful
round-trip is recorded and reviewed.

## Recommended next implementation step (after evidence)

1. Archive observed method, URL, body, and 200-level response in this doc (or a
   `fixtures/` snippet with secrets redacted).
2. Set `CANSUB_PHY_PUT_VERIFIED = True` only if observation matches the implemented
   client (or adjust `set_channel_phy` / payload builder to match observation exactly).
3. Re-run desk test: inactive channel + `connection_policy = "ensure_before_rx"` → PUT →
   GET verify → passive RX proof → capture.
4. Add an integration test using **recorded** request/response fixtures, not invented JSON.

## Related project behaviour (current implementation)

See `timing_preflight.py` and `capture_prepare.py`:

- **Preflight** compares configured bitrates to GET `/phy` (with inactive/default handling).
- **`connection_policy = "none"`** — refuse active **mismatch** only.
- **`connection_policy = "ensure_before_rx"`** — on match, short passive RX proof; on
  inactive/ambiguous PHY, **fail** with `timing_prepare_required` until webCAN configure
  (PUT disabled).

CLI `device apply-phy-timing --yes` is intentionally **refused** while the gate flag is false.
