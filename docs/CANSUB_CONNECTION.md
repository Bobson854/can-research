# CANsub.2 USB / Ethernet connection notes

Observed behaviour on the development desk unit (Device ID `7413f810`). This is
**not** vendor-guaranteed documentation — it records what we have tested locally.

## What works

- CANsub.2 USB networking to the Windows development laptop
- Direct **HTTPS REST** access on port **443** (`https://<host>/api/...`)
- CLI `--host` accepts either a **hostname** or an **IP address**

Example hostname (observed after power cycle):

```text
7413f810-usb.local
```

Example commands:

```powershell
uv run canresearch device info --host 7413f810-usb.local
uv run canresearch device info --host 10.174.12.1
```

## USB IP vs mDNS hostname

| Method | Observed behaviour |
|--------|--------------------|
| USB IP | **Not stable** across power cycles (e.g. `10.158.28.1` before, `10.174.12.1` after) |
| USB mDNS hostname | **Appears stable** across tested power cycles (`7413f810-usb.local` resolved correctly after IP change) |

**Recommendation:** configure the mDNS hostname rather than the temporary USB IP.

```powershell
uv run canresearch config set-host 7413f810-usb.local
uv run canresearch device info
```

## Persistent configuration

Local settings are stored in `data/config.toml` (gitignored). See
`config.toml.example` for the template.

Precedence:

1. CLI `--host` (explicit override)
2. `[cansub].host` in `data/config.toml`
3. Clear error if neither is set

## Read-only REST endpoints in use

| Endpoint | Purpose |
|----------|---------|
| `GET /api/version` | API version |
| `GET /api/info` | Device identity |
| `GET /api/can` | Channel list |
| `GET /api/can/{channel}` | Channel status |
| `GET /api/can/{channel}/phy` | Channel PHY timing (read-only) |
| `WS /api/can/{channel}/ws` | Live CAN RX (binary HDLC-framed messages) |

TLS: the device presents a hostname-based certificate. Direct IP or `.local`
access typically requires `verify_tls = false` in config until the CSS root
certificate is integrated.

## Desk unit snapshot (2026-03)

```text
Device ID:  7413f810
API:        03.00
Hardware:   01.00
Firmware:   02.03.00
Channels:   1, 2
```

No CAN bus was connected during initial bring-up; channel `state` was `stopped`
with zero frames — expected.
