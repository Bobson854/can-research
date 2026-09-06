# AI integration

How to connect CAN Research to generative AI frontends.

**Use each layer for what it does best:**

| Layer | Role |
|-------|------|
| **CAN Research core** | Deterministic CAN capabilities — facts, validation, import |
| **MCP** | Portable AI capability interface — bounded tools over the core |
| **Skills / workflows** | Frontend-specific guidance and orchestration (where supported) |
| **AI** | Interactive operator layer — adapts steps to your situation |

CAN Research does **not** require Cursor or any particular IDE. Cursor is documented below
as a **developer-oriented** MCP client only.

---

## Before connecting AI

1. Complete software setup — [INSTALLATION.md](INSTALLATION.md)
2. Start services:
   - **Windows:** `start-can-research.cmd` — starts MCP and the OpenAI tunnel (after one-time tunnel/connector setup in [MCP_SETUP.md](MCP_SETUP.md))
   - **Developer (MCP only):** `uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp`
3. Confirm health: `status.cmd` or `uv run python scripts/mcp_verify_http.py`

Default local endpoint:

```text
http://127.0.0.1:8765/mcp
```

Transport: **streamable-http** (ChatGPT tunnel / many HTTP MCP clients).

Alternative: **stdio** (`uv run canresearch mcp serve`) for desktop clients that spawn the server as a subprocess.

Verify tool count:

```powershell
uv run canresearch mcp tools
```

Baseline **41 tools** — treat documentation counts as checkpoints, not immutable forever.

---

## ChatGPT (tested primary path)

**MCP:** streamable HTTP via OpenAI Secure MCP tunnel + ChatGPT connector.

**Skills:** CAN Research **Skills** (`can-onboarding`, `can-reference-builder`, `can-signal-research`) are **ChatGPT Skills** — install from packaged `skill.zip` files. They are **not** directly portable to other frontends.

### Connect MCP

Full tunnel and connector setup: [MCP_SETUP.md](MCP_SETUP.md).

Summary:

1. **Daily / after reboot:** Run `start-can-research.cmd` — reuse the **existing** ChatGPT connector
2. **First-time only:** Configure OpenAI tunnel profile and ChatGPT MCP connector — [MCP_SETUP.md](MCP_SETUP.md) (`http://127.0.0.1:8765/mcp`)
3. Verify `get_instance_info` in a fresh chat

### Install Skills

Release ZIPs include pre-built packages under **`skills/dist/`** — no packaging required.

[SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) — upload `.skill.zip` files to ChatGPT Skills.

Recommended order:

1. **can-onboarding** — first
2. **can-reference-builder** — when you have manuals/PDFs to convert
3. **can-signal-research** — before proprietary research

### Start onboarding

1. Enable **can-onboarding** in ChatGPT
2. Attach the CAN Research MCP connector
3. Ask can-onboarding to continue setup from your current machine state

Human-readable parallel path: [USER_ONBOARDING.md](USER_ONBOARDING.md)

### Smoke test

With MCP connected in ChatGPT:

```text
get_instance_info
get_cansub_device_status
get_cansub_channel_status
observe_live_traffic
```

Local verification: `status.cmd`

---

## Claude Desktop / Claude ecosystem

**MCP (stdio):** supported transport — Claude Desktop can run MCP servers via stdio configuration.

**Skills:** CAN Research ChatGPT Skills are **not** Claude Skills. There is no verified equivalent “can-onboarding” package for Claude today. Use documentation + MCP tools, or adapt workflows manually.

**Typical stdio configuration (conceptual):**

- Command: `uv` (or full path to `uv.exe`)
- Args: `run`, `canresearch`, `mcp`, `serve`
- Working directory: your CAN Research install root

Exact Claude Desktop config file location and schema change between versions — refer to Anthropic’s current MCP documentation. **Status: generic pattern documented; not continuously verified in this repo.**

After connect, verify with `get_instance_info`.

---

## Cursor

**Role:** development environment with built-in MCP client support — **not** the assumed end-user interface.

**MCP (stdio):** developers often add CAN Research as a workspace MCP server:

```powershell
uv run canresearch mcp serve
```

Configure in Cursor MCP settings with command `uv`, arguments `run canresearch mcp serve`, cwd = install root.

**Skills:** Cursor uses its own rules/skills model. CAN Research **ChatGPT Skills do not install into Cursor**. Use repo docs and `skills/*/SKILL.md` as reference material when prompting.

**Status: developer-oriented; stdio MCP pattern used in development.**

---

## VS Code / GitHub Copilot

**MCP:** VS Code MCP support (including Copilot-related MCP integrations) evolves quickly. Where your VS Code build supports MCP over **stdio** or **HTTP**, point it at the same commands/endpoints as Claude Desktop or streamable HTTP above.

**Skills:** no verified CAN Research Skill pack for Copilot. Use documentation workflows.

**Status: generic MCP client — follow Microsoft/VS Code MCP docs for your version; not continuously verified here.**

---

## Generic MCP clients

Any client that supports:

- **Streamable HTTP** → `http://127.0.0.1:8765/mcp` while `start-can-research.cmd` is running
- **Stdio** → `uv run canresearch mcp serve` from install root

…can call the same **41-tool** registry. Tool names and schemas are stable across installations; instance identity comes from `get_instance_info`.

**Skills/workflows:** unless the client explicitly supports ChatGPT-compatible Skill packages, assume **no** bundled CAN Research orchestration — use MCP tools + project documentation.

---

## What Skills are (and are not)

| | ChatGPT | Other frontends |
|---|---------|-----------------|
| **MCP tools** | Yes (via connector) | Yes (if client supports MCP) |
| **CAN Research Skills** | Yes — upload `skill.zip` | **Not portable as-is** |
| **Guided onboarding** | **can-onboarding** Skill | [USER_ONBOARDING.md](USER_ONBOARDING.md) + docs |

Skills encode methodology, checkpoints, and handoffs. They complement MCP; they do not replace deterministic CLI validation/import.

---

## Related documents

| Document | Purpose |
|----------|---------|
| [INSTALLATION.md](INSTALLATION.md) | Software install (release ZIP vs developer) |
| [SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) | ChatGPT Skill package install/update |
| [MCP_SETUP.md](MCP_SETUP.md) | Tunnel, connector, reboot startup (ChatGPT) |
| [CANSUB_SETUP.md](CANSUB_SETUP.md) | Hardware connectivity |
| [USER_ONBOARDING.md](USER_ONBOARDING.md) | Human-readable onboarding sequence |
| [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) | Research architecture contract |
