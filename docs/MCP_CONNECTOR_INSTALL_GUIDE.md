# MCP Connector Install and Recovery Guide

## Purpose

Use this guide to expose a local CAN Research MCP server to ChatGPT through the
OpenAI Secure MCP tunnel client.

This sequence was verified end-to-end on the **Office Windows workstation on
2026-09-05** using:

- CAN Research MCP: `http://127.0.0.1:8765/mcp`
- OpenAI `tunnel-client` **v0.0.14**
- Tunnel name/profile: `can-research-office`
- ChatGPT plugin/connector: `can-research-office`
- Expected CAN Research tool count: **32**

The most important operational rule is that three independent states must all
agree:

1. **Local MCP server** is healthy and exposes the expected tools.
2. **OpenAI tunnel client** is healthy and points at that local MCP server.
3. **ChatGPT plugin/connector** has discovered the current schema and is enabled.

Do not troubleshoot these out of order.

---

## Known-good Office deployment

| Item | Verified value |
|---|---|
| Instance key | `office` |
| Display name | `CAN Research - Office` |
| CAN Research MCP URL | `http://127.0.0.1:8765/mcp` |
| MCP transport | `streamable-http` |
| MCP tool count | **32** |
| Read-only tools | 19 |
| Passive live CANsub tools | 7 |
| Signal research tools | 6 |
| Tunnel name | `can-research-office` |
| Tunnel client version | `0.0.14` |
| Tunnel client profile | `can-research-office` |
| Tunnel health/admin listener | `127.0.0.1:8081` |
| Verification date | `2026-09-05` |

The Office machine already had SABnzbd listening on `127.0.0.1:8080`, so the
OpenAI tunnel health listener was moved to `8081`.

**Reboot recovery verified 2026-09-06:** After a Windows power cycle, only the local
MCP server and `tunnel-client.exe` needed restarting. The ChatGPT connector,
installed `can-signal-research` Skill, tunnel profile, and persisted runtime API
key remained intact.

---

## Normal startup after a reboot

Once a workstation has been configured **once**, do **not** repeat the installation
sequence below. Start only these two processes, then use the existing ChatGPT connector.

### Terminal 1 — CAN Research MCP

From the repository root (**Office example path** — substitute on other machines):

```powershell
cd C:\dev\Can_Research\Can-Research_V1\can-research
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Leave it running.

Optional local check (second terminal):

```powershell
uv run python scripts/mcp_verify_http.py
```

### Terminal 2 — OpenAI tunnel

**Prefer the full executable path** — it works regardless of the current drive or shell
working directory (**Office example**):

```powershell
K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

Leave it running.

**Command Prompt** — if changing drive first, use `cd /d` (see [CMD vs PowerShell](#cmd-vs-powershell-drive-switching) below):

```cmd
cd /d K:\Downloads\tunnel-client-v0.0.14-windows-amd64
tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

**PowerShell** — `cd` to another drive works without `/d`:

```powershell
cd K:\Downloads\tunnel-client-v0.0.14-windows-amd64
.\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

Then use the existing ChatGPT connector. No connector recreation or Skill reinstall
is required for normal startup.

### Do NOT recreate (unless configuration was lost or deliberately changed)

- OpenAI tunnel (control plane)
- Runtime API key (`CONTROL_PLANE_API_KEY`)
- Tunnel-client profile (`can-research-office` on Office)
- ChatGPT MCP connector / plugin
- Installed **can-signal-research** Skill

Foreground terminals are the **currently verified** method. Do not add Windows
Services, Scheduled Tasks, or other auto-start mechanisms until multi-machine
installation is proven.

### Portable vs Office-specific (quick reference)

| Item | Office example | Portable convention |
|------|----------------|---------------------|
| Repository | `C:\dev\Can_Research\Can-Research_V1\can-research` | Your clone path |
| MCP URL | `http://127.0.0.1:8765/mcp` | Same on every machine (localhost) |
| Tunnel executable | `K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe` | Your install path |
| Tunnel profile | `can-research-office` | `can-research-<instance_key>` |
| Health listener | `127.0.0.1:8081` | Choose a free port if `8080` is taken |

---

# One-time installation sequence

## 1. Configure and prove CAN Research first

From the CAN Research repository root:

```powershell
uv run canresearch config show
```

For the Office installation the expected identity is:

```text
instance_key = office
display_name = CAN Research - Office
```

Start the HTTP MCP server:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

Leave this terminal running.

In another terminal, verify the MCP protocol and tool inventory:

```powershell
uv run python scripts/mcp_verify_http.py
```

Expected result:

```text
url: http://127.0.0.1:8765/mcp
tool_count: 32
read_only: 19
live: 7
signal_research: 6
match: True
```

A plain HTTP request to `/mcp` may return `400` or `406`. That can still indicate
that the endpoint is alive; the protocol-aware verification script is the
authoritative check.

Do not continue to tunnel setup until the local tool count is correct.

---

## 2. Download the correct OpenAI tunnel client

Open the OpenAI Platform Tunnels page:

```text
https://platform.openai.com/settings/organization/tunnels
```

Use **Download tunnel-client**.

For Windows x64, download the normal Windows AMD64 client archive, for example:

```text
tunnel-client-v0.0.14-windows-amd64.zip
```

Do **not** use the archive named like:

```text
tunnel-client-runtime-cloudflared-v0.0.14-windows-amd64.zip
```

That runtime bundle contains `tunnel-client-runtime-cloudflared.exe` and
`cloudflared.exe`, but not the main `tunnel-client.exe` CLI used by this guide.

After extraction, confirm:

```powershell
.\tunnel-client.exe --version
.\tunnel-client.exe help quickstart
```

Known-good version output began with:

```text
0.0.14
```

---

## 3. Create the OpenAI tunnel

On the Platform **Tunnels** page, click **Create tunnel**.

Use a per-machine name. Office example:

```text
can-research-office
```

After creation, copy the generated tunnel ID. It has the form:

```text
tunnel_...
```

Do not create duplicate tunnels while troubleshooting. Reuse the existing tunnel
for that workstation.

---

## 4. Create the runtime API key

Open:

```text
https://platform.openai.com/settings/organization/api-keys
```

Create a new secret key.

Recommended name:

```text
can-research-office
```

Important UI detail: the **Project** field must be selected before the **Create
secret key** button becomes active. On the Office setup this was:

```text
Default project
```

Use restricted permissions sufficient for tunnel runtime use. The tunnel client
quickstart describes the runtime principal as needing Tunnel **Read + Use**.

Do not use an OpenAI admin key for the long-lived tunnel daemon.

Copy the runtime key when it is shown. Never commit it to Git.

---

## 5. Persist the runtime API key on Windows

The tunnel ID is stored in the tunnel profile, so it does not need to be entered
on every run.

Persist the runtime API key for the Windows user:

```powershell
setx CONTROL_PLANE_API_KEY "sk-REPLACE_WITH_THE_REAL_RUNTIME_KEY"
```

Then **close PowerShell and open a new PowerShell window**. `setx` does not alter
the already-running shell.

Verify only that the variable is present:

```powershell
$env:CONTROL_PLANE_API_KEY
```

Do not paste the key into support chats or documentation.

If a placeholder was accidentally saved literally, simply run `setx` again with
the correct real key and open another new PowerShell window.

---

## 6. Create the local tunnel-client profile

Open PowerShell in the folder containing `tunnel-client.exe`, or use its full
path.

For Office:

```powershell
$env:CONTROL_PLANE_TUNNEL_ID="tunnel_REPLACE_WITH_REAL_ID"

.\tunnel-client.exe init `
  --sample sample_mcp_remote_no_auth `
  --profile can-research-office `
  --tunnel-id $env:CONTROL_PLANE_TUNNEL_ID `
  --mcp-server-url http://127.0.0.1:8765/mcp
```

The profile is stored under the Windows user config directory, for example:

```text
C:\Users\Office\.config\tunnel-client\can-research-office.yaml
```

The tunnel ID is persisted in this profile.

---

## 7. Run `doctor` before starting the tunnel

Run:

```powershell
.\tunnel-client.exe doctor --profile can-research-office --explain
```

On the Office workstation, this initially failed because port `8080` was already
in use:

```text
CHECK health_listener FAIL listen tcp 127.0.0.1:8080
```

Find the owner of a conflicting port with:

```powershell
netstat -ano | findstr :8080
tasklist /FI "PID eq <PID>"
```

On the verified Office setup, the process was `SABnzbd.exe`, so it was left
alone and the tunnel health listener was moved to `8081`.

Known-good doctor command:

```powershell
.\tunnel-client.exe doctor --profile can-research-office --explain --health.listen-addr 127.0.0.1:8081
```

Expected final line:

```text
RESULT ok
```

Expected MCP checks include:

```text
CHECK mcp_target           PASS http://127.0.0.1:8765/mcp
CHECK mcp_server_reachable PASS
CHECK health_listener      PASS will bind http://127.0.0.1:8081
CHECK ui                   PASS http://127.0.0.1:8081/ui
```

`codex_plugin SKIP` is optional and is not a failure for the ChatGPT connector.

---

## 8. Start the tunnel

With the CAN Research MCP server still running, start the tunnel:

```powershell
.\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

Leave this terminal running.

The tunnel client must remain running for ChatGPT connector discovery and every
subsequent MCP call.

At this point the active process chain is:

```text
ChatGPT
  -> OpenAI tunnel
  -> tunnel-client.exe
  -> http://127.0.0.1:8765/mcp
  -> CAN Research MCP server
```

---

## 9. Create/discover the ChatGPT plugin/connector

Do this only while both of these are running:

1. CAN Research MCP server on `127.0.0.1:8765`
2. `tunnel-client.exe run ...`

In ChatGPT, use the workspace/plugin management UI to create or discover the
connector backed by the existing OpenAI tunnel.

Select:

```text
can-research-office
```

The plugin page should populate an **Actions** section from the MCP tool schema.
Seeing tool definitions such as `analyze_can_id_activity` confirms schema
discovery is occurring.

Do not edit the MCP service, tunnel, API key, or tunnel profile while the ChatGPT
UI is already successfully showing the tool actions.

---

## 10. End-to-end verification in ChatGPT

Use **Try in chat** or start a fresh chat with the connector enabled.

First ask:

> How many CAN Research tools can you see? List their names.

Expected:

```text
32 tools
19 read-only/offline
7 live CANsub
6 proprietary signal-research
```

Then verify backend identity:

> Call `get_instance_info`.

Expected Office result:

```text
instance_key: office
display_name: CAN Research - Office
```

Then verify stored-session access:

> Call `list_sessions` with `limit=5`.

If a CANsub.2 is available on the network, verify the passive hardware path:

> Call `get_cansub_device_status`.

The Office connector passed the 32-tool discovery test on **2026-09-05**. After Windows
reboot on **2026-09-06**, ChatGPT reconnected immediately once both local processes were
restarted — see [Normal startup after a reboot](#normal-startup-after-a-reboot).

---

# Troubleshooting order

Always work from the inside out.

| Layer | Check | Meaning |
|---|---|---|
| 1. CAN Research | `uv run python scripts/mcp_verify_http.py` | Must report 32 tools and `match: True` |
| 2. Tunnel profile | `tunnel-client doctor --profile ... --explain` | Must end with `RESULT ok` |
| 3. Tunnel runtime | `tunnel-client run --profile ...` | Must stay running without repeated auth/reconnect errors |
| 4. ChatGPT plugin | Actions/tool list visible | Confirms schema discovery |
| 5. Fresh chat | Ask for tool count | Must report 32 |
| 6. Identity | `get_instance_info` | Must match the machine instance |
| 7. CANsub | `get_cansub_device_status` | Optional passive hardware verification |

Do not delete and recreate the ChatGPT plugin first. A stale or missing tool list
can originate at any earlier layer.

---

# Common failures seen during the Office installation

## CMD vs PowerShell drive switching

**Observed failure in Command Prompt:**

```text
C:\dev\Can_Research\...>cd K:\Downloads\tunnel-client-v0.0.14-windows-amd64

C:\dev\Can_Research\...>.\tunnel-client.exe run ...
'.\tunnel-client.exe' is not recognized as an internal or external command
```

**Cause:** `cmd.exe` does **not** switch the active drive when you run `cd K:\path`.
The prompt stays on `C:` while the directory context may not be what you expect.

**Fix (Command Prompt)** — any of:

```cmd
cd /d K:\Downloads\tunnel-client-v0.0.14-windows-amd64
tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

```cmd
K:
cd \Downloads\tunnel-client-v0.0.14-windows-amd64
tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

Or invoke the **full executable path** (works from any drive):

```cmd
K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081
```

**PowerShell** does not have this same drive-switch limitation for `cd K:\path`.
This guide uses PowerShell in many examples; operators opening **Command Prompt**
should use `/d`, an explicit drive letter, or the full path.

## `tunnel-client.exe` is not found

If PowerShell shows:

```text
The term '.\tunnel-client.exe' is not recognized
```

then either:

- the wrong archive was downloaded; or
- the shell is not in the extracted tunnel-client folder **and** no full path was used.

Change directory first (PowerShell):

```powershell
cd K:\Downloads\tunnel-client-v0.0.14-windows-amd64
```

Or use the executable's full path (recommended after reboot — see [Normal startup](#normal-startup-after-a-reboot)).

## Wrong download: runtime-cloudflared bundle

The runtime-cloudflared ZIP is not the main Windows tunnel-client CLI package.
Download the normal `tunnel-client-v...-windows-amd64.zip` package.

## API key Create button stays disabled

Select a **Project** in the secret-key dialog. The Office setup used `Default
project`.

## `doctor` fails on port 8080

Find the owner with `netstat` and `tasklist`. Do not kill unrelated software
without identifying it first. Choose another tunnel health port instead.

## MCP target returns HTTP 406

This was accepted by `tunnel-client doctor` as reachable for the streamable HTTP
MCP endpoint. Judge health from `doctor` and the MCP verification script rather
than a plain browser/GET request.

## ChatGPT shows tool actions

That is a positive result. Once the Actions list is populated, stop changing the
lower layers and perform the fresh-chat tool-count test.

---

# Per-instance naming convention

Each machine is a self-contained installation. There is no central CAN Research
backend.

Recommended names:

```text
instance_key:             <machine-key>
display_name:             CAN Research - <Machine Name>
OpenAI tunnel:            can-research-<machine-key>
tunnel-client profile:    can-research-<machine-key>
ChatGPT plugin/connector: CAN Research - <Machine Name>
MCP URL:                  http://127.0.0.1:8765/mcp
```

Different computers may all reuse port `8765` because each machine has its own
localhost.

---

# Security and safety

- Never commit `CONTROL_PLANE_API_KEY` or the generated secret value.
- Never paste a live API key into documentation or support messages.
- Use a runtime key for the long-lived tunnel client, not an admin key.
- Keep CAN Research MCP passive: there are no CAN TX tools.
- Candidate confirmation remains CLI-only and human-controlled.
- Keep SAE/ISO licensed reference material local and ignored by Git.

---

# Verification checklist

- [x] Office instance configured as `office`
- [x] CANsub.2 reachable from CAN Research
- [x] Local HTTP MCP verified at `127.0.0.1:8765/mcp`
- [x] 32 tools verified locally
- [x] Correct Windows tunnel-client v0.0.14 installed
- [x] OpenAI tunnel `can-research-office` created
- [x] Runtime API key created and persisted for the Windows user
- [x] `can-research-office` tunnel-client profile created
- [x] Port 8080 conflict identified as SABnzbd and left untouched
- [x] Tunnel health moved to `127.0.0.1:8081`
- [x] `tunnel-client doctor` returned `RESULT ok`
- [x] Tunnel started successfully
- [x] ChatGPT plugin discovered the MCP Actions schema
- [x] Fresh-chat tool count returned **32**
- [x] `get_instance_info` rechecked in ChatGPT after Windows reboot (**2026-09-06**)
- [ ] `get_cansub_device_status` rechecked in ChatGPT with hardware available
