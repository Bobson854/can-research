# CAN Research Reference Bundle V1

## Purpose

Formal handoff contract between a generative converter and CAN Research deterministic validation/import.

```text
original source → generative interpretation → reference bundle JSON → validate → import → MCP lookup/search
```

CAN Research consumes normalized knowledge; it does not need to parse PDFs or spreadsheets itself.

## Top-level

Required:

- `schema_version`: `1`
- `source_key`: registered source key

Optional:

- `generated_by`
- `generated_at`
- `notes`
- `messages`
- `message_families`
- `registers`
- `fault_codes`
- `protocol_notes`
- `enums`

## Exact message

Recommended fields where known:

```json
{
  "key": "dcm_status_sa8a",
  "name": "DCM Status",
  "protocol": "j1939",
  "can_id": "0x18FF748A",
  "is_extended": true,
  "pgn": 65396,
  "source_address": 138,
  "destination_address": null,
  "dlc": 8,
  "period_ms": 100,
  "priority": 6,
  "description": "...",
  "source_location": {"page": 26, "section": "Status Data"},
  "signals": []
}
```

Exact messages require `key`. `can_id` may be omitted if the source only gives partial/J1939 information, but this will not support exact-ID lookup.

## Signal

```json
{
  "key": "motor_speed",
  "name": "MotorSpeed",
  "start_bit": 0,
  "bit_length": 16,
  "byte_order": 1,
  "signedness": "signed",
  "factor": 1,
  "offset": 0,
  "unit": "rpm",
  "minimum": -32768,
  "maximum": 32767,
  "description": "...",
  "enum_key": null,
  "source_location": {"page": 26},
  "confidence": "high"
}
```

Unknown optional fields should be omitted rather than guessed.

## Message family

Use for IDs with a variable component:

```json
{
  "key": "status_reply",
  "name": "Status Reply",
  "pattern": "0x18700055",
  "mask": "0xFFFF00FF",
  "variable_field": "node_id",
  "variable_role": "source",
  "description": "Status family 0x1870??55",
  "source_location": {"page": 12, "section": "CAN Protocol"}
}
```

Deterministic match rule:

```text
(can_id & (mask & 0x1FFFFFFF)) == (pattern & (mask & 0x1FFFFFFF))
```

Do not expand a family into exact IDs without source evidence.

## Register

```json
{
  "key": "max_speed",
  "address": "0x2001",
  "name": "MaxSpeed",
  "width": 16,
  "signedness": "unsigned",
  "factor": 1,
  "offset": 0,
  "unit": "rpm",
  "access": "read_write",
  "minimum": 0,
  "maximum": 6000,
  "default": 3000,
  "description": "...",
  "source_location": {"page": 18, "section": "Register Table"}
}
```

## Fault code

```json
{
  "key": "overtemperature",
  "value": "0x01",
  "name": "OverTemperature",
  "description": "...",
  "source_location": {"page": 30, "section": "Fault Codes"}
}
```

## Protocol note

Use for useful facts that do not fit a signal/register:

```json
{
  "key": "nominal_bitrate",
  "category": "bitrate",
  "name": "Nominal bitrate",
  "value": "500000",
  "unit": "bps",
  "description": "...",
  "source_location": {"page": 10}
}
```

Examples include bitrate, update period, timeout, heartbeat behaviour, checksum algorithm, command/feedback relationship, address assignment and operational constraints.

## Enums

Top-level object keyed by enum key:

```json
{
  "dcm_mode": [
    {"value": 0, "name": "Init"},
    {"value": 1, "name": "Motor_Enable"}
  ]
}
```

Signals/registers reference with `enum_key`.

## Provenance

`source_location` may be an object with `page`, `section`, `table`, or a string shorthand. Use only what the source supports.

## Validation behaviour

Errors block import. Typical errors:

- wrong schema version
- unregistered source key
- invalid CAN ID/mask
- duplicate exact CAN ID
- duplicate object/signal key
- impossible bit range
- overlapping signal ranges
- unknown enum reference

Warnings do not block import. Typical warnings:

- missing exact CAN ID
- signal name missing
- factor/offset unknown
- unit unknown
- incomplete message-family variable metadata
- register address missing

## Important bit-index note

The core overlap validator treats `start_bit` as a normalized linear bit index. Do not copy DBC Motorola sawtooth start-bit numbering blindly. If conversion from source/DBC notation is uncertain, omit/flag the field rather than guess.
