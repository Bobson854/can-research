# MCP Connector Install and Recovery Guide

> **Deployment record — Office workstation.**
>
> This file records the verified Office deployment and recovery history. Canonical setup and startup instructions are in [MCP_SETUP.md](MCP_SETUP.md).

## Current Office deployment

| Item | Value |
|---|---|
| Instance key | `office` |
| Display name | `CAN Research - Office` |
| Local MCP URL | `http://127.0.0.1:8765/mcp` |
| MCP transport | `streamable-http` |
| Tunnel profile | `can-research-office` |
| Tunnel health listener | `127.0.0.1:8081` |
| Permanent tunnel-client location | `%LOCALAPPDATA%\CAN Research\tunnel-client\tunnel-client.exe` |
| Normal startup | `start-can-research.cmd` |
| Health check | `status.cmd` |

The tool count is intentionally not hard-coded here. Verify the current registry with:

```cmd
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

## Normal Office startup

After Windows reboot:

```cmd
cd /d C:\dev\Can_Research\Can-Research_V1\can-research
start-can-research.cmd
```

That command starts/verifies both the CAN Research MCP server and the OpenAI tunnel client. Use the existing ChatGPT connector after the script reports ready.

For diagnostics:

```cmd
status.cmd
```

Do **not** delete/recreate the OpenAI tunnel, tunnel-client profile, runtime API key, ChatGPT connector, or Skills as part of ordinary reboot recovery.

## Historical Downloads-path deployment

The first verified Office deployment on 2026-09-05/06 ran the OpenAI client directly from:

```text
K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe
```

with:

```cmd
K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

That was functional but intentionally **retired** because Downloads is not a stable install location.

`setup.cmd` now migrates an existing extracted `tunnel-client.exe` from normal Downloads locations (including other drive letters such as `K:\Downloads`) into:

```text
%LOCALAPPDATA%\CAN Research\tunnel-client\tunnel-client.exe
```

The original tunnel-client **profile is preserved**; moving/copying the executable does not recreate the `can-research-office` profile or control-plane tunnel.

## Why port 8081

The Office workstation already had SABnzbd bound to `127.0.0.1:8080`, so the OpenAI tunnel health/admin listener was moved to `127.0.0.1:8081`. Preserve that value for this instance unless there is a deliberate conflict-resolution change.

## Existing profile and secret locations

The Office tunnel profile is stored by the tunnel client in the Windows user configuration area, historically:

```text
C:\Users\Office\.config\tunnel-client\can-research-office.yaml
```

The runtime API key is persisted as the user environment variable:

```text
CONTROL_PLANE_API_KEY
```

Never commit or paste the key into documentation/support chats.

## Recovery sequence

Always recover inside-out:

1. Run `status.cmd`.
2. If local MCP is down, run `start-can-research.cmd`.
3. If the tunnel executable is missing, run `setup.cmd` to restore/migrate the permanent copy.
4. If tunnel `doctor` reports profile/auth failure, repair the existing profile/API key.
5. Only after MCP and tunnel both pass should the ChatGPT connector be investigated.

A stopped local process is **not** a reason to recreate the connector.

## Verified history

- **2026-09-05:** Office MCP/tunnel/ChatGPT path verified end-to-end.
- **2026-09-06:** Reboot recovery verified: persisted profile/API key/connector survived; only local MCP and tunnel runtime needed restarting.
- **2026-09-06:** Windows startup hardening introduced permanent tunnel-client installation, one-command startup, and tunnel-aware status diagnostics after the historical Downloads-path weakness was identified.

For portable/multi-machine installation, use [MCP_SETUP.md](MCP_SETUP.md), not this deployment record.
