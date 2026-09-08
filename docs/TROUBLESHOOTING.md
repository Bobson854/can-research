# Troubleshooting

Practical decision guide for CAN Research installations.

**Setup guides:** [INSTALLATION.md](INSTALLATION.md) · [CANSUB_SETUP.md](CANSUB_SETUP.md) ·
[MCP_SETUP.md](MCP_SETUP.md) · [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md)

---

## Decision logic (live research path)

```text
CANsub reachable?
  no  → network / hostname / power / TLS (see A)
  yes
    ↓
channel healthy?
  no  → bitrate / wiring / listen_only / bus errors (see H)
  yes
    ↓
observe_live_traffic returns frames?
  no  → bus silent, wrong channel, or config (see B, H)
  channel_rx_in_use → WebSocket owned elsewhere (see C)
  yes → research path healthy — preflight passed
```

Aligns with [CAN Signal Research Skill](../skills/can-signal-research/SKILL.md) V2 preflight.

---

## A. CANsub unreachable

**Symptoms:** `device info` fails; MCP `get_cansub_device_status` errors; connection timeout.

**Checks:**

1. CANsub powered and on network (USB or Ethernet)
2. Correct host in config: `uv run canresearch config show`
3. Prefer mDNS hostname (`<device-id>-usb.local`) over a stale USB IP
4. Ping or browse to device; try webCAN in browser
5. `verify_tls = false` for `.local` / IP if certificate hostname mismatches
6. Firewall blocking HTTPS (443) to CANsub

**Commands:**

```powershell
uv run canresearch config set-host your-device-id-usb.local
uv run canresearch device info
```

Bench notes: [CANSUB_CONNECTION.md](CANSUB_CONNECTION.md).

---

## B. No frames in live observation

**Symptoms:** `observe_live_traffic` succeeds but returns zero frames; CLI `device rx` shows 0 frames.

**This is not `channel_rx_in_use`** — the channel was free but the bus was silent or misconfigured.

**Checks:**

1. CAN wiring and termination
2. Other nodes transmitting (ECU powered, bus active)
3. Correct **channel** selected (1 vs 2)
4. Bitrate matches bus (500 kbit/s typical on J1939 benches)
5. `listen_only` setting — on some benches must be **false** for ACK (see CANSUB_SETUP)
6. Channel status error counters increasing

**Do not** start `start_live_capture` for signal research when observation already shows no traffic.

---

## C. `channel_rx_in_use`

**Symptoms:** MCP returns `channel_rx_in_use` for `observe_live_traffic` or capture.

**Meaning:** Another **WebSocket client owns that CANsub channel** — **not** “no CAN traffic.”

**Common owners:**

- webCAN on that channel
- Active MCP `start_live_capture` on that channel
- Another observer application
- Stuck MCP process still holding the socket (see D)

**Fix:**

1. Disconnect webCAN **on that channel only** (use another channel for display if needed)
2. Stop other captures: `uv run canresearch capture stop [<session-id>]`
3. Optional dual-channel bench layout: channel 1 = MCP, channel 2 = webCAN (same bus)

Do **not** reboot the whole system as the first response.

---

## D. Stuck capture / session remains recording

**Symptoms:** Capture shows recording; `stop_live_capture` fails; channel stays busy.

**Likely cause:** Local MCP process still holds the WebSocket.

**Recovery:**

1. Try `stop_live_capture` with the session ID
2. Stop the MCP server process (Ctrl+C in its terminal)
3. Restart MCP: `uv run canresearch mcp serve ...`
4. Re-run preflight before new capture

Full system reboot is a last resort, not the first fix.

---

## E. Tunnel client not polling / unhealthy

**Symptoms:** ChatGPT connector offline; tunnel health endpoint not responding.

**Checks:**

1. Run `.\status.cmd` — note whether MCP, connection config, secrets, executable, or health failed
2. Is `tunnel-client.exe` running?
3. For `openai-runtime-env`: are namespaced User env vars set? Run `uv run python scripts\connection_windows.py configure` if missing
4. For legacy profile runtimes: correct `--profile` for this machine (`can-research-<instance_key>`)?
5. Health listener port free (`127.0.0.1:<port>` from `data/config.toml`)?
6. Local MCP still up at `http://127.0.0.1:8765/mcp`?
7. Runtime API key / tunnel identity still valid (recreate remote resources only if deliberately lost)

See [MCP_SETUP.md](MCP_SETUP.md) — normal startup vs one-time setup.

---

## F. MCP server unreachable

**Symptoms:** `mcp tools` fails locally; `mcp_verify_http.py` fails; ChatGPT tools unavailable.

**Checks:**

1. MCP terminal still running?
2. Correct command: `uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp`
3. Port 8765 not used by another process
4. HTTP GET to `/mcp` returning 400 is **normal** without session — use verify script

```powershell
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

---

## G. webCAN works but MCP cannot observe

Usually **`channel_rx_in_use`** — webCAN owns the channel MCP needs.

**Fix:** Release MCP target channel in webCAN, or use dual-channel layout (MCP on 1, webCAN on 2).

---

## H. Wrong channel / bitrate / physical connection

**Symptoms:** Frames on webCAN but not on MCP channel; zero-frame captures; `error_active`
state; garbage/error frames; bus errors climbing.

**Checks:**

1. MCP using same physical channel as working webCAN view
2. **Timing preflight** — if `[cansub.channels.<n>]` is configured:
   ```powershell
   uv run canresearch device timing-check <n>
   ```
   A `timing_mismatch` error means CANsub PHY bitrates differ from config — correct
   timing in webCAN, then re-check. This is **not** `channel_rx_in_use`.
3. Bitrate and `listen_only` match working bench configuration
4. `get_cansub_channel_status` — compare counters, `timing_preflight`, and state
5. Swap channel 1 ↔ 2 test if wiring unclear

**Distinct errors:**

| Error | Meaning |
|-------|---------|
| `timing_mismatch` | Device PHY ≠ configured expected nominal/data bitrate |
| `timing_unknown` | Expected timing configured but device PHY could not be verified |
| `channel_rx_in_use` | Another WebSocket client owns the channel (webCAN, other capture) |

---

## I. Windows CMD path / drive confusion

**Symptoms:** `'.\tunnel-client.exe' is not recognized` after `cd K:\path` in **cmd.exe**.

**Cause:** `cmd.exe` does not switch drives with plain `cd K:\path`.

**Fix (cmd):**

```cmd
cd /d K:\path\to\tunnel-client
tunnel-client.exe run --profile can-research-workshop ...
```

Or use full executable path. **PowerShell:** `cd K:\path` works without `/d`.

---

## J. Restart procedure after reboot

After Windows power cycle (verified behaviour):

**Persist without restart:** ChatGPT connector, tunnel profile, API key, installed Skill.

**Must restart (two processes):**

1. CAN Research MCP server
2. OpenAI tunnel client (if used)

Do **not** recreate tunnel, connector, or Skill unless configuration was lost.

→ [MCP_SETUP.md — Normal startup after reboot](MCP_SETUP.md#normal-startup-after-reboot)

---

## Wrong backend connected

When multiple ChatGPT connectors exist:

```text
get_instance_info
```

Confirm `instance_key` matches the machine you intend. The Skill is portable — always verify.

---

## Still stuck?

| Area | Deep-dive doc |
|------|----------------|
| CANsub bench history | [CANSUB_CONNECTION.md](CANSUB_CONNECTION.md) |
| Office MCP deployment record | [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md) |
| Per-instance checklist | [MCP_CONNECTION.md](MCP_CONNECTION.md) |
| Multi-machine model | [MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md) |
