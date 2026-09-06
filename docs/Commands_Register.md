# Office startup command register

> **Deployment record — not canonical installation instructions.**
>
> Quick cheat sheet for the **Office** workstation only. For portable setup and current
> conventions, see [MCP_SETUP.md](MCP_SETUP.md#normal-startup-after-reboot).

After a Windows reboot, start these two processes (substitute paths on other machines).

## Terminal 1 — CAN Research MCP

```powershell
cd C:\dev\Can_Research\Can-Research_V1\can-research
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

## Terminal 2 — OpenAI tunnel

Full path (works from any drive/shell):

```powershell
K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

Then use the existing ChatGPT connector — no Skill reinstall required.

Verify backend: `get_instance_info` · tool count: `uv run canresearch mcp tools`.
