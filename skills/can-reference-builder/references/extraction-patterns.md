# Extraction patterns

## J1939-like OEM manual

Look for:

- PGN / CAN ID / priority / SA / DA
- message period and timeout
- field byte/bit position
- bit length
- signedness
- scale/offset/unit
- enum/value tables
- source-address assignments
- fault/status codes
- network bitrate

Map exact messages into `messages`; non-field operational facts into `protocol_notes`.

## Proprietary CAN family manual

When IDs contain a variable node component (`??`, configurable byte, address nibble):

- derive `pattern` only from fixed bits stated by source
- derive `mask` from fixed/variable positions
- describe the variable field/role if the manual says what it means
- do not create every possible node ID

Put register read/write/reply transactions in `message_families` and the parameter catalogue in `registers`.

## Spreadsheet / CSV

Use column semantics rather than file layout. Preserve row provenance with sheet/table/row description where practical. If columns conflict or use undocumented shorthand, do not infer a meaning solely from naming.

## DBC-derived source

A DBC is already structured, but the normalized bundle is not a replacement for the DBC library. Use bundle conversion only when the user wants its facts represented in reference knowledge. Preserve DBC endian semantics carefully; normalize bit numbering before setting `start_bit`.

## Diagrams and images

Use visual interpretation when the document expresses layouts graphically. Cross-check the diagram against nearby text/tables. If they disagree, record the conflict rather than choosing silently.

## Cross-page definitions

A message may be defined on one page and its enum/fault table later. Combine them only when the source clearly links them. Provenance may point each object/field to its own page/section.
