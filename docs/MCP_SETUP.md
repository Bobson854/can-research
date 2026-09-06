# MCP setup

Public guide for exposing a local CAN Research MCP server to ChatGPT or other MCP clients.

**Office verified deployment record:** [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md)
(one-time install checklist, reboot recovery dates, deployment-specific paths).

**Per-instance verification checklist:** [MCP_CONNECTION.md](MCP_CONNECTION.md).

## Three independent states

Before tools work in ChatGPT, all three must agree:

1. **Local MCP server** — healthy, current tool registry, correct `get_instance_info`
2. **Tunnel client** (if using OpenAI Secure MCP) — healthy, points at local MCP
3. **ChatGPT connector** — schema discovered, enabled in chat/workspace

Troubleshoot in that order. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Normal startup after reboot

Once configured **once**, do **not** repeat full installation. Start only:

### Terminal 1 — CAN Research MCP

From your repository root:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Leave running. Optional local check:

```powershell
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

### Terminal 2 — OpenAI tunnel client (if used)

Use the **full path** to `tunnel-client.exe` so drive/shell context does not matter:

```powershell
C:\path\to\tunnel-client.exe run --profile can-research-<instance_key> --health.listen-addr 127.0.0.1:8081
```

Choose a health listener port free on your machine (e.g. `8081` if `8080` is taken).

**Command Prompt** — switching drives requires `/d`:

```cmd
cd /d C:\path\to\tunnel-client
tunnel-client.exe run --profile can-research-workshop --health.listen-addr 127.0.0.1:8081
```

**PowerShell** — `cd` to another drive works without `/d`:

```powershell
cd C:\path\to\tunnel-client
.\tunnel-client.exe run --profile can-research-workshop --health.listen-addr 127.0.0.1:8081
```

Then use the **existing** ChatGPT connector.

### Do NOT recreate after every reboot

Unless configuration was lost or deliberately changed:

- OpenAI tunnel (control plane)
- Runtime API key
- Tunnel-client profile
- ChatGPT MCP connector
- Installed Skills (**can-onboarding**, **can-reference-builder**, **can-signal-research** as needed)

Foreground terminals are the currently verified startup method.

---

## One-time setup

### 1. Prove local MCP first

```powershell
uv run canresearch config show
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

In a second terminal:

```powershell
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

Expected baseline: **41 tools** (28 read-only / 7 live / 6 signal research).

Verify the **current** count on your machine — do not treat documentation as immutable:

```powershell
uv run canresearch mcp tools
```

Same registry for stdio and streamable HTTP.

Default endpoint convention:

```text
http://127.0.0.1:8765/mcp
```

Port **8765** is a project convention (avoids common dev ports). Each machine uses
localhost independently — the same port on different laptops does not conflict.

A plain `GET` to `/mcp` may return HTTP **400** (missing session ID). That does **not**
mean the server is down — use `mcp tools` or `mcp_verify_http.py`.

### 2. Stdio transport (Cursor, Claude Desktop, etc.)

For desktop MCP clients that use stdio:

```powershell
uv run canresearch mcp serve
```

Same tool registry as streamable HTTP (verify with `uv run canresearch mcp tools`).

### 3. OpenAI Secure MCP tunnel (ChatGPT)

Download the OpenAI `tunnel-client` for your platform from OpenAI Platform documentation.

Typical flow:

1. Create a tunnel in OpenAI Platform pointing at your local MCP URL
2. Create a tunnel-client **profile** (name convention: `can-research-<instance_key>`)
3. Run `tunnel-client.exe run --profile <name> --health.listen-addr 127.0.0.1:<port>`
4. Create a ChatGPT MCP connector / plugin linked to that tunnel
5. Enable the connector in ChatGPT

Each machine gets its **own** tunnel, profile, and connector — see
[MULTI_INSTANCE_DEPLOYMENT.md](MULTI_INSTANCE_DEPLOYMENT.md).

Do not commit API keys, tunnel IDs, or profile secrets to the repository.

### 4. ChatGPT connector

In ChatGPT, add an MCP connector for your tunnel. Name it to match your instance
(e.g. `CAN Research - Workshop`). After connect, verify:

```text
get_instance_info
```

Confirm `instance_key` and `display_name` match `data/config.toml`.

### 5. Install Skills

See [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md). Typical order: **can-onboarding** →
**can-reference-builder** (when reference material exists) → **can-signal-research**.

---

## Portable conventions

| Item | Convention |
|------|------------|
| MCP URL | `http://127.0.0.1:8765/mcp` |
| Transport | `streamable-http` |
| Tool count (baseline) | 41 — verify with `uv run canresearch mcp tools` |
| DB schema | v9 — reported by `get_instance_info` |
| Tunnel profile | `can-research-<instance_key>` |
| Backend identity | `get_instance_info` — never assume a specific installation name |

Substitute on each machine: repository path, tunnel-client install path, health listener
port, CANsub host, `instance_key`, display name.

---

## MCP capabilities summary

**Can:** read sessions, references, assets, candidates; passive live CANsub; signal
research evidence; preview DBCs; `get_instance_info`.

**Cannot:** confirm candidates, write DBC files, transmit CAN.

Full tool list: [README.md](../README.md#mcp-tool-surface-41-total) · verify locally with `uv run canresearch mcp tools`.

---

## Related documents

| Document | Purpose |
|----------|---------|
| [INSTALLATION.md](INSTALLATION.md) | Clone, config, first-run |
| [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) | Skill zip install/update |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | MCP, tunnel, channel issues |
| [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md) | Verified Office deployment notes |
