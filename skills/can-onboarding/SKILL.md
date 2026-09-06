---
name: can-onboarding
description: >-
  Guide a user through installing, configuring, validating, and troubleshooting CAN Research on a Windows machine, including CANsub.2, MCP/tunnel/ChatGPT connector, Skills, DBC knowledge, and reference-source onboarding. Use for fresh installs, second-laptop setup, post-reboot recovery, connector/tool visibility problems, or getting from clone to a verified research-ready system. Prefer verification checkpoints over assumptions and hand reference conversion to can-reference-builder and proprietary research to can-signal-research.
---

# CAN Research onboarding

Guide the user from their current state to a **verified research-ready installation**.

## Operating principles

- Windows is the primary supported onboarding path.
- Ask at most one or two high-value questions at a time.
- Determine whether the user is in PowerShell or CMD before giving shell-sensitive commands.
- Skip steps already proven complete.
- Verify each layer before moving upward.
- Use `uv run canresearch ...`; do not assume bare `canresearch` is installed on PATH.
- Keep private/licensed reference material local.
- Current CAN Research live workflow is passive RX only. Do not introduce CAN TX/injection.

Read [windows-setup.md](references/windows-setup.md) for installation/configuration, [cansub-and-mcp.md](references/cansub-and-mcp.md) for hardware/connector work, [reference-onboarding.md](references/reference-onboarding.md) for knowledge intake, and [troubleshooting.md](references/troubleshooting.md) when a checkpoint fails.

## Required onboarding state machine

```text
1. HOST + SHELL
2. REPO + UV
3. INSTANCE CONFIG
4. CANsub CONNECTIVITY
5. LIVE TRAFFIC
6. LOCAL MCP
7. TUNNEL / CHATGPT CONNECTOR
8. SKILLS
9. EXISTING KNOWLEDGE
10. REFERENCE + DBC VERIFICATION
11. ASSET
12. END-TO-END SMOKE TEST
13. HANDOFF TO can-signal-research
```

Do not force a user through every stage if they already have evidence that a stage is complete.

## First questions

When state is unknown, start with only what changes the instructions materially:

1. “Are you setting up from a fresh clone, or is CAN Research already installed?”
2. “Are you using PowerShell or Command Prompt?”

Then continue from the earliest unverified checkpoint.

## Checkpoint 1 — repository and CLI

Minimum proof:

```powershell
uv sync
uv run canresearch --help
uv run canresearch config show
```

Do not proceed to CANsub troubleshooting until the CLI/config layer works.

## Checkpoint 2 — instance identity

Configure a unique local instance and confirm resolved data directory. Machine-specific config stays local/gitignored.

When MCP is available, verify with `get_instance_info`; never assume the backend identity from chat history.

## Checkpoint 3 — CANsub.2

Verify in order:

```text
device reachable → channel exists → channel state healthy → bounded live RX sees frames
```

CLI smoke checks:

```powershell
uv run canresearch device info
uv run canresearch device channel-info 1
uv run canresearch device rx 1 --duration 5
```

MCP preflight:

```text
get_instance_info → get_cansub_device_status → get_cansub_channel_status → observe_live_traffic
```

No frames means stop and diagnose. Do not start an empty research capture.

## Checkpoint 4 — local MCP before tunnel

Start local MCP from repo root:

```powershell
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
```

In another terminal:

```powershell
uv run canresearch mcp tools
uv run python scripts/mcp_verify_http.py
```

Current package baseline is **41 tools** (28 read-only, 7 live/passive, 6 signal research). Treat this as a version checkpoint, not a timeless constant: if a newer repo intentionally exposes a different tested count, trust the local repo/tool registry and compare the ChatGPT connector against it.

## Checkpoint 5 — tunnel and ChatGPT connector

Troubleshoot the three independent states in order:

```text
local MCP → tunnel client → ChatGPT connector schema/chat binding
```

Do not recreate a connector just because a chat sees stale tools. First prove the local tool registry and tunnel target.

After connector attachment, call `get_instance_info`, then one small read-only tool.

## Checkpoint 6 — Skills

Target installed Skills for a complete workflow:

- `can-onboarding` — this setup workflow
- `can-reference-builder` — messy reference material → normalized bundle
- `can-signal-research` — known-first signal research

If a Skill has just been updated, verify/reinstall the packaged `skill.zip` rather than assuming an old deployed copy changed automatically.

## Checkpoint 7 — onboard existing knowledge

Ask:

> “Do you already have DBCs, J1939/ISOBUS references, OEM manuals, supplier docs, spreadsheets, CSV signal tables, protocol notes, or previous reverse-engineering work?”

Route each item; do not treat all source formats the same.

### Existing DBC

```text
register → inspect → coverage
```

### J1939/ISOBUS structured source

Use existing supported catalogue import where appropriate.

### OEM/supplier/general document

Verify **can-reference-builder** is installed. Onboarding verifies the path works; **do not**
own day-to-day conversion or ingest staging here — hand that Skill the original document,
registered `source_key`, and any context.

```text
inventory → register source (if needed) → can-reference-builder (convert + validate/import) → verify search/lookup
```

See [reference-onboarding.md](references/reference-onboarding.md).

## Completion test

Do not declare onboarding complete until applicable checks pass:

```text
✓ CLI works
✓ instance identity is correct
✓ CANsub reachable (if live work required)
✓ frames observed (if bus connected)
✓ local MCP verified
✓ ChatGPT connector sees current tool surface
✓ required Skills installed
✓ existing DBC/reference knowledge onboarded or consciously skipped
✓ reference lookup/search works when reference material was added
✓ asset exists or user is ready to create one
```

Then hand off:

> “CAN Research is ready. Use can-signal-research to establish the asset/system context and run known-first research.”

## Reboot recovery

Once one-time setup is complete, normally restart only:

1. CAN Research MCP server
2. tunnel client

Do not recreate tunnel control-plane objects, runtime keys, profiles, connector, or Skills after every reboot.

## References

- [windows-setup.md](references/windows-setup.md)
- [cansub-and-mcp.md](references/cansub-and-mcp.md)
- [reference-onboarding.md](references/reference-onboarding.md)
- [troubleshooting.md](references/troubleshooting.md)
