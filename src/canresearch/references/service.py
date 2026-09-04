"""Reference catalogue database operations."""

from __future__ import annotations

import sqlite3
from typing import Any

from canresearch.references.models import ParsedDdi, ParsedPgn, ParsedPgnSpnMapping, ParsedSpn


class ReferenceService:
    """CRUD and lookup for normalized reference tables."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def ensure_source(
        self,
        *,
        source_key: str,
        source_type: str,
        title: str,
        revision: str,
        coverage_date: str,
        origin: str,
        source_path: str | None = None,
        source_url: str | None = None,
        fingerprint: str | None = None,
        notes: str | None = None,
    ) -> int:
        row = self.conn.execute(
            "SELECT id FROM reference_sources WHERE source_key = ?",
            (source_key,),
        ).fetchone()
        if row:
            self.conn.execute(
                """
                UPDATE reference_sources
                SET source_type = ?, title = ?, revision = ?, coverage_date = ?,
                    origin = ?, source_path = ?, source_url = ?, fingerprint = ?,
                    imported_at = datetime('now'), notes = ?
                WHERE id = ?
                """,
                (
                    source_type,
                    title,
                    revision,
                    coverage_date,
                    origin,
                    source_path,
                    source_url,
                    fingerprint,
                    notes,
                    row["id"],
                ),
            )
            return int(row["id"])

        cursor = self.conn.execute(
            """
            INSERT INTO reference_sources (
                source_key, source_type, title, revision, coverage_date, origin,
                source_path, source_url, fingerprint, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_key,
                source_type,
                title,
                revision,
                coverage_date,
                origin,
                source_path,
                source_url,
                fingerprint,
                notes,
            ),
        )
        return int(cursor.lastrowid)

    def _row_changed(self, existing: sqlite3.Row, values: dict[str, Any]) -> bool:
        def norm(value: object) -> object:
            if value == "":
                return None
            return value

        return any(norm(existing[key]) != norm(value) for key, value in values.items())

    def upsert_spn(self, source_id: int, origin: str, spn: ParsedSpn) -> dict[str, int]:
        values = {
            "name": spn.name,
            "definition": spn.definition,
            "description": spn.description,
            "data_length_bits": spn.data_length_bits,
            "resolution": spn.resolution,
            "offset": spn.offset,
            "minimum": spn.minimum,
            "maximum": spn.maximum,
            "unit": spn.unit,
            "data_type": spn.data_type,
            "status": spn.status,
            "source_page": spn.source_page,
            "raw_text": spn.raw_text,
        }
        existing = self.conn.execute(
            "SELECT * FROM reference_spns WHERE source_id = ? AND spn = ?",
            (source_id, spn.spn),
        ).fetchone()

        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        if existing is None:
            self.conn.execute(
                """
                INSERT INTO reference_spns (
                    spn, name, definition, description, data_length_bits, resolution,
                    offset, minimum, maximum, unit, data_type, status, source_id,
                    origin, source_page, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spn.spn,
                    values["name"],
                    values["definition"],
                    values["description"],
                    values["data_length_bits"],
                    values["resolution"],
                    values["offset"],
                    values["minimum"],
                    values["maximum"],
                    values["unit"],
                    values["data_type"],
                    values["status"],
                    source_id,
                    origin,
                    values["source_page"],
                    values["raw_text"],
                ),
            )
            counts["inserted"] = 1
        elif self._row_changed(existing, values):
            self.conn.execute(
                """
                UPDATE reference_spns SET
                    name = ?, definition = ?, description = ?, data_length_bits = ?,
                    resolution = ?, offset = ?, minimum = ?, maximum = ?, unit = ?,
                    data_type = ?, status = ?, origin = ?, source_page = ?, raw_text = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    values["name"],
                    values["definition"],
                    values["description"],
                    values["data_length_bits"],
                    values["resolution"],
                    values["offset"],
                    values["minimum"],
                    values["maximum"],
                    values["unit"],
                    values["data_type"],
                    values["status"],
                    origin,
                    values["source_page"],
                    values["raw_text"],
                    existing["id"],
                ),
            )
            counts["updated"] = 1
        else:
            counts["unchanged"] = 1
        return counts

    def upsert_pgn(self, source_id: int, origin: str, pgn: ParsedPgn) -> dict[str, int]:
        values = {
            "name": pgn.name,
            "acronym": pgn.acronym,
            "description": pgn.description,
            "transmission_rate": pgn.transmission_rate,
            "payload_length": pgn.payload_length,
            "default_priority": pgn.default_priority,
            "data_page": pgn.data_page,
            "pdu_format": pgn.pdu_format,
            "pdu_specific": pgn.pdu_specific,
            "source_page": pgn.source_page,
            "raw_text": pgn.raw_text,
        }
        existing = self.conn.execute(
            "SELECT * FROM reference_pgns WHERE source_id = ? AND pgn = ?",
            (source_id, pgn.pgn),
        ).fetchone()

        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        if existing is None:
            self.conn.execute(
                """
                INSERT INTO reference_pgns (
                    pgn, name, acronym, description, transmission_rate, payload_length,
                    default_priority, data_page, pdu_format, pdu_specific, source_id,
                    origin, source_page, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pgn.pgn,
                    values["name"],
                    values["acronym"],
                    values["description"],
                    values["transmission_rate"],
                    values["payload_length"],
                    values["default_priority"],
                    values["data_page"],
                    values["pdu_format"],
                    values["pdu_specific"],
                    source_id,
                    origin,
                    values["source_page"],
                    values["raw_text"],
                ),
            )
            counts["inserted"] = 1
        elif self._row_changed(existing, values):
            self.conn.execute(
                """
                UPDATE reference_pgns SET
                    name = ?, acronym = ?, description = ?, transmission_rate = ?,
                    payload_length = ?, default_priority = ?, data_page = ?,
                    pdu_format = ?, pdu_specific = ?, origin = ?, source_page = ?,
                    raw_text = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    values["name"],
                    values["acronym"],
                    values["description"],
                    values["transmission_rate"],
                    values["payload_length"],
                    values["default_priority"],
                    values["data_page"],
                    values["pdu_format"],
                    values["pdu_specific"],
                    origin,
                    values["source_page"],
                    values["raw_text"],
                    existing["id"],
                ),
            )
            counts["updated"] = 1
        else:
            counts["unchanged"] = 1
        return counts

    def upsert_pgn_spn_mapping(
        self,
        source_id: int,
        pgn_number: int,
        mapping: ParsedPgnSpnMapping,
    ) -> None:
        pgn_row = self.conn.execute(
            "SELECT id FROM reference_pgns WHERE source_id = ? AND pgn = ?",
            (source_id, pgn_number),
        ).fetchone()
        spn_row = self.conn.execute(
            "SELECT id FROM reference_spns WHERE source_id = ? AND spn = ?",
            (source_id, mapping.spn),
        ).fetchone()
        if pgn_row is None:
            return

        spn_id = spn_row["id"] if spn_row else None
        existing = self.conn.execute(
            """
            SELECT id FROM reference_pgn_spns
            WHERE source_id = ? AND pgn_id = ? AND spn = ? AND raw_position_text = ?
            """,
            (source_id, pgn_row["id"], mapping.spn, mapping.raw_position_text),
        ).fetchone()

        if existing:
            return

        self.conn.execute(
            """
            INSERT INTO reference_pgn_spns (
                pgn_id, spn_id, spn, position_order, start_byte, start_bit,
                bit_length, byte_order, source_id, source_page, raw_position_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pgn_row["id"],
                spn_id,
                mapping.spn,
                mapping.position_order,
                mapping.start_byte,
                mapping.start_bit,
                mapping.bit_length,
                mapping.byte_order,
                source_id,
                mapping.source_page,
                mapping.raw_position_text,
            ),
        )

    def upsert_ddi(self, source_id: int, origin: str, ddi: ParsedDdi) -> dict[str, int]:
        values = {
            "name": ddi.name,
            "definition": ddi.definition,
            "comment": ddi.comment,
            "unit_symbol": ddi.unit_symbol,
            "unit_description": ddi.unit_description,
            "resolution": ddi.resolution,
            "can_min": ddi.can_min,
            "can_max": ddi.can_max,
            "display_min": ddi.display_min,
            "display_max": ddi.display_max,
            "sae_spn": ddi.sae_spn,
            "submit_by": ddi.submit_by,
            "submit_date": ddi.submit_date,
            "submit_company": ddi.submit_company,
            "revision_number": ddi.revision_number,
            "current_status": ddi.current_status,
            "status_date": ddi.status_date,
            "status_comments": ddi.status_comments,
            "source_page": ddi.source_page,
            "raw_text": ddi.raw_text,
        }
        existing = self.conn.execute(
            "SELECT * FROM reference_ddis WHERE source_id = ? AND ddi = ?",
            (source_id, ddi.ddi),
        ).fetchone()

        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        if existing is None:
            cursor = self.conn.execute(
                """
                INSERT INTO reference_ddis (
                    ddi, name, definition, comment, unit_symbol, unit_description,
                    resolution, can_min, can_max, display_min, display_max, sae_spn,
                    submit_by, submit_date, submit_company, revision_number,
                    current_status, status_date, status_comments, source_id, origin,
                    source_page, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ddi.ddi,
                    values["name"],
                    values["definition"],
                    values["comment"],
                    values["unit_symbol"],
                    values["unit_description"],
                    values["resolution"],
                    values["can_min"],
                    values["can_max"],
                    values["display_min"],
                    values["display_max"],
                    values["sae_spn"],
                    values["submit_by"],
                    values["submit_date"],
                    values["submit_company"],
                    values["revision_number"],
                    values["current_status"],
                    values["status_date"],
                    values["status_comments"],
                    source_id,
                    origin,
                    values["source_page"],
                    values["raw_text"],
                ),
            )
            ddi_id = int(cursor.lastrowid)
            counts["inserted"] = 1
        elif self._row_changed(existing, values):
            self.conn.execute(
                """
                UPDATE reference_ddis SET
                    name = ?, definition = ?, comment = ?, unit_symbol = ?,
                    unit_description = ?, resolution = ?, can_min = ?, can_max = ?,
                    display_min = ?, display_max = ?, sae_spn = ?, submit_by = ?,
                    submit_date = ?, submit_company = ?, revision_number = ?,
                    current_status = ?, status_date = ?, status_comments = ?,
                    origin = ?, source_page = ?, raw_text = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    values["name"],
                    values["definition"],
                    values["comment"],
                    values["unit_symbol"],
                    values["unit_description"],
                    values["resolution"],
                    values["can_min"],
                    values["can_max"],
                    values["display_min"],
                    values["display_max"],
                    values["sae_spn"],
                    values["submit_by"],
                    values["submit_date"],
                    values["submit_company"],
                    values["revision_number"],
                    values["current_status"],
                    values["status_date"],
                    values["status_comments"],
                    origin,
                    values["source_page"],
                    values["raw_text"],
                    existing["id"],
                ),
            )
            ddi_id = int(existing["id"])
            counts["updated"] = 1
        else:
            ddi_id = int(existing["id"])
            counts["unchanged"] = 1

        self.conn.execute(
            "DELETE FROM reference_ddi_device_classes WHERE ddi_id = ?",
            (ddi_id,),
        )
        for device_class, device_class_name in ddi.device_classes:
            self.conn.execute(
                """
                INSERT INTO reference_ddi_device_classes (ddi_id, device_class, device_class_name)
                VALUES (?, ?, ?)
                """,
                (ddi_id, device_class, device_class_name),
            )
        return counts

    def stats(self) -> dict[str, int]:
        def count(table: str) -> int:
            return self.conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]  # noqa: S608

        return {
            "sources": count("reference_sources"),
            "pgns": count("reference_pgns"),
            "spns": count("reference_spns"),
            "mappings": count("reference_pgn_spns"),
            "ddis": count("reference_ddis"),
        }

    def lookup_pgn(self, pgn: int, origin: str | None = None) -> list[sqlite3.Row]:
        if origin:
            return self.conn.execute(
                """
                SELECT p.*, s.title AS source_title, s.revision AS source_revision,
                       s.coverage_date, s.origin AS source_origin
                FROM reference_pgns p
                JOIN reference_sources s ON s.id = p.source_id
                WHERE p.pgn = ? AND p.origin = ?
                ORDER BY p.source_id
                """,
                (pgn, origin),
            ).fetchall()
        return self.conn.execute(
            """
            SELECT p.*, s.title AS source_title, s.revision AS source_revision,
                   s.coverage_date, s.origin AS source_origin
            FROM reference_pgns p
            JOIN reference_sources s ON s.id = p.source_id
            WHERE p.pgn = ?
            ORDER BY CASE p.origin WHEN 'j1939_base_2001' THEN 0 ELSE 1 END, p.source_id
            """,
            (pgn,),
        ).fetchall()

    def lookup_spn(self, spn: int, origin: str | None = None) -> list[sqlite3.Row]:
        if origin:
            return self.conn.execute(
                """
                SELECT sp.*, s.title AS source_title, s.revision AS source_revision,
                       s.coverage_date, s.origin AS source_origin
                FROM reference_spns sp
                JOIN reference_sources s ON s.id = sp.source_id
                WHERE sp.spn = ? AND sp.origin = ?
                """,
                (spn, origin),
            ).fetchall()
        return self.conn.execute(
            """
            SELECT sp.*, s.title AS source_title, s.revision AS source_revision,
                   s.coverage_date, s.origin AS source_origin
            FROM reference_spns sp
            JOIN reference_sources s ON s.id = sp.source_id
            WHERE sp.spn = ?
            ORDER BY CASE sp.origin WHEN 'j1939_base_2001' THEN 0 ELSE 1 END, sp.source_id
            """,
            (spn,),
        ).fetchall()

    def lookup_ddi(self, ddi: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT d.*, s.title AS source_title, s.revision AS source_revision,
                   s.coverage_date, s.origin AS source_origin
            FROM reference_ddis d
            JOIN reference_sources s ON s.id = d.source_id
            WHERE d.ddi = ?
            """,
            (ddi,),
        ).fetchall()

    def pgn_spn_mappings(self, pgn: int, source_id: int | None = None) -> list[sqlite3.Row]:
        if source_id is not None:
            return self.conn.execute(
                """
                SELECT m.*, sp.name AS spn_name
                FROM reference_pgn_spns m
                JOIN reference_pgns p ON p.id = m.pgn_id
                LEFT JOIN reference_spns sp ON sp.id = m.spn_id
                WHERE p.pgn = ? AND m.source_id = ?
                ORDER BY m.position_order, m.id
                """,
                (pgn, source_id),
            ).fetchall()
        return self.conn.execute(
            """
            SELECT m.*, sp.name AS spn_name, p.origin
            FROM reference_pgn_spns m
            JOIN reference_pgns p ON p.id = m.pgn_id
            LEFT JOIN reference_spns sp ON sp.id = m.spn_id
            WHERE p.pgn = ?
            ORDER BY p.origin, m.position_order, m.id
            """,
            (pgn,),
        ).fetchall()

    def list_sources(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM reference_sources ORDER BY imported_at DESC"
        ).fetchall()
