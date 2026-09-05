# Strict DBC Compatibility Reference

## Purpose

This document records DBC parser issues found while validating existing files against the stricter parser used by CSS Electronics webCAN.

The main lesson is that SavvyCAN can tolerate some DBC constructs that stricter parsers reject. For future DBC generation and cleanup, prefer conservative, standards-friendly definitions that avoid ambiguous identifiers and overlapping non-multiplexed signals.

---

## Recommended Baseline Rules

Use these rules when creating or cleaning DBC files:

1. Use only letters, digits, and underscores in message and signal identifiers.
2. Do not begin an identifier with a digit.
3. Keep signal names unique within each message.
4. Avoid overlapping non-multiplexed signals.
5. Do not create duplicate aliases over the same bits just to provide raw, scaled, byte, or word views.
6. When a packed field is split into subfields, verify the bit ranges carefully.
7. Prefer one canonical engineering-value signal when both raw and scaled aliases exist.
8. If overlapping definitions are genuinely required, use proper multiplexing rather than relying on parser tolerance.
9. Treat webCAN acceptance as a useful stricter validation target.

---

# Error Types and Fixes

## 1. Invalid Identifier Characters

### Problem

Some DBC files used punctuation such as hyphens inside signal or message identifiers.

Examples:

```dbc
SG_ D-Flip_Output : 41|1@1+ ...
SG_ E-Stop_Set : 43|1@1+ ...
BO_ 2360147731 VDC2-Prop: 8 Vector__XXX
```

SavvyCAN may accept these, while webCAN rejects them.

### Fix

Replace punctuation with underscores.

```dbc
SG_ D_Flip_Output : 41|1@1+ ...
SG_ E_Stop_Set : 43|1@1+ ...
BO_ 2360147731 VDC2_Prop: 8 Vector__XXX
```

### Rule

Use:

```text
A-Z
a-z
0-9
_
```

Avoid:

```text
-
.
/
spaces
other punctuation
```

---

## 2. Identifier Begins With a Digit

### Problem

A signal name beginning with a number was rejected by the strict parser.

Example:

```dbc
SG_ 18173201_Connected : 47|1@1+ ...
```

### Fix

Prefix the identifier with a letter or meaningful word.

```dbc
SG_ CAN18173201_Connected : 47|1@1+ ...
```

### Rule

Identifiers should begin with a letter or underscore.

Preferred style:

```text
CAN18173201_Connected
Motor_1_Speed
Section_3_Status
```

---

## 3. Duplicate Signal Names Within One Message

### Problem

Two signals in the same message had the same name.

Example:

```dbc
SG_ Geo_Mid_IN : 6|1@1+ ...
SG_ Geo_Mid_IN : 7|1@1+ ...
```

### Fix

Rename the signals so each has a unique semantic meaning.

Example:

```dbc
SG_ Geo_Left_IN  : 5|1@1+ ...
SG_ Geo_Mid_IN   : 6|1@1+ ...
SG_ Geo_Right_IN : 7|1@1+ ...
```

### Rule

Signal names must be unique within the message.

Repeated signal names in different messages may be acceptable, but avoid duplicates inside the same `BO_` block.

---

## 4. Overlapping Non-Multiplexed Signals

### Problem

Two signals were defined over exactly the same bits.

Example:

```dbc
SG_ CAN_Motor_Speed        : 31|16@0+ ...
SG_ CAN_Motor_Scaled_Speed : 31|16@0+ ...
```

Another example:

```dbc
SG_ Motor_Speed_Output : 31|16@0+ ...
SG_ Motor_Speed_Shaft  : 31|16@0+ ...
```

SavvyCAN can tolerate these as alternate interpretations of the same raw value. webCAN rejects the overlap.

### Fix

Keep one canonical representation.

Prefer the engineering-value signal when appropriate.

Example:

```dbc
SG_ CAN_Motor_Scaled_Speed : 31|16@0+ (0.3,0) [0|65535] "RPM" Vector__XXX
```

Remove the raw alias unless it is genuinely needed elsewhere.

### Rule

One physical bit range should normally map to one non-multiplexed signal.

If multiple interpretations are required, document them outside the DBC or use a parser-supported multiplexing structure.

---

## 5. Incorrect Packed-Bit Start Position

### Problem

A packed field used the wrong start bit, unintentionally overlapping the previous field.

Example from a J1939 DM1-style DTC layout:

```dbc
SG_ SuspectParameterNumber : 16|19@1+ ...
SG_ FailureModeIdentifier  : 32|5@1+ ...
```

The 19-bit SPN occupies bits 16 through 34.

Starting the FMI at bit 32 therefore overlaps bits 32 through 34.

### Fix

Move the FMI start bit to 35.

```dbc
SG_ SuspectParameterNumber : 16|19@1+ ...
SG_ FailureModeIdentifier  : 35|5@1+ ...
```

### Rule

When defining packed fields:

```text
end_bit = start_bit + length - 1
```

The next adjacent little-endian field should begin at:

```text
next_start_bit = previous_start_bit + previous_length
```

Always verify the actual occupied bit range before adding the next field.

---

## 6. Convenience Aliases Over the Same Data

### Problem

Some DBC files contained multiple simultaneous views of the same bytes:

- full-word value
- high byte
- low byte
- raw value
- scaled value
- complete checksum
- checksum high byte
- checksum low byte
- complete heartbeat
- heartbeat high byte
- heartbeat low byte

Example pattern:

```dbc
SG_ Target_Data : ...
SG_ Target_Data_Byte_High : ...
SG_ Target_Data_Byte_Low : ...
```

These definitions are useful for manual analysis but create overlapping non-multiplexed signals.

### Fix

Keep one canonical representation.

For example:

```dbc
SG_ Target_Data : ...
```

Remove byte aliases unless they are genuinely separate protocol fields.

The same approach was used for:

```text
Heartbeat
Checksum_FULL
Motor_Speed_Output
```

### Rule

DBC files intended for strict parsers should describe the protocol, not provide every possible diagnostic view of the same bits.

Use external tooling for alternate byte/raw views.

---

## 7. Malformed Byte-Order or Sign Definition

### Problem

One tractor DBC contained a malformed signal definition:

```dbc
SG_ TransmissionRequestedRange : 32|16@4-
```

The `@4-` form was inconsistent with valid DBC byte-order syntax and with the same signal in the other tractor files.

### Fix

Corrected to:

```dbc
SG_ TransmissionRequestedRange : 32|16@1+
```

### Rule

The standard signal form is:

```dbc
SG_ SignalName : StartBit|Length@ByteOrderSign (Factor,Offset) [Min|Max] "Unit" Receiver
```

Where:

```text
@0 = Motorola / big-endian
@1 = Intel / little-endian

+ = unsigned
- = signed
```

Values such as `@4` are invalid.

---

## 8. Stray Signal Inserted Into an Existing Packed Layout

### Problem

A signal was found inside a message where it overlapped existing protocol fields and did not match the surrounding message structure.

Example:

```dbc
SG_ CCVSSig297 : 1|1@0+ ...
```

inside a `PTO_Info` message.

### Fix

Remove the stray signal when it is clearly not part of the actual message layout.

### Rule

When a single unexpected signal causes overlap:

1. Compare against equivalent messages.
2. Compare against known protocol structure.
3. Check whether the signal name belongs to another PGN/message.
4. Remove it if it is clearly an accidental insertion rather than moving bits arbitrarily.

---

## 9. Packed Subfield Positioned Over Another Subfield

### Problem

A Front PTO message had a 6-bit field starting on top of an existing 2-bit field.

The corresponding Rear PTO message showed the intended layout.

### Fix

Move the follow-on field to the correct adjacent start bit.

Example repair:

```dbc
SG_ Front_PTO_mode_request_status22 : 56|6@1+ ...
```

instead of the overlapping earlier start position.

### Rule

Equivalent message layouts are useful references.

If Front/Rear, Left/Right, or Channel 1/Channel 2 messages share the same protocol structure, compare them before guessing the intended bit position.

---

# Validation Workflow

A practical cleanup workflow is:

## Step 1 - Load in SavvyCAN

SavvyCAN remains useful for general viewing and basic validation.

However, successful import does **not** prove strict DBC compliance.

## Step 2 - Load in webCAN

Use webCAN as the stricter parser.

When it rejects a file, record:

- message name
- signal name
- parser error
- line number if available

## Step 3 - Fix the First Reported Error

Strict parsers often stop at the first failure.

Repair that issue, then reload.

## Step 4 - Continue Until the File Imports Cleanly

Each successful import confirms that:

- identifier syntax is acceptable
- duplicate/overlap checks have passed
- the parser can consume the whole file

## Step 5 - Preserve Semantic Intent

Do not blindly delete or move signals just to satisfy the parser.

Before changing a field:

- check neighboring fields
- compare equivalent messages
- compare known protocol documentation where available
- prefer the engineering-value representation over convenience aliases
- preserve actual bit layout

---

# Recommended DBC Generation Style

For future generated DBC files, use a conservative naming pattern.

## Messages

```text
Engine_Status
Motor_Command
PTO_Info
Active_Diagnostic_Trouble_Codes
```

## Signals

```text
Engine_Speed
Motor_Speed_RPM
Geo_Left_IN
Geo_Mid_IN
Geo_Right_IN
CAN18173201_Connected
Failure_Mode_Identifier
```

Avoid names such as:

```text
D-Flip_Output
E-Stop_Set
18173201_Connected
VDC2-Prop
```

---

# Preferred Signal Design

Prefer:

```dbc
SG_ Motor_Speed_RPM : 31|16@0+ (0.3,0) [0|19660.5] "RPM" Vector__XXX
```

rather than defining both:

```dbc
SG_ Motor_Speed_Raw : 31|16@0+ ...
SG_ Motor_Speed_RPM : 31|16@0+ ...
```

Likewise, prefer:

```dbc
SG_ Checksum : 48|16@1+ ...
```

rather than also defining:

```dbc
SG_ Checksum_High : ...
SG_ Checksum_Low : ...
```

unless those bytes are independently meaningful protocol fields.

---

# Known Behaviour Difference

## SavvyCAN

Observed to tolerate some of the following:

- hyphens in identifiers
- duplicate/alias signal definitions
- overlapping non-multiplexed signals
- convenience raw/scaled views

## CSS Electronics webCAN

Observed to reject:

- invalid identifiers
- overlapping non-multiplexed signals
- malformed signal definitions
- incorrect packed-bit layouts

For this reason, webCAN is a useful target for producing cleaner and more portable DBC files.

---

# Files Successfully Cleaned During This Exercise

The following types of files were repaired and successfully imported into webCAN:

- PLC output / control DBC
- John Deere tractor DBC
- DB Series CAN Motor DBC
- three additional tractor DBCs

These files exposed the error classes documented above.

---

# Future Checklist

Before considering a generated DBC complete, check:

- [ ] Message identifiers contain only letters, digits, and underscores
- [ ] Signal identifiers contain only letters, digits, and underscores
- [ ] No identifier begins with a digit
- [ ] Signal names are unique within each message
- [ ] No unintended signal overlap exists
- [ ] No raw/scaled aliases occupy the same bits
- [ ] No high-byte/low-byte aliases overlap a full-word signal
- [ ] Packed fields use correct start bits
- [ ] Byte-order field is only `@0` or `@1`
- [ ] Sign is explicitly `+` or `-`
- [ ] Equivalent messages use consistent layouts
- [ ] File imports successfully into webCAN
- [ ] File still decodes correctly in SavvyCAN

---

# Suggested Policy Going Forward

For CSS Electronics / CAN Research work:

> A DBC should not be considered finished merely because SavvyCAN can open it. It should also pass a stricter parser such as CSS Electronics webCAN without syntax, overlap, or layout errors.

This gives us a more portable baseline for future DBC generation, automated tooling, CANedge workflows, and other software that may use stricter DBC libraries.
