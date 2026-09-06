# CANsub.2 and MCP setup

## CANsub connection

CAN Research uses HTTPS REST for device/channel status and WebSocket for passive RX.

Configure host:

```powershell
uv run canresearch config set-host <device-host>
uv run canresearch device info
```

USB mDNS hostnames are preferred over changing USB IPs when available. Direct IP/`.local` often needs `verify_tls=false` with the current device certificate model.

## Channel verification

```powershell
uv run canresearch device channel-info 1
uv run canresearch device channel-info 2
```

CANsub.2 has one WebSocket client per channel. `channel_rx_in_use` means another client owns the channel, not that traffic is absent.

Common owners:

- webCAN
- active MCP capture
- another observer/application

Free only the intended research channel first.

Optional bench layout when both channels are physically connected to the same bus:

- channel 1: MCP research
- channel 2: webCAN display

## Passive live preflight

```text
get_instance_info
→ get_cansub_device_status
→ get_cansub_channel_status
→ observe_live_traffic
→ frames present
→ capture if needed
```

No CAN TX is part of onboarding/current signal research.

## Local MCP

Start:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Verify separately:

```powershell
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

A plain HTTP GET can fail with a session-related 400 and still have a healthy MCP endpoint. Use the project verification commands.

## Tunnel

Use the existing tunnel profile after one-time configuration:

```powershell
C:\path\to\tunnel-client.exe run --profile can-research-<instance_key> --health.listen-addr 127.0.0.1:8081
```

Use any free health port; 8081 is a convention, not a requirement.

Then verify the existing ChatGPT connector with `get_instance_info`.
