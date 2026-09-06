"""Import and lookup for normalized reference bundle knowledge."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from canresearch.references.bundle_common import (
    family_matches,
    load_bundle_json,
    normalize_byte_order,
    normalize_signedness,
    parse_can_id,
    parse_mask_pair,
    source_location_to_json,
)
from canresearch.references.bundle_validate import BundleValidationReport, validate_reference_bundle


@dataclass(slots=True)
class BundleImportReport:
    source_key: str
    fingerprint: str
    messages: int = 0
    signals: int = 0
    message_families: int = 0
    registers: int = 0
    fault_codes: int = 0
    protocol_notes: int = 0
    enums: int = 0


def bundle_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def import_reference_bundle(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    replace: bool = True,
) -> BundleImportReport:
    """Import validated bundle knowledge into SQLite."""
    source_key = str(payload["source_key"]).strip()
    fingerprint = bundle_fingerprint(payload)

    if replace:
        for table in (
            "reference_knowledge_signals",
            "reference_knowledge_messages",
            "reference_knowledge_message_families",
            "reference_knowledge_registers",
            "reference_knowledge_fault_codes",
            "reference_knowledge_protocol_notes",
            "reference_knowledge_enums",
        ):
            conn.execute(f"DELETE FROM {table} WHERE source_key = ?", (source_key,))

    conn.execute(
        """
        INSERT INTO reference_knowledge_imports (
            source_key, bundle_schema_version, generated_by, generated_at, fingerprint
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_key, fingerprint) DO UPDATE SET
            imported_at = datetime('now')
        """,
        (
            source_key,
            int(payload.get("schema_version", 1)),
            payload.get("generated_by"),
            payload.get("generated_at"),
            fingerprint,
        ),
    )

    report = BundleImportReport(source_key=source_key, fingerprint=fingerprint)
    enums = payload.get("enums") or {}
    if isinstance(enums, dict):
        for enum_key, values in enums.items():
            conn.execute(
                """
                INSERT INTO reference_knowledge_enums (source_key, enum_key, values_json)
                VALUES (?, ?, ?)
                ON CONFLICT(source_key, enum_key) DO UPDATE SET values_json = excluded.values_json
                """,
                (source_key, str(enum_key), json.dumps(values, separators=(",", ":"))),
            )
            report.enums += 1

    for message in payload.get("messages") or []:
        if not isinstance(message, dict):
            continue
        obj_key = str(message["key"]).strip()
        can_id = parse_can_id(message.get("can_id"), field="can_id")
        is_ext = message.get("is_extended")
        is_extended = int(bool(is_ext if is_ext is not None else (can_id or 0) > 0x7FF))
        conn.execute(
            """
            INSERT INTO reference_knowledge_messages (
                source_key, object_key, name, protocol, can_id, is_extended, pgn,
                source_address, destination_address, dlc, period_ms, priority,
                description, source_location_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key, object_key) DO UPDATE SET
                name = excluded.name, protocol = excluded.protocol, can_id = excluded.can_id,
                is_extended = excluded.is_extended, pgn = excluded.pgn,
                source_address = excluded.source_address,
                destination_address = excluded.destination_address,
                dlc = excluded.dlc, period_ms = excluded.period_ms,
                priority = excluded.priority, description = excluded.description,
                source_location_json = excluded.source_location_json,
                confidence = excluded.confidence,
                updated_at = datetime('now')
            """,
            (
                source_key,
                obj_key,
                message.get("name"),
                message.get("protocol"),
                can_id,
                is_extended,
                message.get("pgn"),
                message.get("source_address"),
                message.get("destination_address"),
                message.get("dlc"),
                message.get("period_ms"),
                message.get("priority"),
                message.get("description"),
                source_location_to_json(message.get("source_location")),
                message.get("confidence"),
            ),
        )
        report.messages += 1

        for signal in message.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            sig_key = str(signal.get("key") or signal.get("name")).strip()
            byte_order = None
            if signal.get("byte_order") is not None:
                byte_order = normalize_byte_order(signal.get("byte_order"))
            signedness = None
            if signal.get("signedness") is not None:
                signedness = normalize_signedness(signal.get("signedness"))
            conn.execute(
                """
                INSERT INTO reference_knowledge_signals (
                    source_key, message_object_key, signal_key, name, start_bit, bit_length,
                    byte_order, signedness, factor, offset, unit, minimum, maximum,
                    description, enum_key, source_location_json, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key, message_object_key, signal_key) DO UPDATE SET
                    name = excluded.name, start_bit = excluded.start_bit,
                    bit_length = excluded.bit_length, byte_order = excluded.byte_order,
                    signedness = excluded.signedness, factor = excluded.factor,
                    offset = excluded.offset, unit = excluded.unit,
                    minimum = excluded.minimum, maximum = excluded.maximum,
                    description = excluded.description, enum_key = excluded.enum_key,
                    source_location_json = excluded.source_location_json,
                    confidence = excluded.confidence,
                    updated_at = datetime('now')
                """,
                (
                    source_key,
                    obj_key,
                    sig_key,
                    signal.get("name"),
                    signal.get("start_bit"),
                    signal.get("bit_length"),
                    byte_order,
                    signedness,
                    signal.get("factor"),
                    signal.get("offset"),
                    signal.get("unit"),
                    signal.get("minimum"),
                    signal.get("maximum"),
                    signal.get("description"),
                    signal.get("enum_key"),
                    source_location_to_json(signal.get("source_location")),
                    signal.get("confidence"),
                ),
            )
            report.signals += 1

    for family in payload.get("message_families") or []:
        if not isinstance(family, dict):
            continue
        obj_key = str(family["key"]).strip()
        pattern, mask = parse_mask_pair(family.get("pattern"), family.get("mask"), field=obj_key)
        conn.execute(
            """
            INSERT INTO reference_knowledge_message_families (
                source_key, object_key, name, pattern, mask, variable_field, variable_role,
                description, source_location_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key, object_key) DO UPDATE SET
                name = excluded.name, pattern = excluded.pattern, mask = excluded.mask,
                variable_field = excluded.variable_field, variable_role = excluded.variable_role,
                description = excluded.description,
                source_location_json = excluded.source_location_json,
                confidence = excluded.confidence,
                updated_at = datetime('now')
            """,
            (
                source_key,
                obj_key,
                family.get("name"),
                pattern,
                mask,
                family.get("variable_field"),
                family.get("variable_role"),
                family.get("description"),
                source_location_to_json(family.get("source_location")),
                family.get("confidence"),
            ),
        )
        report.message_families += 1

    for reg in payload.get("registers") or []:
        if not isinstance(reg, dict):
            continue
        obj_key = str(reg["key"]).strip()
        conn.execute(
            """
            INSERT INTO reference_knowledge_registers (
                source_key, object_key, address, name, width, signedness, factor, offset, unit,
                access, minimum, maximum, default_value, description, enum_key,
                source_location_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key, object_key) DO UPDATE SET
                address = excluded.address, name = excluded.name, width = excluded.width,
                signedness = excluded.signedness, factor = excluded.factor,
                offset = excluded.offset, unit = excluded.unit, access = excluded.access,
                minimum = excluded.minimum, maximum = excluded.maximum,
                default_value = excluded.default_value, description = excluded.description,
                enum_key = excluded.enum_key,
                source_location_json = excluded.source_location_json,
                confidence = excluded.confidence,
                updated_at = datetime('now')
            """,
            (
                source_key,
                obj_key,
                reg.get("address"),
                reg.get("name"),
                reg.get("width"),
                reg.get("signedness"),
                reg.get("factor"),
                reg.get("offset"),
                reg.get("unit"),
                reg.get("access"),
                reg.get("minimum"),
                reg.get("maximum"),
                reg.get("default"),
                reg.get("description"),
                reg.get("enum_key"),
                source_location_to_json(reg.get("source_location")),
                reg.get("confidence"),
            ),
        )
        report.registers += 1

    for fault in payload.get("fault_codes") or []:
        if not isinstance(fault, dict):
            continue
        obj_key = str(fault.get("key") or fault.get("name") or fault.get("value")).strip()
        conn.execute(
            """
            INSERT INTO reference_knowledge_fault_codes (
                source_key, object_key, value, name, description, source_location_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key, object_key) DO UPDATE SET
                value = excluded.value, name = excluded.name,
                description = excluded.description,
                source_location_json = excluded.source_location_json,
                updated_at = datetime('now')
            """,
            (
                source_key,
                obj_key,
                fault.get("value"),
                fault.get("name"),
                fault.get("description"),
                source_location_to_json(fault.get("source_location")),
            ),
        )
        report.fault_codes += 1

    for note in payload.get("protocol_notes") or payload.get("notes") or []:
        if not isinstance(note, dict):
            continue
        obj_key = str(note.get("key") or note.get("category") or note.get("name")).strip()
        conn.execute(
            """
            INSERT INTO reference_knowledge_protocol_notes (
                source_key, object_key, category, name, value, unit, description,
                source_location_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key, object_key) DO UPDATE SET
                category = excluded.category, name = excluded.name, value = excluded.value,
                unit = excluded.unit, description = excluded.description,
                source_location_json = excluded.source_location_json,
                updated_at = datetime('now')
            """,
            (
                source_key,
                obj_key,
                note.get("category"),
                note.get("name"),
                note.get("value"),
                note.get("unit"),
                note.get("description"),
                source_location_to_json(note.get("source_location")),
            ),
        )
        report.protocol_notes += 1

    conn.commit()
    return report


def import_bundle_file(
    conn: sqlite3.Connection,
    path: Path,
    *,
    data_dir: Any = None,
    skip_validation: bool = False,
) -> tuple[BundleImportReport, BundleValidationReport | None]:
    payload = load_bundle_json(path)
    validation: BundleValidationReport | None = None
    if not skip_validation:
        validation = validate_reference_bundle(payload, data_dir=data_dir)
        if not validation.valid:
            msg = f"Bundle validation failed with {len(validation.errors)} error(s)"
            raise ValueError(msg)
    report = import_reference_bundle(conn, payload)
    return report, validation


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def lookup_message_by_can_id(
    conn: sqlite3.Connection,
    *,
    can_id: int,
    is_extended: bool,
    source_key: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT * FROM reference_knowledge_messages
        WHERE can_id = ? AND is_extended = ?
    """
    params: list[Any] = [can_id, int(is_extended)]
    if source_key:
        query += " AND source_key = ?"
        params.append(source_key)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def lookup_message_families_by_can_id(
    conn: sqlite3.Connection,
    *,
    can_id: int,
    source_key: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM reference_knowledge_message_families"
    params: list[Any] = []
    if source_key:
        query += " WHERE source_key = ?"
        params.append(source_key)
    rows = conn.execute(query, params).fetchall()
    matches: list[dict[str, Any]] = []
    for row in rows:
        if family_matches(can_id, int(row["pattern"]), int(row["mask"])):
            item = _row_to_dict(row)
            item["match_type"] = "message_family"
            matches.append(item)
    return matches


def lookup_message_by_pgn(
    conn: sqlite3.Connection,
    *,
    pgn: int,
    source_key: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM reference_knowledge_messages WHERE pgn = ?"
    params: list[Any] = [pgn]
    if source_key:
        query += " AND source_key = ?"
        params.append(source_key)
    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def lookup_signals_for_message(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    message_object_key: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM reference_knowledge_signals
        WHERE source_key = ? AND message_object_key = ?
        ORDER BY start_bit
        """,
        (source_key, message_object_key),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def search_reference_knowledge(
    conn: sqlite3.Connection,
    *,
    query: str,
    source_key: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    pattern = f"%{query.strip()}%"
    results: dict[str, list[dict[str, Any]]] = {
        "messages": [],
        "signals": [],
        "message_families": [],
        "registers": [],
        "fault_codes": [],
        "protocol_notes": [],
    }
    if not query.strip():
        return {"query": query, "results": results, "total": 0}

    def _search(table: str, columns: tuple[str, ...], bucket: str) -> None:
        where = " OR ".join(f"{col} LIKE ?" for col in columns)
        sql = f"SELECT * FROM {table} WHERE ({where})"
        params: list[Any] = [pattern] * len(columns)
        if source_key:
            sql += " AND source_key = ?"
            params.append(source_key)
        sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, params).fetchall()
        results[bucket] = [_row_to_dict(row) for row in rows]

    _search(
        "reference_knowledge_messages",
        ("name", "description", "object_key", "protocol"),
        "messages",
    )
    _search(
        "reference_knowledge_signals",
        ("name", "description", "signal_key", "unit"),
        "signals",
    )
    _search(
        "reference_knowledge_message_families",
        ("name", "description", "object_key", "variable_field"),
        "message_families",
    )
    _search(
        "reference_knowledge_registers",
        ("name", "description", "object_key"),
        "registers",
    )
    _search(
        "reference_knowledge_fault_codes",
        ("name", "description", "object_key"),
        "fault_codes",
    )
    _search(
        "reference_knowledge_protocol_notes",
        ("name", "description", "category", "value"),
        "protocol_notes",
    )
    total = sum(len(items) for items in results.values())
    return {"query": query, "results": results, "total": total}


def knowledge_stats(conn: sqlite3.Connection, source_key: str | None = None) -> dict[str, int]:
    tables = (
        "reference_knowledge_messages",
        "reference_knowledge_signals",
        "reference_knowledge_message_families",
        "reference_knowledge_registers",
        "reference_knowledge_fault_codes",
        "reference_knowledge_protocol_notes",
    )
    stats: dict[str, int] = {}
    for table in tables:
        if source_key:
            row = conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE source_key = ?",
                (source_key,),
            ).fetchone()
        else:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
        stats[table.removeprefix("reference_knowledge_")] = int(row["c"])
    return stats
