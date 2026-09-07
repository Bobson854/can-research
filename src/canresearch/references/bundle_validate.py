"""Validation for normalized reference bundles (V1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from canresearch.references.bundle_common import (
    BUNDLE_SCHEMA_VERSION,
    BundleFormatError,
    SQLITE_INTEGER_MAX,
    SQLITE_INTEGER_MIN,
    coerce_storable_integer,
    family_matches,
    finite_float,
    normalize_byte_order,
    normalize_signedness,
    parse_can_id,
    parse_mask_pair,
    sqlite_integer_out_of_range,
)
from canresearch.references.source_registry import source_exists


@dataclass(slots=True)
class BundleValidationIssue:
    severity: str
    category: str
    message: str
    path: str = ""


@dataclass(slots=True)
class BundleValidationReport:
    valid: bool
    errors: list[BundleValidationIssue] = field(default_factory=list)
    warnings: list[BundleValidationIssue] = field(default_factory=list)

    def add_error(self, category: str, message: str, path: str = "") -> None:
        self.errors.append(BundleValidationIssue("error", category, message, path))
        self.valid = False

    def add_warning(self, category: str, message: str, path: str = "") -> None:
        self.warnings.append(BundleValidationIssue("warning", category, message, path))


def _validate_sqlite_integer_field(
    value: Any,
    *,
    path: str,
    field: str,
    report: BundleValidationReport,
) -> None:
    coerced = coerce_storable_integer(value)
    if coerced is None:
        return
    if sqlite_integer_out_of_range(coerced):
        report.add_error(
            "sqlite_integer",
            f"{path}.{field}={coerced} cannot be stored in SQLite INTEGER "
            f"(signed 64-bit range {SQLITE_INTEGER_MIN}..{SQLITE_INTEGER_MAX}); "
            f"omit the numeric field and preserve the source value in description or provenance",
            path,
        )


def format_bundle_warnings(warnings: list[BundleValidationIssue]) -> list[str]:
    """Format warnings for CLI output, summarizing repeated identical messages."""
    if not warnings:
        return []
    groups: dict[tuple[str, str], list[str]] = {}
    for issue in warnings:
        groups.setdefault((issue.category, issue.message), []).append(issue.path)

    lines: list[str] = []
    for (category, message), paths in groups.items():
        count = len(paths)
        if count > 1 and message == "no exact CAN ID on message":
            lines.append(
                f"WARN  [{category}] {count} messages have no exact CAN ID "
                f"(PGN-level definitions)"
            )
        elif count > 1:
            lines.append(f"WARN  [{category}] {count} occurrences: {message}")
        else:
            lines.append(f"WARN  [{category}] {paths[0]}: {message}")
    return lines


def _require_key(obj: dict[str, Any], path: str, report: BundleValidationReport) -> str | None:
    key = obj.get("key")
    if not key or not str(key).strip():
        report.add_error("missing_key", f"{path}: key is required", path)
        return None
    return str(key).strip()


def _validate_signal_overlap(
    signals: list[dict[str, Any]],
    *,
    path: str,
    report: BundleValidationReport,
) -> None:
    occupied: list[tuple[int, int]] = []
    for index, signal in enumerate(signals):
        spath = f"{path}.signals[{index}]"
        start = signal.get("start_bit")
        length = signal.get("bit_length")
        if start is None or length is None:
            continue
        try:
            start_i = int(start)
            length_i = int(length)
        except (TypeError, ValueError):
            report.add_error(
                "invalid_bit_field",
                f"{spath}: start_bit/bit_length must be integers",
                spath,
            )
            continue
        if start_i < 0 or length_i <= 0 or start_i + length_i > 512:
            report.add_error(
                "invalid_bit_field",
                f"{spath}: invalid bit range {start_i}|{length_i}",
                spath,
            )
            continue
        end = start_i + length_i
        for other_start, other_end in occupied:
            if start_i < other_end and end > other_start:
                report.add_error(
                    "signal_overlap",
                    f"{spath}: overlaps another signal in message",
                    spath,
                )
                break
        occupied.append((start_i, end))


def validate_reference_bundle(
    payload: dict[str, Any],
    *,
    require_registered_source: bool = True,
    data_dir: Any = None,
) -> BundleValidationReport:
    report = BundleValidationReport(valid=True)

    schema_version = payload.get("schema_version")
    if schema_version != BUNDLE_SCHEMA_VERSION:
        report.add_error(
            "schema_version",
            f"schema_version must be {BUNDLE_SCHEMA_VERSION}, got {schema_version!r}",
        )

    source_key = payload.get("source_key")
    if not source_key or not str(source_key).strip():
        report.add_error("source_key", "source_key is required")
    else:
        source_key = str(source_key).strip()
        if require_registered_source and not source_exists(source_key, data_dir=data_dir):
            report.add_error(
                "source_key",
                f"source_key {source_key!r} is not registered; use reference source add first",
            )

    enums = payload.get("enums", {})
    if enums is None:
        enums = {}
    if not isinstance(enums, dict):
        report.add_error("enums", "enums must be an object")
        enums = {}

    message_keys: set[str] = set()
    exact_can_ids: dict[tuple[bool, int], str] = {}

    messages = payload.get("messages", [])
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        report.add_error("messages", "messages must be an array")
        messages = []

    for index, message in enumerate(messages):
        mpath = f"messages[{index}]"
        if not isinstance(message, dict):
            report.add_error("message_shape", f"{mpath}: must be an object", mpath)
            continue
        obj_key = _require_key(message, mpath, report)
        if obj_key:
            if obj_key in message_keys:
                report.add_error("duplicate_key", f"duplicate message key {obj_key!r}", mpath)
            message_keys.add(obj_key)

        can_id = None
        is_extended = message.get("is_extended")
        try:
            can_id = parse_can_id(message.get("can_id"), field=f"{mpath}.can_id")
        except BundleFormatError as exc:
            report.add_error("can_id", str(exc), mpath)

        if can_id is None:
            report.add_warning("incomplete", "no exact CAN ID on message", mpath)
        else:
            ext = bool(is_extended) if is_extended is not None else can_id > 0x7FF
            id_key = (ext, can_id)
            if id_key in exact_can_ids:
                report.add_error(
                    "duplicate_can_id",
                    f"duplicate CAN ID {can_id:#x} (extended={ext})",
                    mpath,
                )
            else:
                exact_can_ids[id_key] = obj_key or mpath

        dlc = message.get("dlc")
        if dlc is not None:
            try:
                dlc_i = int(dlc)
                if dlc_i < 0 or dlc_i > 64:
                    report.add_error("dlc", f"{mpath}: dlc out of range", mpath)
            except (TypeError, ValueError):
                report.add_error("dlc", f"{mpath}: dlc must be integer", mpath)

        for field in ("pgn", "source_address", "destination_address", "period_ms", "priority", "dlc"):
            _validate_sqlite_integer_field(
                message.get(field),
                path=mpath,
                field=field,
                report=report,
            )

        signals = message.get("signals", [])
        if signals is None:
            signals = []
        if not isinstance(signals, list):
            report.add_error("signals", f"{mpath}.signals must be an array", mpath)
            signals = []
        else:
            signal_keys: set[str] = set()
            for sindex, signal in enumerate(signals):
                spath = f"{mpath}.signals[{sindex}]"
                if not isinstance(signal, dict):
                    report.add_error("signal_shape", f"{spath}: must be an object", spath)
                    continue
                sig_key = signal.get("key") or signal.get("name")
                if sig_key:
                    sig_key = str(sig_key).strip()
                    if sig_key in signal_keys:
                        report.add_error("duplicate_signal", f"duplicate signal {sig_key!r}", spath)
                    signal_keys.add(sig_key)
                if not signal.get("name"):
                    report.add_warning("incomplete", "signal name missing", spath)
                try:
                    if signal.get("byte_order") is not None:
                        normalize_byte_order(signal.get("byte_order"))
                    if signal.get("signedness") is not None:
                        normalize_signedness(signal.get("signedness"))
                    finite_float(signal.get("factor"), field=f"{spath}.factor")
                    finite_float(signal.get("offset"), field=f"{spath}.offset")
                except BundleFormatError as exc:
                    report.add_error("signal_field", str(exc), spath)
                enum_key = signal.get("enum_key")
                if enum_key and enum_key not in enums:
                    report.add_error("enum_reference", f"unknown enum_key {enum_key!r}", spath)
                if signal.get("factor") is None and signal.get("offset") is None:
                    report.add_warning("incomplete", "signal scale unknown", spath)
                if not signal.get("unit"):
                    report.add_warning("incomplete", "signal unit unknown", spath)
                for field in ("start_bit", "bit_length", "minimum", "maximum"):
                    _validate_sqlite_integer_field(
                        signal.get(field),
                        path=spath,
                        field=field,
                        report=report,
                    )
            _validate_signal_overlap(signals, path=mpath, report=report)

    families = payload.get("message_families", [])
    if families is None:
        families = []
    if not isinstance(families, list):
        report.add_error("message_families", "message_families must be an array")
        families = []

    family_keys: set[str] = set()
    for index, family in enumerate(families):
        fpath = f"message_families[{index}]"
        if not isinstance(family, dict):
            report.add_error("family_shape", f"{fpath}: must be an object", fpath)
            continue
        obj_key = _require_key(family, fpath, report)
        if obj_key:
            if obj_key in family_keys:
                report.add_error("duplicate_key", f"duplicate family key {obj_key!r}", fpath)
            family_keys.add(obj_key)
        try:
            pattern, mask = parse_mask_pair(
                family.get("pattern"),
                family.get("mask"),
                field=fpath,
            )
            if not family.get("variable_field") and not family.get("variable_role"):
                report.add_warning("incomplete", "no variable_field/role on message family", fpath)
            _ = pattern, mask
        except BundleFormatError as exc:
            report.add_error("message_family", str(exc), fpath)

    registers = payload.get("registers", [])
    if registers is None:
        registers = []
    if not isinstance(registers, list):
        report.add_error("registers", "registers must be an array")
        registers = []

    register_keys: set[str] = set()
    for index, reg in enumerate(registers):
        rpath = f"registers[{index}]"
        if not isinstance(reg, dict):
            report.add_error("register_shape", f"{rpath}: must be an object", rpath)
            continue
        obj_key = _require_key(reg, rpath, report)
        if obj_key:
            if obj_key in register_keys:
                report.add_error("duplicate_key", f"duplicate register key {obj_key!r}", rpath)
            register_keys.add(obj_key)
        address = reg.get("address")
        if address is None:
            report.add_warning("incomplete", "register address missing", rpath)
        try:
            if reg.get("byte_order") is not None:
                normalize_byte_order(reg.get("byte_order"))
            finite_float(reg.get("factor"), field=f"{rpath}.factor")
        except BundleFormatError as exc:
            report.add_error("register_field", str(exc), rpath)
        for field in ("address", "width", "minimum", "maximum", "default"):
            _validate_sqlite_integer_field(
                reg.get(field),
                path=rpath,
                field=field,
                report=report,
            )

    fault_codes = payload.get("fault_codes", [])
    if fault_codes is None:
        fault_codes = []
    if not isinstance(fault_codes, list):
        report.add_error("fault_codes", "fault_codes must be an array")
        fault_codes = []

    for index, fault in enumerate(fault_codes):
        fpath = f"fault_codes[{index}]"
        if not isinstance(fault, dict):
            report.add_error("fault_shape", f"{fpath}: must be an object", fpath)
            continue
        if fault.get("value") is None and not fault.get("name"):
            report.add_warning("incomplete", "fault code value/name missing", fpath)
        _validate_sqlite_integer_field(
            fault.get("value"),
            path=fpath,
            field="value",
            report=report,
        )

    notes = payload.get("protocol_notes", payload.get("notes", []))
    if notes is None:
        notes = []
    if not isinstance(notes, list):
        report.add_error("protocol_notes", "protocol_notes must be an array")
        notes = []

    for index, note in enumerate(notes):
        npath = f"protocol_notes[{index}]"
        if not isinstance(note, dict):
            report.add_error("note_shape", f"{npath}: must be an object", npath)

    return report


def acceptance_family_match(can_id: int, pattern: int, mask: int) -> bool:
    """Public helper for tests — family match predicate."""
    return family_matches(can_id, pattern, mask)
