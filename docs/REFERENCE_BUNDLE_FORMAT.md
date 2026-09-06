# Reference bundle format (V1)

Formal handoff contract between **can-reference-builder**, other generative converters,
and **CAN Research** deterministic import.

**Full operator lifecycle:** [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md)  
**Knowledge model context:** [REFERENCE_DATA.md](REFERENCE_DATA.md)

```text
ORIGINAL SOURCE (retained, registered)
        ↓
generative conversion (external)
        ↓
reference_bundle.json  →  validate  →  import  →  MCP lookup/search
```

CAN Research **does not** parse arbitrary PDFs in-core. It validates and stores
normalized knowledge from Reference Bundle V1 JSON.

**Machine-readable schema:** [../schemas/reference-bundle-v1.schema.json](../schemas/reference-bundle-v1.schema.json)

**Synthetic examples (safe to commit):**

- [../tests/fixtures/reference_bundles/smartec_mownet_synthetic.json](../tests/fixtures/reference_bundles/smartec_mownet_synthetic.json) — J1939-like PGN document shape
- [../tests/fixtures/reference_bundles/db_series_driver_synthetic.json](../tests/fixtures/reference_bundles/db_series_driver_synthetic.json) — CAN ID family / register manual shape

---

## Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | yes | Must be `1` |
| `source_key` | yes | Must match a registered `reference source add` key |
| `generated_by` | no | Converter identity (e.g. `can-reference-builder`) |
| `generated_at` | no | ISO-8601 timestamp |
| `notes` | no | Free-form bundle notes |
| `messages` | no | Exact CAN message definitions |
| `message_families` | no | Pattern/mask families (variable node ID) |
| `registers` | no | Protocol register catalogue |
| `fault_codes` | no | Fault/status code table |
| `protocol_notes` | no | Bitrate, periods, checksum notes, etc. |
| `enums` | no | Object keyed by `enum_key` → array of `{value, name, description?}` |

Not every document uses every section. Missing optional metadata produces
**warnings**, not errors.

---

## Provenance (`source_location`)

Every object should include provenance where known:

```json
"source_location": {
  "page": 13,
  "section": "6.2 SPN Definition"
}
```

Or a string shorthand (stored as `{"section": "..."}`).

Do **not** invent page numbers. Partial provenance is acceptable.

---

## Message definition

```json
{
  "key": "dcm_control_sa8a",
  "name": "DCM Control",
  "protocol": "j1939",
  "can_id": "0x18FF3C8A",
  "is_extended": true,
  "pgn": 65340,
  "source_address": 138,
  "destination_address": null,
  "dlc": 8,
  "period_ms": 100,
  "priority": 6,
  "description": "...",
  "source_location": {"page": 13, "section": "6.2"},
  "signals": [ ... ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `key` | yes | Stable unique key within bundle |
| `name` | recommended | Human name |
| `can_id` | no* | Hex string or integer; 11-bit or 29-bit |
| `is_extended` | no | Defaults from CAN ID magnitude |
| `pgn` / addresses | no | J1939 fields when known |
| `signals` | no | Nested signal definitions |

\*Exact messages need `can_id` for exact lookup. Pattern-only knowledge belongs in `message_families`.

---

## Signal definition

```json
{
  "key": "target_rpm",
  "name": "TargetRPM",
  "start_bit": 0,
  "bit_length": 16,
  "byte_order": 1,
  "signedness": "unsigned",
  "factor": 0.5,
  "offset": 0,
  "unit": "rpm",
  "minimum": 0,
  "maximum": 8031.5,
  "description": "...",
  "enum_key": "dcm_mode",
  "source_location": {"page": 13, "section": "6.2.1"},
  "confidence": "high"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | recommended | Missing → warning |
| `start_bit`, `bit_length` | recommended | Overlap within message → **error** |
| `byte_order` | no | `1`/`intel` or `0`/`motorola` |
| `signedness` | no | `signed`, `unsigned`, `unknown` |
| `factor`, `offset`, `unit` | no | Missing scale → **warning** |
| `enum_key` | no | Must exist in top-level `enums` |

---

## Message family (pattern / mask)

For manuals describing **families** such as `0x187055??` or `0x1870??55`:

```json
{
  "key": "running_status",
  "name": "Running Status",
  "pattern": "0x18705500",
  "mask": "0xFFFFFF00",
  "variable_field": "node_id",
  "variable_role": "destination",
  "description": "Running status 0x187055??",
  "source_location": {"page": 12, "section": "CAN Protocol"}
}
```

**Matching rule (deterministic):**

```text
(can_id & (mask & 0x1FFFFFFF)) == (pattern & (mask & 0x1FFFFFFF))
```

CAN Research does **not** expand families into exact IDs automatically.

---

## Register definition

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
  "enum_key": null,
  "source_location": {"page": 18, "section": "Register Table"}
}
```

---

## Fault code definition

```json
{
  "key": "overtemp",
  "value": "0x01",
  "name": "OverTemperature",
  "description": "Motor over temperature",
  "source_location": {"page": 30, "section": "Fault Codes"}
}
```

---

## Protocol notes

Structured facts that are not single signals:

```json
{
  "key": "bitrate",
  "category": "bitrate",
  "name": "Nominal bitrate",
  "value": "250000",
  "unit": "bps",
  "description": "..."
}
```

Do not use free-text notes as a substitute for signal definitions when bit layout is known.

---

## Validation rules

CLI: `uv run canresearch reference bundle validate <path>`

| Severity | Examples |
|----------|----------|
| **Error** | Wrong schema version; unregistered `source_key`; invalid CAN ID; overlapping signals; unknown `enum_key`; invalid mask |
| **Warning** | Missing unit/scale; no exact CAN ID; incomplete family variable metadata; missing signal name |

Import requires **zero errors**. Warnings are printed but do not block import.

---

## Import

```powershell
uv run canresearch reference source add path\to\manual.pdf --key my_manual --visibility private
uv run canresearch reference bundle validate my_manual.json
uv run canresearch reference bundle import my_manual.json
uv run canresearch reference search "TargetRPM"
```

Re-importing the same bundle content replaces rows for that `source_key` (idempotent).

---

## Relationship to other knowledge

| Track | Purpose |
|-------|---------|
| **Reference source registry** | Original PDF/manual retention + visibility |
| **Normalized bundle import** | Deterministic messages/families/registers/faults |
| **J1939/ISOBUS PDF catalogue** | `reference import-j1939` / `import-isobus-pdf` → SQLite PGN/SPN |
| **DBC library** | `reference dbc register` → tuned DBC files |

All contribute to **known-first** analysis. DBC and bundle knowledge remain separate;
provenance is retained per source.

---

### External conversion (can-reference-builder)

The **can-reference-builder** Skill (source under `skills/can-reference-builder/`) outputs
Reference Bundle V1 JSON. Package locally with `scripts/package_skill.py` — see
[SKILL_INSTALLATION.md](SKILL_INSTALLATION.md). CAN Research validates and imports the
bundle deterministically; it does not parse arbitrary PDFs in-core.

See [USER_ONBOARDING.md](USER_ONBOARDING.md), [REFERENCE_ONBOARDING.md](REFERENCE_ONBOARDING.md),
and [REFERENCE_DATA.md](REFERENCE_DATA.md).
