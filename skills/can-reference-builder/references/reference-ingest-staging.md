# Reference ingest staging (Windows)

Recommended default when starting a **new** reference conversion or import on Windows.

## Shell discipline

**Determine PowerShell vs Command Prompt before giving copy/paste commands.**

| Shell | Path example |
|-------|----------------|
| PowerShell | `"$env:USERPROFILE\Downloads\file.json"` |
| Command Prompt | `"%USERPROFILE%\Downloads\file.json"` |

If the user provides an explicit path (e.g. `K:\Downloads\isobus_parameters_reference.json`), **use that exact path** — do not replace it with `%USERPROFILE%` or `$env:USERPROFILE` assumptions.

Command Prompt — use `cd /d` when changing drives to the repo before `uv run ...`.

## Staging convention

Before register / validate / import, suggest:

1. Place the **original** reference document in the user's **Downloads** folder.
2. Save the generated **Reference Bundle V1 JSON** (`<source_key>_reference.json`) in the
   **same Downloads** folder.
3. Run validate and import from those explicit paths while both files are together.

```text
Reference ingest staging:
For simplicity on Windows, place both the original reference document and the generated
normalized JSON file in your Downloads folder before validation/import. Keeping them
together makes CLI paths predictable and easy to paste. Downloads is only a staging
location; after `reference source add` / ingest, use the managed registry copy. Do not
commit private or licensed originals to the repository.
```

This is **recommended default** behaviour, not a hard requirement — another folder works if
paths stay explicit.

After successful ingest:

- `reference source add` retains the authoritative managed copy under
  `{data_dir}/reference_sources/`
- The Downloads copies can remain or be archived locally
- Do **not** move originals into the CAN Research repository or Skill packages

## Register source (if not already registered)

PowerShell:

```powershell
uv run canresearch reference source add "$env:USERPROFILE\Downloads\db_series_manual.pdf" `
  --key db_series_motor --type oem --visibility private
uv run canresearch reference source inspect db_series_motor
```

Explicit path form:

```powershell
uv run canresearch reference source add C:\Users\Office\Downloads\db_series_manual.pdf `
  --key db_series_motor --type oem --visibility private
```

Command Prompt — use `%USERPROFILE%\Downloads`; use `cd /d` when changing drives to the repo.

## After bundle output — validate and import

Save `<source_key>_reference.json` to Downloads, then:

```powershell
uv run canresearch reference bundle validate "$env:USERPROFILE\Downloads\db_series_motor_reference.json"
uv run canresearch reference bundle import "$env:USERPROFILE\Downloads\db_series_motor_reference.json"
uv run canresearch reference search "target rpm"
```

The Skill must **not** call import or modify the database directly — guide the user to run CLI.

## Privacy

- Default uncertain material to `private` visibility
- Never commit private/licensed originals to Git
- Never embed whole source documents in the bundle or Skill package

See [quality-and-provenance.md](quality-and-provenance.md).
