# MCP setup

Public guide for exposing a local CAN Research MCP server to ChatGPT or other MCP clients.

**Office verified deployment record:** [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md)

**Per-instance verification checklist:** [MCP_CONNECTION.md](MCP_CONNECTION.md).

## Three independent states

Before tools work in ChatGPT, all three must agree:

1. **Local MCP server** — healthy, current tool registry, correct `get_instance_info`
2. **OpenAI tunnel client** — running and targeting the local MCP endpoint
3. **ChatGPT connector** — schema discovered and enabled

Troubleshoot in that order. Do not delete/recreate the ChatGPT connector just because a local process stopped.

---

## Windows: normal startup after reboot

After one-time setup, the normal operator workflow is intentionally one command:

```cmd
start-can-research.cmd
```

That script:

1. Reads the per-instance tunnel settings from `data/config.toml`
2. Starts the CAN Research MCP service if it is not already healthy
3. Verifies the MCP registry with `scripts/mcp_verify_http.py`
4. Runs `tunnel-client doctor` before starting a stopped tunnel
5. Starts the OpenAI tunnel if it is not already running
6. Waits for the tunnel health listener
7. Tells the operator to use the **existing** ChatGPT connector

It opens separate foreground windows for the MCP service and OpenAI tunnel. Closing those windows stops the corresponding process.

Check health at any time with:

```cmd
status.cmd
```

`status.cmd` checks the CLI/config, local MCP endpoint/tool registry, OpenAI tunnel client/health listener, and CANsub.2 reachability.

### Do not recreate after reboot

Do not recreate these unless configuration was deliberately removed or replaced:

- OpenAI control-plane tunnel
- runtime API key
- tunnel-client profile
- ChatGPT MCP connector/plugin
- installed CAN Research Skills

A reboot normally requires only `start-can-research.cmd`.

---

## Permanent Windows tunnel-client location

The tunnel client must not be run long-term from a Downloads folder.

Default permanent per-user location:

```text
%LOCALAPPDATA%\CAN Research\tunnel-client\tunnel-client.exe
```

`setup.cmd` runs `scripts/tunnel_windows.py install`. If the permanent copy is missing, the helper searches normal Windows Downloads locations (including other drive letters such as `K:\Downloads`) for an extracted `tunnel-client.exe` and copies the newest matching executable into the permanent location.

You can override the source for migration/setup:

```cmd
set CANRESEARCH_TUNNEL_CLIENT_SOURCE=K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe
setup.cmd
```

The source archive/folder can then be removed from Downloads after the permanent copy is verified.

---

## Per-instance tunnel configuration

Tunnel runtime settings belong in the machine-local, gitignored `data/config.toml`:

```toml
[instance]
instance_key = "office"
display_name = "CAN Research - Office"

[tunnel]
profile = "can-research-office"
health_host = "127.0.0.1"
health_port = 8081
install_dir = "%LOCALAPPDATA%\\CAN Research\\tunnel-client"
```

If `[tunnel]` is absent, the Windows helper derives defaults from `instance.instance_key`:

- profile: `can-research-<instance_key>`
- health listener: `127.0.0.1:8081`
- install directory: `%LOCALAPPDATA%\CAN Research\tunnel-client`

This keeps older installations working while allowing workshop/travel/office machines to preserve separate tunnel profiles.

---

## One-time Windows setup

### 1. Install CAN Research

From the repository/release directory:

```cmd
setup.cmd
```

The setup script now also prepares the permanent tunnel-client location. If `tunnel-client.exe` cannot be found, setup stops with explicit instructions rather than leaving ChatGPT connectivity half-configured.

### 2. Configure CAN Research identity and CANsub

Edit `data/config.toml` as required, then verify:

```cmd
uv run canresearch config show
```

### 3. Create the OpenAI tunnel and runtime key

Create one control-plane tunnel per CAN Research machine using the OpenAI Platform tunnel UI. Use the profile convention:

```text
can-research-<instance_key>
```

Persist the runtime API key for the Windows user:

```cmd
setx CONTROL_PLANE_API_KEY "sk-REPLACE_WITH_REAL_RUNTIME_KEY"
```

Close the terminal and open a new one after `setx`.

Never commit the API key, tunnel ID, or profile secrets.

### 4. Create the local tunnel profile once

With the local MCP endpoint running at `http://127.0.0.1:8765/mcp`, initialize the profile using the permanent executable. Example:

```powershell
$env:CONTROL_PLANE_TUNNEL_ID="tunnel_REPLACE_WITH_REAL_ID"
& "$env:LOCALAPPDATA\CAN Research\tunnel-client\tunnel-client.exe" init `
  --sample sample_mcp_remote_no_auth `
  --profile can-research-office `
  --tunnel-id $env:CONTROL_PLANE_TUNNEL_ID `
  --mcp-server-url http://127.0.0.1:8765/mcp
```

Profiles are stored by the tunnel client under the Windows user configuration directory, for example:

```text
C:\Users\Office\.config\tunnel-client\can-research-office.yaml
```

### 5. Create the ChatGPT connector once

While both the local MCP server and tunnel client are running, create the ChatGPT connector backed by that tunnel. After successful schema discovery, reuse that connector on subsequent boots.

Verify in a fresh chat with:

```text
get_instance_info
```

---

## Local verification

CAN Research MCP default endpoint:

```text
http://127.0.0.1:8765/mcp
```

Verify current registry:

```cmd
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

Current project baseline at the time of this document update: **41 tools** (28 read-only / 7 live / 6 signal research). Treat counts as checkpoints, not immutable constants.

A plain browser/GET request to `/mcp` may return `400` or `406`; use the protocol-aware verification script instead.

---

## Troubleshooting order

Always work inside-out:

| Layer | Check | Recovery |
|---|---|---|
| CAN Research | `uv run python scripts/mcp_verify_http.py` | `start-can-research.cmd` |
| Tunnel install | `uv run python scripts/tunnel_windows.py show` | `setup.cmd` |
| Tunnel runtime | `uv run python scripts/tunnel_windows.py status` | `start-can-research.cmd` |
| Tunnel profile/auth | `tunnel-client doctor --profile ... --explain` | fix profile/API key; do not recreate connector |
| ChatGPT connector | actions/schema visible | refresh/use existing connector after lower layers pass |
| Backend identity | `get_instance_info` | verify the selected connector/instance |

If `CONTROL_PLANE_API_KEY` was set with `setx` but startup reports it missing, close the current Command Prompt/PowerShell window and open a new one.

If `8081` is occupied, choose another free health port in `data/config.toml` and use the same value for that instance thereafter.

---

## Non-Windows / developer startup

The underlying MCP service remains available directly:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Stdio clients can use:

```powershell
uv run canresearch mcp serve
```

Same tool registry, different transport.

---

## MCP capability boundary

Current MCP tools can read sessions, references, assets and candidates; perform passive live CANsub observation; run signal-research evidence tools; and preview DBCs.

Candidate confirmation/rejection and DBC writes remain CLI-only until that approval boundary is intentionally redesigned.

---

## Related documents

| Document | Purpose |
|---|---|
| [INSTALLATION.md](INSTALLATION.md) | CAN Research software installation |
| [AI_INTEGRATION.md](AI_INTEGRATION.md) | Supported AI frontends |
| [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md) | Historical Office deployment record |
| [MCP_CONNECTION.md](MCP_CONNECTION.md) | Per-instance connection verification |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Broader MCP/CANsub troubleshooting |
| [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) | ChatGPT Skill packages |
