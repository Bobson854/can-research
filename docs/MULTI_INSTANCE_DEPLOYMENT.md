# Multi-instance CAN Research deployment

Each machine is **self-contained** — no central coordination server required.

**Public guides:** [INSTALLATION.md](INSTALLATION.md) · [MCP_SETUP.md](MCP_SETUP.md) ·
[SKILL_INSTALLATION.md](SKILL_INSTALLATION.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

CAN Research is designed so **each laptop/backend is an independent installation**
with the same code and MCP tool schemas. Connectors, tunnels, and datastores are
**not shared** in this milestone.

See also:

- [MCP_SETUP.md](MCP_SETUP.md) — public MCP + tunnel setup (canonical)
- [MCP_CONNECTOR_INSTALL_GUIDE.md](MCP_CONNECTOR_INSTALL_GUIDE.md) — verified Office deployment record
- [MCP_CONNECTION.md](MCP_CONNECTION.md) — per-instance connector checklist

## Example: two independent machines

```text
Office machine                    Laptop / travel machine
  local repo clone                  local repo clone
  data/config.toml (office)         data/config.toml (travel)
  local CANsub.2                    local CANsub.2
  MCP http://127.0.0.1:8765/mcp     MCP http://127.0.0.1:8765/mcp
  tunnel profile can-research-office  tunnel profile can-research-travel
  ChatGPT connector (Office)          ChatGPT connector (Travel)
```

Same MCP port on each machine is fine — each host is a different computer.

## Model

```text
Same CAN Research code + identical 32-tool MCP API
        |
        +-- Workshop instance (instance_key = workshop)
        |     +-- local datastore (data/ or configured data_dir)
        |     +-- local CANsub.2 (USB on workshop network)
        |     +-- local MCP http://127.0.0.1:8765/mcp
        |     +-- tunnel profile can-research-workshop
        |     +-- ChatGPT app "CAN Research - Workshop"
        |
        +-- Travel instance (instance_key = travel)
              +-- local datastore
              +-- local CANsub.2 (USB on travel network)
              +-- local MCP http://127.0.0.1:8765/mcp
              +-- tunnel profile can-research-travel
              +-- ChatGPT app "CAN Research - Travel"
```

## Per machine vs portable (reboot and deployment)

**Each machine needs its own** (not shared):

| Item | Notes |
|------|--------|
| Local CAN Research config | `data/config.toml` — `instance_key`, `display_name`, `data_dir` |
| CANsub hostname | `[cansub].host` for the device on that network |
| OpenAI tunnel | One tunnel per workstation in OpenAI Platform |
| Tunnel-client profile | e.g. `can-research-office`, `can-research-workshop` |
| ChatGPT MCP connector | One connector per backend instance |
| Local MCP + tunnel processes | **Stopped on reboot** — restart both after power cycle |

**Portable / reusable across machines** (same repo, no Office identity baked in):

| Item | Notes |
|------|--------|
| CAN Research repository and code | Same git tree |
| MCP tool schema | 41 tools (baseline), identical names everywhere — verify with `mcp tools` |
| **CAN Research Skills** | can-onboarding, can-reference-builder, can-signal-research — install as needed |
| Operating methodology | [AI_GUIDED_SIGNAL_RESEARCH.md](AI_GUIDED_SIGNAL_RESEARCH.md) |

The Skill must **not** hard-code Office backend identity. After connect, call
`get_instance_info` to confirm which installation is active.

Normal startup after reboot (two processes only):
[MCP_SETUP.md — Normal startup after reboot](MCP_SETUP.md#normal-startup-after-reboot).

## Identity concepts (keep separate)

| Concept | Meaning | Stable across CANsub swaps? |
|---|---|---|
| **CAN Research instance** | Laptop/backend installation (`instance_key`, `display_name`) | Yes — configured in `data/config.toml` |
| **CANsub device** | Physical CANsub.2 currently attached | No — discovery/status finds current device |
| **Capture session** | One recording/analysis unit (UUID) | Yes — UUID within local DB |
| **Research asset** | Tractor/implement/controller research object | Yes — domain identity in local DB |

Do **not** bake a CANsub serial into instance identity or database schema. The same
CANsub hardware may move between laptops; each installation configures `[cansub].host`
for whichever device is attached locally.

## Configuration

Settings live in `data/config.toml` (TOML). Copy from `config.toml.example` or a
deployment example under `config/examples/`.

### Required instance fields

```toml
[instance]
instance_key = "workshop"
display_name = "CAN Research - Workshop"
```

- `instance_key` — stable, filename-safe (`[A-Za-z0-9][A-Za-z0-9_-]*`)
- `display_name` — human label for operators and MCP clients

**Development default** (no config file):

- `instance_key = local`
- `display_name = CAN Research (local)`

CLI:

```powershell
uv run canresearch config set-instance --key workshop --name "CAN Research - Workshop"
uv run canresearch config show
```

### Optional paths

```toml
[paths]
data_dir = "data"
```

Defaults preserve existing development layout:

| Purpose | Default path (relative to CWD unless absolute) |
|---|---|
| Config | `data/config.toml` |
| SQLite | `{data_dir}/references/canresearch.db` |
| JSONL captures | `{data_dir}/sessions/<session_id>/frames.jsonl` |
| Standard DBC output | `<asset_key>_standard.dbc` (CWD) |
| Research DBC output | `<asset_key>_research.dbc` (CWD) |

Each installation uses its **own** checkout and `data_dir`. Instance keys are **not**
prefixed onto session UUIDs or asset keys — separation comes from independent
filesystems.

Override data root if needed:

```powershell
uv run canresearch config set-data-dir D:\CANResearch\workshop-data
```

## MCP API (identical everywhere)

Every installation exposes the **same tool schemas** (baseline **41 tools**: 28 read-only /
7 live / 6 signal research). Verify on each machine with `uv run canresearch mcp tools`.
Instance-specific details appear in **configuration and tool results**, not in tool names or schemas.

Do **not** create per-instance tools such as `workshop_list_sessions`.

### Confirming which backend is active

When multiple ChatGPT connectors exist, call:

```text
get_instance_info()
```

Expected shape:

```json
{
  "instance_key": "workshop",
  "display_name": "CAN Research - Workshop",
  "version": "0.1.0",
  "schema_version": 8,
  "mcp_tool_count": 32,
  "capabilities": {
    "read_only_tools": 19,
    "live_tools": 7,
    "signal_research_tools": 6,
    "can_tx": false,
    "candidate_confirmation": false
  },
  "platform": "Windows",
  "cansub": {
    "host_configured": true,
    "connection_mode": "configured_host"
  }
}
```

No hostnames, home paths, tokens, or database contents are returned.

## Deployment examples

### Workshop

Copy `config/examples/workshop.toml.example` → `data/config.toml` and edit CANsub host.

| Deployment item | Suggested value |
|---|---|
| `instance_key` | `workshop` |
| `display_name` | `CAN Research - Workshop` |
| Tunnel profile | `can-research-workshop` |
| ChatGPT app | `CAN Research - Workshop` |
| Local MCP | `http://127.0.0.1:8765/mcp` |

### Travel

Copy `config/examples/travel.toml.example` → `data/config.toml`.

| Deployment item | Suggested value |
|---|---|
| `instance_key` | `travel` |
| `display_name` | `CAN Research - Travel` |
| Tunnel profile | `can-research-travel` |
| ChatGPT app | `CAN Research - Travel` |
| Local MCP | `http://127.0.0.1:8765/mcp` |

Tunnel profile and ChatGPT app names are **deployment configuration only** — they are
not encoded in application logic.

## Live capture state

Each running CAN Research process maintains **process-local** live capture state
(one active capture per channel). This is not shared across laptops or connectors.

## Port 8765 on every laptop

Using `http://127.0.0.1:8765/mcp` on workshop, travel, and other machines is fine.
Each host is a different machine — ports do not collide across installations.

## No central shared MCP endpoint

There is currently **no mechanism** for multiple laptops to connect through one
shared central CAN Research MCP backend or router. Each installation runs its own
MCP server, datastore, and (future) tunnel profile. Central routing may be
revisited later but is **not** current architecture and must not be implied by docs.

## What is explicitly out of scope

- Central routing or shared MCP backend
- Cross-laptop discovery or synchronization
- Cloud databases or remote CANsub access
- Instance-prefixed session/asset IDs in the database

Central routing may be considered later; independent multi-laptop deployment is the
current model.

## Verification checklist (per installation)

1. `uv run canresearch config show` — correct `instance_key` / `display_name`
2. `uv run canresearch mcp tools` — **32** tools
3. `uv run python scripts/mcp_verify_http.py` — initialize + verify tool count (baseline 41)
4. MCP `get_instance_info()` — matches configured identity
5. Record values in [MCP_CONNECTION.md](MCP_CONNECTION.md) for that instance

## Release expectation

```text
Expected MCP tools: 32
Read-only: 19 | Live: 7 | Signal research: 6
Schema: v8
```

No CAN TX tools. Candidate confirmation remains CLI-only.
