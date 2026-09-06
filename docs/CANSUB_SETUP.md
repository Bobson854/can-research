# CANsub.2 setup

Public guide for connecting a CSS Electronics CANsub.2 to CAN Research.

**Bench-tested detail:** [CANSUB_CONNECTION.md](CANSUB_CONNECTION.md) (desk unit notes,
verified firmware/API versions, historical bench lessons).

## Connection model

CAN Research talks to CANsub.2 over:

- **HTTPS REST** — device info, channel status, PHY timing (read-only)
- **WebSocket** — passive CAN RX on `wss://<host>/api/can/{channel}/ws`

Configure the host once in `data/config.toml` or via CLI:

```powershell
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch config show
uv run canresearch device info
```

Host precedence:

1. CLI `--host` (explicit override)
2. `[cansub].host` in `data/config.toml`
3. Error if neither is set

## USB vs Ethernet

| Method | Notes |
|--------|--------|
| **USB mDNS hostname** | Preferred stable identifier, e.g. `<device-id>-usb.local` |
| **USB IP** | Often changes between power cycles — avoid hard-coding |
| **Ethernet / PoE** | Often more stable on bench setups; use IP or hostname as appropriate |

TLS: CANsub presents a hostname-based certificate. Direct IP or `.local` access
typically requires `verify_tls = false` in config until a trusted root is integrated.

## Channel selection

CANsub.2 exposes channels **1** and **2**. Check availability:

```powershell
uv run canresearch device channel-info 1
uv run canresearch device channel-info 2
```

Choose the channel wired to your bus. MCP and CLI capture use `--channel <n>`.

## Bitrate and PHY timing

CAN bitrate and timing are configured on the CANsub (via webCAN or vendor tools). CAN
Research reads PHY timing read-only via REST — it does not change bus timing.

Verify channel status shows expected bus state before research:

```powershell
uv run canresearch device channel-info 1
```

Look for `state`, error counters, and `listen_only` setting. On some benches,
**Listen Only must be false** so the CANsub can ACK valid frames from other nodes.

## Basic verification

```powershell
uv run canresearch device info
uv run canresearch device channel-info 1
uv run canresearch device rx 1 --duration 5
```

Short passive RX test (CLI):

```powershell
uv run canresearch capture start --channel 1 --duration 10 --name "smoke-test"
uv run canresearch session list
uv run canresearch session summary <session-id>
```

## webCAN and dual-channel workflow

webCAN (browser UI) and CAN Research both use WebSocket RX. **CANsub.2 allows only one
WebSocket client per channel.**

### `channel_rx_in_use`

If MCP returns **`channel_rx_in_use`**, another WebSocket client owns that channel.

This means **channel ownership conflict** — **not** “the CAN bus has no traffic.”

Common owners:

- webCAN on that channel
- An active MCP live capture
- Another live observer
- Another application

**Recovery:** free only the intended research channel (disconnect webCAN on that channel,
stop the other capture, etc.). Do not restart the whole system as a first response.

### Optional bench pattern (two channels on same bus)

When **both channels are physically connected to the same CAN bus**, a useful debug layout:

| Channel | Use |
|---------|-----|
| **1** | MCP research (capture / `observe_live_traffic`) |
| **2** | webCAN operator display |

This is **optional** — only when you have wired both channels to the same bus and want
simultaneous MCP research plus a human display. It is not a wiring requirement.

## Passive RX research model

CAN Research live MCP tools are **passive only**:

- Observe traffic, capture sessions, mark experiment events
- **No CAN TX** through MCP or the standard live workflow

Physical machine actions remain human-in-the-loop.

## MCP live tools (CANsub)

| Tool | Purpose |
|------|---------|
| `get_cansub_device_status` | Device ID, firmware, API, channels |
| `get_cansub_channel_status` | Bus state, counters, PHY |
| `observe_live_traffic` | Bounded traffic snapshot (default ~3 s, max 15 s) |
| `start_live_capture` / `stop_live_capture` | Passive session capture |
| `mark_experiment_event` / `compare_experiment_windows` | Experiment windows |

Preflight before capture:

```text
get_instance_info → get_cansub_device_status → get_cansub_channel_status
  → observe_live_traffic → confirm frames → start_live_capture
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for decision logic when things fail.

## Data flow

```text
CANsub.2
  → HTTPS REST (status)
  → WSS /api/can/{channel}/ws (RX)
  → JSONL frames (data/sessions/...)
  → SQLite session metadata
  → analysis / reference lookup / MCP tools
```
