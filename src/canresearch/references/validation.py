"""Reference catalogue validation."""

from __future__ import annotations

import sqlite3

from canresearch.references.models import IssueSeverity, ValidationIssue, ValidationReport


def validate_reference_catalogue(conn: sqlite3.Connection) -> ValidationReport:
    """Validate imported reference data without modifying records."""
    report = ValidationReport()

    _check_duplicate_pgns(conn, report)
    _check_duplicate_spns(conn, report)
    _check_duplicate_ddis(conn, report)
    _check_missing_spn_targets(conn, report)
    _check_bit_positions(conn, report)
    _check_payload_length(conn, report)
    _check_numeric_identifiers(conn, report)
    _check_duplicate_mappings(conn, report)
    _check_overlapping_signals(conn, report)
    _check_provenance(conn, report)

    return report


def _add(
    report: ValidationReport,
    severity: IssueSeverity,
    category: str,
    message: str,
    *,
    pgn: int | None = None,
    spn: int | None = None,
    ddi: int | None = None,
    source_id: int | None = None,
) -> None:
    report.issues.append(
        ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            pgn=pgn,
            spn=spn,
            ddi=ddi,
            source_id=source_id,
        )
    )


def _check_duplicate_pgns(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT source_id, pgn, COUNT(*) AS c
        FROM reference_pgns GROUP BY source_id, pgn HAVING c > 1
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.ERROR,
            "duplicate_pgn",
            f"Duplicate PGN {row['pgn']} within source_id {row['source_id']}",
            pgn=row["pgn"],
            source_id=row["source_id"],
        )


def _check_duplicate_spns(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT source_id, spn, COUNT(*) AS c
        FROM reference_spns GROUP BY source_id, spn HAVING c > 1
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.ERROR,
            "duplicate_spn",
            f"Duplicate SPN {row['spn']} within source_id {row['source_id']}",
            spn=row["spn"],
            source_id=row["source_id"],
        )


def _check_duplicate_ddis(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT source_id, ddi, COUNT(*) AS c
        FROM reference_ddis GROUP BY source_id, ddi HAVING c > 1
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.ERROR,
            "duplicate_ddi",
            f"Duplicate DDI {row['ddi']} within source_id {row['source_id']}",
            ddi=row["ddi"],
            source_id=row["source_id"],
        )


def _check_missing_spn_targets(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT m.source_id, p.pgn, m.spn
        FROM reference_pgn_spns m
        JOIN reference_pgns p ON p.id = m.pgn_id
        LEFT JOIN reference_spns sp ON sp.source_id = m.source_id AND sp.spn = m.spn
        WHERE sp.id IS NULL
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.WARNING,
            "missing_spn",
            f"PGN {row['pgn']} maps to SPN {row['spn']} not present in same source",
            pgn=row["pgn"],
            spn=row["spn"],
            source_id=row["source_id"],
        )


def _check_bit_positions(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT p.pgn, m.spn, m.start_byte, m.start_bit, m.bit_length,
               m.source_id, p.payload_length
        FROM reference_pgn_spns m
        JOIN reference_pgns p ON p.id = m.pgn_id
        WHERE m.start_byte IS NOT NULL
        """
    ).fetchall()
    for row in rows:
        payload = row["payload_length"]
        start_byte = row["start_byte"]
        if payload is not None and start_byte > payload:
            _add(
                report,
                IssueSeverity.ERROR,
                "invalid_bit_position",
                f"PGN {row['pgn']} SPN {row['spn']} start_byte {start_byte} exceeds payload {payload}",
                pgn=row["pgn"],
                spn=row["spn"],
                source_id=row["source_id"],
            )
        elif start_byte > 8:
            _add(
                report,
                IssueSeverity.WARNING,
                "invalid_bit_position",
                f"PGN {row['pgn']} SPN {row['spn']} start_byte {start_byte} exceeds 8-byte PDU",
                pgn=row["pgn"],
                spn=row["spn"],
                source_id=row["source_id"],
            )

    rows = conn.execute(
        """
        SELECT p.pgn, m.spn, m.start_bit, m.source_id
        FROM reference_pgn_spns m
        JOIN reference_pgns p ON p.id = m.pgn_id
        WHERE m.start_bit IS NOT NULL AND (m.start_bit < 1 OR m.start_bit > 8)
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.ERROR,
            "invalid_bit_position",
            f"PGN {row['pgn']} SPN {row['spn']} has invalid start_bit {row['start_bit']}",
            pgn=row["pgn"],
            spn=row["spn"],
            source_id=row["source_id"],
        )


def _check_payload_length(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT p.pgn, p.payload_length, m.spn, m.start_byte, m.bit_length, m.source_id
        FROM reference_pgn_spns m
        JOIN reference_pgns p ON p.id = m.pgn_id
        WHERE p.payload_length IS NOT NULL AND m.start_byte IS NOT NULL
          AND m.start_byte > p.payload_length
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.ERROR,
            "signal_exceeds_payload",
            f"PGN {row['pgn']} SPN {row['spn']} start_byte {row['start_byte']} exceeds payload {row['payload_length']}",
            pgn=row["pgn"],
            spn=row["spn"],
            source_id=row["source_id"],
        )


def _check_numeric_identifiers(conn: sqlite3.Connection, report: ValidationReport) -> None:
    for table, col in [("reference_pgns", "pgn"), ("reference_spns", "spn"), ("reference_ddis", "ddi")]:
        rows = conn.execute(
            f"SELECT id, {col}, source_id FROM {table} WHERE {col} < 0"  # noqa: S608
        ).fetchall()
        for row in rows:
            _add(
                report,
                IssueSeverity.ERROR,
                "invalid_identifier",
                f"{table} row id={row['id']} has invalid {col}={row[col]}",
                pgn=row[col] if col == "pgn" else None,
                spn=row[col] if col == "spn" else None,
                ddi=row[col] if col == "ddi" else None,
                source_id=row["source_id"],
            )


def _check_duplicate_mappings(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT source_id, pgn_id, spn, raw_position_text, COUNT(*) AS c
        FROM reference_pgn_spns
        GROUP BY source_id, pgn_id, spn, raw_position_text
        HAVING c > 1
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.WARNING,
            "duplicate_mapping",
            f"Duplicate mapping for pgn_id={row['pgn_id']} spn={row['spn']}",
            spn=row["spn"],
            source_id=row["source_id"],
        )


def _check_overlapping_signals(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT p.pgn, m1.spn AS spn1, m2.spn AS spn2, m1.start_byte, m1.start_bit,
               m1.bit_length, m1.source_id
        FROM reference_pgn_spns m1
        JOIN reference_pgn_spns m2
          ON m1.pgn_id = m2.pgn_id AND m1.source_id = m2.source_id AND m1.id < m2.id
        JOIN reference_pgns p ON p.id = m1.pgn_id
        WHERE m1.start_byte IS NOT NULL AND m2.start_byte IS NOT NULL
          AND m1.start_byte = m2.start_byte
          AND m1.start_bit IS NOT NULL AND m2.start_bit IS NOT NULL
          AND m1.bit_length IS NOT NULL AND m2.bit_length IS NOT NULL
          AND m1.start_bit = m2.start_bit AND m1.bit_length = m2.bit_length
        LIMIT 100
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.INFO,
            "overlapping_signal",
            f"PGN {row['pgn']} has potentially overlapping mappings for SPN {row['spn1']} and {row['spn2']}",
            pgn=row["pgn"],
            source_id=row["source_id"],
        )


def _check_provenance(conn: sqlite3.Connection, report: ValidationReport) -> None:
    rows = conn.execute(
        """
        SELECT id, pgn, source_id FROM reference_pgns
        WHERE origin IS NULL OR origin = ''
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.ERROR,
            "provenance",
            f"PGN {row['pgn']} missing origin",
            pgn=row["pgn"],
            source_id=row["source_id"],
        )

    rows = conn.execute(
        """
        SELECT id, name, source_id FROM reference_pgns
        WHERE name IS NULL OR trim(name) = ''
        """
    ).fetchall()
    for row in rows:
        _add(
            report,
            IssueSeverity.WARNING,
            "missing_field",
            f"PGN id={row['id']} missing name",
            source_id=row["source_id"],
        )
