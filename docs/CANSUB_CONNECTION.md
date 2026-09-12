# CANsub.2 USB / Ethernet connection notes

> **Deployment record — not canonical installation instructions.**
>
> This document retains **desk-unit bench history**, verified firmware/API versions, and
> tested command output from development hardware. For current CANsub setup, see
> [CANSUB_SETUP.md](CANSUB_SETUP.md).

Observed behaviour on the development desk unit (Device ID `7413f810`). This is
**not** vendor-guaranteed documentation — it records what we have tested locally.

## Tested desk unit

| Field | Value |
|-------|-------|
| Device ID | `7413f810` |
| Hardware | `01.00` |
| Firmware (current baseline) | `02.04.00` |
| API (current baseline) | `04.00` |
| MAC | `04916244365e` |
| USB ID | `04D8&E487` |
| Channels | 1, 2 |

Preferred USB hostname:

```text
7413f810-usb.local
```

## USB IP vs mDNS hostname

Observed testing indicates the USB mDNS hostname is the preferred stable
identifier, while the USB IP address may change between power cycles.

| Method | Observed behaviour |
|--------|--------------------|
| USB IP | **Dynamic** — examples seen across power cycles include `10.158.28.1`, `10.174.12.1`, and `10.108.188.1` |
| USB mDNS hostname | **Preferred** — `7413f810-usb.local` has remained the useful stable device identifier during testing |

Do not treat the hostname as vendor-guaranteed permanent unless confirmed in
official CSS documentation.

**Recommendation:** configure the mDNS hostname rather than a temporary USB IP.

```powershell
uv run canresearch config set-host 7413f810-usb.local
uv run canresearch device info
```

## Firmware / API baseline

The device was originally tested on firmware **02.03.00** / API **03.00**.
Intermittent connectivity or name-resolution behaviour was observed during that
period.

After upgrading to firmware **02.04.00** / API **04.00**, the complete
connection and capture path was verified successfully on the desk unit. Earlier
intermittent connectivity was observed on 02.03.00 / 03.00, but a causal
firmware fix has **not** been established.

The CLI accepts any `MAJOR.MINOR` API version string returned by
`GET /api/version`; no code assumes 03.00 specifically.

## What works (verified on FW 02.04.00 / API 04.00)

- CANsub.2 USB networking to the Windows development laptop
- Direct **HTTPS REST** access on port **443** (`https://<host>/api/...`)
- Configured host (no `--host` required after `config set-host`)
- Read-only channel status for channels 1 and 2
- **WebSocket RX** on `wss://{host}/api/can/{channel}/ws` (binary HDLC-framed messages)
- **Persistent capture sessions** (JSONL frame store + SQLite metadata)
- **Configured timing preparation** (`connection_policy = "ensure_before_rx"`) on API
  **04.00** / FW **02.04.00** — verified PUT, GET read-back, passive frame proof before
  capture (hardware acceptance on device `7413f810`; see
  [CANSUB_PHY_API_INVESTIGATION.md](CANSUB_PHY_API_INVESTIGATION.md))
- CLI `--host` accepts either a **hostname** or an **IP address**

Early bench tests used USB with no CAN bus attached (zero frames expected).
Real EDGE101 two-node bench capture has since been verified over **Ethernet/PoE**.

## Ethernet vs USB (observed bench behaviour)

On this Windows development setup, **Ethernet/PoE was substantially more stable**
than USB NCM. USB-side subnet addresses changed between power cycles and showed
routing/mDNS instability. During Ethernet bench testing the device was reachable
at `192.168.50.39` — treat this as a **temporary test address**, not a permanent
configuration value.

## Two-node bench: Listen Only setting

On a two-node bench bus (EDGE101 + CANsub), observed testing showed **Listen Only
must be false** so the CANsub can ACK valid EDGE101 frames.

| Listen Only | Observed result |
|-------------|-----------------|
| `true` | ~3145 fps, ~96% bus load, retransmissions/errors, unstable WebSocket/webCAN |
| `false` | ~11 fps, 0% bus load, 0 bus errors, stable traffic |

This reflects tested bench behaviour on this setup, not a universal vendor requirement.

## Persistent configuration

Local settings are stored in `data/config.toml` (gitignored). See
`config.toml.example` for the template (`[instance]`, `[paths]`, `[cansub]`).

**Installation vs CANsub:** `instance_key` identifies the laptop/backend installation.
`[cansub].host` identifies whichever CANsub.2 is currently attached — the same
physical unit may move between installations; update the host when it moves.

Precedence for CANsub host:

1. CLI `--host` (explicit override)
2. `[cansub].host` in `data/config.toml`
3. Clear error if neither is set

## Endpoints exercised

| Endpoint | Purpose |
|----------|---------|
| `GET /api/version` | API version |
| `GET /api/info` | Device identity |
| `GET /api/can` | Channel list |
| `GET /api/can/{channel}` | Channel status |
| `GET /api/can/{channel}/phy` | Channel PHY timing (read-only) |
| `WS /api/can/{channel}/ws` | Live CAN RX (read-only; binary HDLC-framed messages) |

PHY **write** via **`PUT /api/can/{channel}/phy`** is verified on API **04.00** (schema
includes `tx_ack_frames`); see
[CANSUB_PHY_API_INVESTIGATION.md](CANSUB_PHY_API_INVESTIGATION.md).

## Capture preparation flow (configured timing)

When `[cansub.channels.<n>]` declares expected bitrates (and optionally
`connection_policy = "ensure_before_rx"`):

```text
configured desired timing
  → inspect channel + GET /phy
  → classify: active match | active mismatch | inactive/ambiguous
  → active mismatch: fail closed (no silent PHY overwrite)
  → ensure_before_rx + inactive/ambiguous: PUT → GET verify → passive RX proof
  → persistent capture only after successful proof (or match path per policy)
```

Stopped/default-looking **250 kbit/s / 1 Mbit/s** on an idle channel is
**inactive_or_ambiguous**, not proof of a live-bus mismatch. On the tested baseline,
runtime **500 kbit/s / 1 Mbit/s** did **not** survive a full power cycle until prepare
ran again.

Per vendor documentation, only **one WebSocket client** may be connected to each
channel at a time.

TLS: the device presents a hostname-based certificate. Direct IP or `.local`
access typically requires `verify_tls = false` in config until the CSS root
certificate is integrated.

## Verified command sequence

```powershell
uv run canresearch config show
uv run canresearch device info
uv run canresearch device channel-info 1
uv run canresearch device channel-info 2
uv run canresearch device rx 1 --duration 5
uv run canresearch capture start --channel 1 --duration 10 --name "edge101-ethernet-bench"
uv run canresearch session list
uv run canresearch session summary <session-id>
uv run canresearch session analyze <session-id>
```

### Example `device info` output (2026-03)

```text
CANsub.2
Host:       7413f810-usb.local
Status:     reachable
Device ID:  7413f810
API:        04.00
Hardware:   01.00
Firmware:   02.04.00
MAC:        04916244365e
USB ID:     04D8&E487
Channels:   1, 2
```

### Channel status (no bus connected)

Both channels reported `state: stopped`, zero frames, zero errors. Example PHY
timing: `timing = {brp: 4, seg1: 63, seg2: 16, sjw: 4}`,
`timing_data = {brp: 4, seg1: 15, seg2: 4, sjw: 4}`.

### WebSocket idle RX (channel 1)

```text
CANsub.2 RX
Host:       7413f810-usb.local
Channel:    1
Duration:   5 s
Status:     connected
Frames:     0
Result:     duration elapsed
```

Channel 2 idle RX has also succeeded. This path is read-only — no CAN
transmission is performed.

### Real CAN capture (EDGE101 bench, Ethernet)

Successful session: `9622f81f1e67` (`edge101-ethernet-bench`, channel 1, host
`192.168.50.39`, status `completed`, **116 frames** over ~10.2 s). Nominal bitrate
500 kbit/s, `listen_only: false`, `state: error_active` during capture.

Frame data: `data/sessions/9622f81f1e67/frames.jsonl` (gitignored). Analyze with:

```powershell
uv run canresearch session analyze 9622f81f1e67
```

### Persistent capture (zero frames, USB idle)

Successful session example: `4a5bfe6b65d0` (`desk-idle-fw204`, channel 1,
status `completed`, frames `0`). Frame data is stored under
`data/sessions/<session-id>/frames.jsonl` (gitignored).

Earlier failed sessions from connectivity attempts remain in SQLite as audit
history and are not deleted automatically.

## Live MCP research (passive)

The MCP server exposed **32 tools** at Office verification (2026-09-05); current baseline
is **41 tools** (28 read-only, 7 live, 6 signal research) — verify with
`uv run canresearch mcp tools`. See [MCP_SETUP.md](MCP_SETUP.md).
Live tools are **passive only** — no CAN transmission, no autonomous experimentation.

| Tool | Purpose |
|------|---------|
| `get_instance_info` | Backend installation identity (use when multiple connectors exist) |
| `get_cansub_device_status` | Device ID, firmware, API version, channels |
| `get_cansub_channel_status` | Bus state, counters, PHY config |
| `start_live_capture` | Background capture → session JSONL |
| `stop_live_capture` | Stop active capture by session_id |
| `observe_live_traffic` | Bounded aggregated traffic (3s default, max 15s) |
| `mark_experiment_event` | Annotation markers (baseline_start, scv2_extend, …) |
| `compare_experiment_windows` | Deterministic baseline vs action comparison |

**Concurrency:** one active capture per channel. `observe_live_traffic` returns
`channel_rx_in_use` if the channel WebSocket is owned by a capture.

**CLI equivalents:**

```powershell
uv run canresearch capture stop [<session-id>]
uv run canresearch session event add <session-id> --label baseline_start
uv run canresearch session event list <session-id>
uv run canresearch session compare <session-id> --baseline-event baseline_start --action-event scv2_extend
```

## Data flow (verified path)

```text
CANsub.2 (USB hostname or Ethernet)
  -> HTTPS REST (config, device info, channel status)
  -> WSS /api/can/{channel}/ws (RX)
  -> JsonlCaptureStore (data/sessions/.../frames.jsonl)
  -> SQLite session metadata (data/references/canresearch.db)
  -> session analyze -> observed_pgns + reference lookup
```
