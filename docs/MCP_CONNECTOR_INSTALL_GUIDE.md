# MCP Connector Install and Recovery Guide

## Purpose

Use this when exposing a self-hosted MCP server to ChatGPT through an OpenAI
tunnel-backed app. It is deliberately project-agnostic; replace the names and
URLs in angle brackets.

This guide is based on the BLE Research setup. The important lesson is that
there are **three independent states** that must all agree:

1. The local MCP server exposes the tools.
2. The tunnel is healthy and points at that server.
3. The ChatGPT app has refreshed its published tool schema and is enabled in
   the current chat/workspace.

Solving only one of those states does not make the tools usable.

## Before creating the connector

- Make the MCP server reachable **from the machine running the tunnel**.
- Give the server a stable local endpoint, normally `http://127.0.0.1:<port>/mcp`.
- Keep the MCP service read-only until the connection has been proven.
- Decide which tools should be exposed. Tool names and descriptions are the
  user-facing contract; avoid experimental or duplicate names.
- Do not put API keys, database credentials, or Omada/Home Assistant tokens in
  tool results or tool descriptions.

For the BLE Research service the known-good local endpoint was:

```text
http://127.0.0.1:8000/mcp
```

## 1. Prove the local server first

Do this on the host that runs the service and tunnel.

```bash
curl -i http://127.0.0.1:<port>/mcp
```

An MCP endpoint may reject a plain `GET`; that alone is not a failure. What
matters is that it is listening and that the tunnel/client can initialise an
MCP session against it. Also confirm the application service is healthy:

```bash
docker compose ps
docker compose logs --tail=100 <service-name>
```

If you have an application-level tool listing or tests, run them now. Record the
expected count and exact names. For BLE Research, the final expected count was
**21**: 12 BLE tools, 5 Omada tools, and 4 passive Wi-Fi tools.

Do not create or reinstall the ChatGPT app yet if the local service cannot see
the expected tool set.

## 2. Start the OpenAI tunnel

Use the existing tunnel profile, with the local MCP endpoint as its target.
For the BLE project this was managed by `/opt/openai-tunnel-client`, profile
`ble-research`, targeting `http://127.0.0.1:8000/mcp`.

The exact client command may vary by client version, but verify these facts:

- The client process remains running after startup.
- Its readiness/status output says it is connected.
- It reports the expected endpoint and does not show repeated reconnect or
  authentication errors.
- The app has a stable tunnel URL; do not repeatedly create replacement apps
  while diagnosing a stale tool list.

Capture a short status/log extract if anything is wrong:

```bash
ps aux | rg 'openai|tunnel'
<tunnel-client-command> status
```

## 3. Create or configure the ChatGPT app once

In ChatGPT Work, create a connector/app using the tunnel URL supplied by the
client. For an internal, read-only research service, use the simplest allowed
authentication mode that matches the tunnel setup (the BLE Research connector
was configured as **no auth** at the app layer).

Then:

1. Save the app.
2. Confirm its tool list/count in the app configuration.
3. Enable or publish it for the intended workspace/personal use.
4. Start a fresh chat and explicitly enable/select the app for that chat.

Treat the app configuration as a schema cache. A healthy tunnel does **not**
guarantee the ChatGPT UI has the current tool list.

## 4. Verify in the chat that will use it

Ask a small, unambiguous question first:

> How many `<project name>` tools can you see? List their names.

Then run one safe, small query, for example a 60-minute summary with a small
limit. Do not begin with a large raw-observation query.

Success criteria:

- The tool count and names match the local server’s expected list.
- A live tool call returns current data.
- A new chat can see the same tool set after the app is selected.

For BLE Research, `ble_proxy_summary(minutes=60, limit=20)` was a good smoke
test because it is compact, read-only, and clearly time-sensitive.

## When tools are missing or stale

Work through this order. Do not jump straight to reinstalling the app.

| Check | What to do | Interpretation |
|---|---|---|
| Local tool list | Confirm the service has the new tool registered and its tests/import succeed. | If missing here, this is an application deployment issue. |
| Tunnel health | Check profile/process/readiness and its target URL. | If unhealthy, fix the tunnel/service path first. |
| App tool count | Open the existing app configuration and compare its tool count to the local expected count. | A mismatch means stale schema, not a chat checkbox problem. |
| Refresh | Restart/refresh the existing tunnel profile after the server change, then allow the app schema to update. | This is the normal recovery after adding tools. |
| New chat smoke test | Start a genuinely new chat, enable the app, and ask for the count/names. | Confirms the conversational tool binding. |

Only delete and recreate the app after the first four checks have failed and you
have verified the tunnel is serving the correct schema. Recreating it too early
can create multiple similar connectors and makes the diagnosis harder.

## Common pitfalls from the BLE setup

### "The app is connected, but the new tools are not visible"

Most likely cause: ChatGPT has retained the earlier app schema. Confirm the
local count, refresh/restart the **existing** tunnel profile, then re-check the
app count and test in a fresh chat. Do not assume enabling extra checkboxes
refreshes the schema.

### "A different chat can see a different tool count"

The connector may be enabled in one workspace/chat but not another, or the
conversation was started before the schema refresh. Use a fresh chat for the
authoritative smoke test.

### "The tunnel exists, but calls fail"

Check the local target from the tunnel host, Docker service health, and tunnel
logs before editing any app settings. The tunnel URL is only a route; it cannot
repair an unhealthy service behind it.

### "We have added tools but do not know whether deployment succeeded"

Keep an explicit expected-count check in the release notes. For example:

```text
Expected after deployment: 21 tools
BLE: 12 | Omada: 5 | Wi-Fi: 4
```

That turns a vague UI problem into a binary comparison at each layer.

## Minimal release checklist

- [ ] New MCP tools are registered in the server and covered by tests.
- [ ] The application/service has been deployed and is healthy.
- [ ] Local expected count and names have been recorded.
- [ ] Tunnel profile is healthy and targets the correct local `/mcp` URL.
- [ ] Existing ChatGPT app shows the expected tool count.
- [ ] App is enabled/published for the intended scope.
- [ ] Fresh-chat tool-name check passes.
- [ ] One small read-only live query passes.
- [ ] No duplicate old connectors remain enabled.

## Recommended operational pattern

For each new project, make a small `MCP_CONNECTION.md` beside the service with:

- service name and local MCP URL;
- tunnel profile name and how it is started/status-checked;
- expected tool count, grouped by function;
- one compact smoke-test tool and arguments;
- authentication model; and
- the date/version of the last successful fresh-chat verification.

That file makes future changes routine, and it prevents a tool-cache issue from
being mistaken for a code or credential failure.
