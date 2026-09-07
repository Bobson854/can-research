# Setup troubleshooting

## CLI fails

Stay below the MCP layer. Check repo directory, `uv sync`, Python/uv install, and `uv run canresearch --help` first.

## Wrong backend in ChatGPT

Call `get_instance_info`. Compare `instance_key` and `display_name` with local config. Do not continue research on an unexpected backend.

## CANsub unreachable

Check configured host, USB/Ethernet connectivity, hostname resolution, TLS setting and `device info` before debugging captures.

## No CAN frames

Check:

1. correct physical channel
2. bitrate/PHY configuration on CANsub
3. bus termination/power
4. channel error state/counters
5. listen-only/ACK behaviour where relevant
6. another client owning the WebSocket

Do not label an empty capture as useful evidence.

## `channel_rx_in_use`

Another WebSocket client owns that CANsub channel. Close/stop the competing owner on the research channel. It does not mean the bus is silent.

## Local MCP works but ChatGPT tools are stale

Treat three states separately:

```text
local MCP registry
→ tunnel health/target
→ connector schema/chat binding
```

Record the local expected count/names from `uv run canresearch mcp tools`. Current baseline for this Skill package is 41 tools. After code changes, the local registry is authoritative.

Do not delete/recreate the connector until local MCP and tunnel are proven correct and the existing connector refresh path has failed.

## After reboot

Normally restart only MCP and tunnel client. Do not recreate tunnel/profile/connector/Skills.

## Reference bundle fails validation

Do not mutate source facts to make validation pass. Give the errors to `can-reference-builder`, repair the normalized representation, then validate again.

**SQLite INTEGER overflow** (`sqlite_integer` error): a numeric field such as signal `maximum` exceeds signed 64-bit range (e.g. `18446744073709551615` for a 64-bit NAME field). Remove the numeric field from the bundle and preserve the source value in `description` or provenance text — do not clip to a smaller number.

**Many PGN-only warnings:** `no exact CAN ID on message` is expected for ISO 11783/J1939 standard exports. The CLI summarizes repeated occurrences; do not invent CAN IDs to silence them.

## Reference search returns nothing

Confirm:

- source is registered
- bundle `source_key` matches exactly
- bundle was imported after validation
- `inspect_reference_source` reports imported knowledge counts
- query uses a known signal/message/register term

## DBC coverage looks wrong

Confirm correct DBC source and asset scope. Exact CAN ID matches are different from partial PGN/address variants; CAN Research does not silently rewrite IDs.
