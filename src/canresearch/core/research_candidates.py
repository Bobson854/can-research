"""Persisted research candidate workflow: create, review, confirm, reject."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from canresearch.core.assets import get_asset_by_key, require_session_asset_link
from canresearch.core.dbc_identifiers import sanitize_dbc_identifier
from canresearch.core.dbc_position import signal_bit_range
from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.research_frames import parse_can_id_fields
from canresearch.storage.database import connect, default_db_path, initialize

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


class CandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class CandidateClassification(StrEnum):
    SIGNAL = "signal"
    COUNTER = "counter"
    CHECKSUM = "checksum"
    RESERVED = "reserved"
    UNKNOWN = "unknown"


class ByteOrder(StrEnum):
    INTEL = "intel"
    MOTOROLA = "motorola"


class Signedness(StrEnum):
    SIGNED = "signed"
    UNSIGNED = "unsigned"
    UNKNOWN = "unknown"


class EvidenceType(StrEnum):
    WINDOW_COMPARISON = "window_comparison"
    REPEAT_CONSISTENCY = "repeat_consistency"
    COUNTER_DETECTION = "counter_detection"
    CHECKSUM_DETECTION = "checksum_detection"
    REFERENCE_CORRELATION = "reference_correlation"
    MANUAL_NOTE = "manual_note"


VALID_TRANSITIONS: dict[CandidateStatus, frozenset[CandidateStatus]] = {
    CandidateStatus.CANDIDATE: frozenset({CandidateStatus.REVIEWED, CandidateStatus.REJECTED}),
    CandidateStatus.REVIEWED: frozenset({CandidateStatus.CONFIRMED, CandidateStatus.REJECTED}),
    CandidateStatus.CONFIRMED: frozenset(),
    CandidateStatus.REJECTED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ResearchCandidateRecord:
    id: str
    asset_id: str
    asset_key: str
    origin_session_id: str | None
    can_id: int
    is_extended: bool
    pgn: int | None
    source_address: int | None
    destination_address: int | None
    start_bit: int
    bit_length: int
    byte_order: str
    signedness: str
    classification: str
    status: str
    suggested_name: str | None
    signal_name: str | None
    unit: str | None
    factor: float | None
    offset: float | None
    minimum: float | None
    maximum: float | None
    notes: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateEvidenceRecord:
    id: int
    candidate_id: str
    evidence_type: str
    evidence: dict[str, Any]
    session_id: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StatusTransitionResult:
    candidate: ResearchCandidateRecord
    from_status: str
    to_status: str


@dataclass(frozen=True, slots=True)
class ConfirmCandidateResult:
    candidate: ResearchCandidateRecord
    requested_name: str
    dbc_signal_name: str
    name_sanitized: bool


@dataclass(frozen=True, slots=True)
class OverlapConflict:
    conflicting_id: str
    conflicting_signal_name: str | None
    conflicting_start_bit: int
    conflicting_bit_length: int
    source: str


class ResearchCandidateError(Exception):
    """Structured failure for candidate workflow operations."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _row_to_candidate(row: sqlite3.Row) -> ResearchCandidateRecord:
    return ResearchCandidateRecord(
        id=row["id"],
        asset_id=row["asset_id"],
        asset_key=row["asset_key"],
        origin_session_id=row["origin_session_id"],
        can_id=row["can_id"],
        is_extended=bool(row["is_extended"]),
        pgn=row["pgn"],
        source_address=row["source_address"],
        destination_address=row["destination_address"],
        start_bit=row["start_bit"],
        bit_length=row["bit_length"],
        byte_order=row["byte_order"],
        signedness=row["signedness"],
        classification=row["classification"],
        status=row["status"],
        suggested_name=row["suggested_name"],
        signal_name=row["signal_name"],
        unit=row["unit"],
        factor=row["factor"],
        offset=row["offset"],
        minimum=row["minimum"],
        maximum=row["maximum"],
        notes=row["notes"],
        confirmed_at=_parse_dt(row["confirmed_at"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _candidate_select() -> str:
    return """
        SELECT
            rc.*,
            a.asset_key
        FROM research_candidates rc
        JOIN assets a ON a.id = rc.asset_id
    """


def _get_candidate_row(
    conn: sqlite3.Connection,
    candidate_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        _candidate_select() + " WHERE rc.id = ?",
        (candidate_id,),
    ).fetchone()


def _load_candidate(conn: sqlite3.Connection, candidate_id: str) -> ResearchCandidateRecord:
    row = _get_candidate_row(conn, candidate_id)
    if row is None:
        raise ResearchCandidateError(
            "candidate_not_found",
            f"Research candidate {candidate_id!r} not found",
        )
    return _row_to_candidate(row)


def _validate_byte_order(byte_order: str) -> str:
    value = byte_order.strip().lower()
    if value not in ByteOrder:
        msg = f"byte_order must be 'intel' or 'motorola', got {byte_order!r}"
        raise ValueError(msg)
    return value


def _validate_signedness(signedness: str) -> str:
    value = signedness.strip().lower()
    if value not in Signedness:
        msg = f"signedness must be 'signed', 'unsigned', or 'unknown', got {signedness!r}"
        raise ValueError(msg)
    return value


def _validate_classification(classification: str) -> str:
    value = classification.strip().lower()
    if value not in CandidateClassification:
        msg = (
            "classification must be one of signal, counter, checksum, reserved, unknown: "
            f"{classification!r}"
        )
        raise ValueError(msg)
    return value


def _validate_evidence_type(evidence_type: str) -> str:
    value = evidence_type.strip().lower()
    if value not in EvidenceType:
        msg = f"unsupported evidence_type: {evidence_type!r}"
        raise ValueError(msg)
    return value


def _infer_j1939_fields(can_id: int, *, is_extended: bool) -> dict[str, int | None]:
    fields = parse_can_id_fields(can_id, is_extended=is_extended)
    return {
        "pgn": fields.get("pgn"),
        "source_address": fields.get("source_address"),
        "destination_address": fields.get("destination_address"),
    }


def _bit_ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _collect_overlap_conflicts(
    conn: sqlite3.Connection,
    *,
    asset_id: str,
    can_id: int,
    start_bit: int,
    bit_length: int,
    exclude_candidate_id: str | None = None,
    standard_ranges: list[tuple[tuple[int, int], str]] | None = None,
) -> list[OverlapConflict]:
    candidate_range = signal_bit_range(start_bit, bit_length)
    conflicts: list[OverlapConflict] = []

    rows = conn.execute(
        """
        SELECT id, signal_name, start_bit, bit_length
        FROM research_candidates
        WHERE asset_id = ? AND can_id = ? AND status = ?
          AND id != COALESCE(?, '')
        """,
        (asset_id, can_id, CandidateStatus.CONFIRMED.value, exclude_candidate_id),
    ).fetchall()
    for row in rows:
        other_range = signal_bit_range(row["start_bit"], row["bit_length"])
        if _bit_ranges_overlap(candidate_range, other_range):
            conflicts.append(
                OverlapConflict(
                    conflicting_id=row["id"],
                    conflicting_signal_name=row["signal_name"],
                    conflicting_start_bit=row["start_bit"],
                    conflicting_bit_length=row["bit_length"],
                    source="confirmed_research",
                )
            )

    for bit_range, label in standard_ranges or []:
        if _bit_ranges_overlap(candidate_range, bit_range):
            conflicts.append(
                OverlapConflict(
                    conflicting_id=label,
                    conflicting_signal_name=label,
                    conflicting_start_bit=bit_range[0],
                    conflicting_bit_length=bit_range[1] - bit_range[0],
                    source="reference_standard",
                )
            )

    return conflicts


def load_standard_signal_ranges_for_can_id(
    can_id: int,
    *,
    is_extended: bool,
    db_path: Path | None = None,
) -> list[tuple[tuple[int, int], str]]:
    """Return reference-backed DBC bit ranges for overlap checks (best effort)."""
    if not is_extended or can_id > 0x1FFFFFFF:
        return []

    try:
        parsed = parse_j1939_id(can_id)
    except ValueError:
        return []

    from canresearch.core.dbc_generation import _build_signals  # noqa: PLC0415
    from canresearch.core.j1939_mappings import load_pgn_mapping_specs  # noqa: PLC0415
    from canresearch.core.session_decode import J1939_ORIGINS  # noqa: PLC0415
    from canresearch.references.service import ReferenceService  # noqa: PLC0415

    path = db_path or default_db_path()
    conn = connect(path)
    try:
        service = ReferenceService(conn)
        ranges: list[tuple[tuple[int, int], str]] = []

        for origin in J1939_ORIGINS:
            specs, _ = load_pgn_mapping_specs(service, parsed.pgn, origin)
            if not specs:
                continue
            signals, _, _, _ = _build_signals(specs, pgn=parsed.pgn, can_id=can_id)
            for signal in signals:
                ranges.append((signal_bit_range(signal.start_bit, signal.bit_length), signal.name))
            break

        return ranges
    finally:
        conn.close()


def create_research_candidate(
    *,
    asset_key: str,
    session_id: str,
    can_id: int,
    start_bit: int,
    bit_length: int,
    byte_order: str,
    signedness: str = Signedness.UNKNOWN.value,
    is_extended: bool | None = None,
    classification: str = CandidateClassification.UNKNOWN.value,
    suggested_name: str | None = None,
    unit: str | None = None,
    factor: float | None = None,
    offset: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> ResearchCandidateRecord:
    """Persist a new research candidate in candidate status."""
    path = db_path or default_db_path()
    initialize(path)

    asset = get_asset_by_key(asset_key, db_path=path)
    require_session_asset_link(session_id, asset_key, db_path=path)

    if start_bit < 0 or bit_length <= 0:
        raise ResearchCandidateError(
            "invalid_field_definition",
            "start_bit must be >= 0 and bit_length must be > 0",
        )

    byte_order_value = _validate_byte_order(byte_order)
    signedness_value = _validate_signedness(signedness)
    classification_value = _validate_classification(classification)

    extended = is_extended if is_extended is not None else can_id > 0x7FF
    j1939_fields = _infer_j1939_fields(can_id, is_extended=extended)

    candidate_id = str(uuid.uuid4())
    now = _now_iso()
    conn = connect(path)
    try:
        conn.execute(
            """
            INSERT INTO research_candidates (
                id, asset_id, origin_session_id, can_id, is_extended,
                pgn, source_address, destination_address,
                start_bit, bit_length, byte_order, signedness, classification,
                status, suggested_name, unit, factor, offset, minimum, maximum,
                notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                asset.id,
                session_id,
                can_id,
                1 if extended else 0,
                j1939_fields["pgn"],
                j1939_fields["source_address"],
                j1939_fields["destination_address"],
                start_bit,
                bit_length,
                byte_order_value,
                signedness_value,
                classification_value,
                CandidateStatus.CANDIDATE.value,
                suggested_name,
                unit,
                factor,
                offset,
                minimum,
                maximum,
                notes,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO research_candidate_status_history
                (candidate_id, from_status, to_status, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (candidate_id, "", CandidateStatus.CANDIDATE.value, "created", now),
        )
        conn.commit()
        return _load_candidate(conn, candidate_id)
    finally:
        conn.close()


def list_research_candidates(
    *,
    asset_key: str | None = None,
    status: str | None = None,
    session_id: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    db_path: Path | None = None,
) -> list[ResearchCandidateRecord]:
    path = db_path or default_db_path()
    initialize(path)
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ResearchCandidateError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_LIST_LIMIT}, got {limit}",
        )

    clauses: list[str] = []
    params: list[Any] = []
    if asset_key is not None:
        asset = get_asset_by_key(asset_key, db_path=path)
        clauses.append("rc.asset_id = ?")
        params.append(asset.id)
    if status is not None:
        value = status.strip().lower()
        if value not in CandidateStatus:
            raise ResearchCandidateError("invalid_status", f"Unknown status: {status!r}")
        clauses.append("rc.status = ?")
        params.append(value)
    if session_id is not None:
        clauses.append("rc.origin_session_id = ?")
        params.append(session_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        _candidate_select()
        + f" {where} ORDER BY rc.created_at DESC, rc.id LIMIT ?"
    )
    params.append(limit)

    conn = connect(path)
    try:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_candidate(row) for row in rows]
    finally:
        conn.close()


def get_research_candidate(
    candidate_id: str,
    *,
    db_path: Path | None = None,
) -> ResearchCandidateRecord:
    path = db_path or default_db_path()
    initialize(path)
    conn = connect(path)
    try:
        return _load_candidate(conn, candidate_id)
    finally:
        conn.close()


def add_candidate_evidence(
    candidate_id: str,
    *,
    evidence_type: str,
    evidence: dict[str, Any],
    session_id: str | None = None,
    db_path: Path | None = None,
) -> CandidateEvidenceRecord:
    path = db_path or default_db_path()
    initialize(path)
    evidence_type_value = _validate_evidence_type(evidence_type)

    conn = connect(path)
    try:
        _load_candidate(conn, candidate_id)
        if session_id is not None:
            row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise ResearchCandidateError(
                    "session_not_found",
                    f"Session {session_id!r} not found",
                )

        cursor = conn.execute(
            """
            INSERT INTO research_candidate_evidence
                (candidate_id, evidence_type, evidence_json, session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                evidence_type_value,
                json.dumps(evidence, sort_keys=True),
                session_id,
                _now_iso(),
            ),
        )
        conn.commit()
        evidence_id = int(cursor.lastrowid)
        row = conn.execute(
            """
            SELECT id, candidate_id, evidence_type, evidence_json, session_id, created_at
            FROM research_candidate_evidence WHERE id = ?
            """,
            (evidence_id,),
        ).fetchone()
        assert row is not None
        return CandidateEvidenceRecord(
            id=row["id"],
            candidate_id=row["candidate_id"],
            evidence_type=row["evidence_type"],
            evidence=json.loads(row["evidence_json"]),
            session_id=row["session_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    finally:
        conn.close()


def list_candidate_evidence(
    candidate_id: str,
    *,
    limit: int = DEFAULT_LIST_LIMIT,
    db_path: Path | None = None,
) -> list[CandidateEvidenceRecord]:
    path = db_path or default_db_path()
    initialize(path)
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ResearchCandidateError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_LIST_LIMIT}, got {limit}",
        )

    conn = connect(path)
    try:
        _load_candidate(conn, candidate_id)
        rows = conn.execute(
            """
            SELECT id, candidate_id, evidence_type, evidence_json, session_id, created_at
            FROM research_candidate_evidence
            WHERE candidate_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (candidate_id, limit),
        ).fetchall()
        return [
            CandidateEvidenceRecord(
                id=row["id"],
                candidate_id=row["candidate_id"],
                evidence_type=row["evidence_type"],
                evidence=json.loads(row["evidence_json"]),
                session_id=row["session_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def _transition_status(
    candidate_id: str,
    *,
    to_status: CandidateStatus,
    notes: str | None = None,
    db_path: Path | None = None,
) -> StatusTransitionResult:
    path = db_path or default_db_path()
    initialize(path)
    conn = connect(path)
    try:
        candidate = _load_candidate(conn, candidate_id)
        current = CandidateStatus(candidate.status)
        allowed = VALID_TRANSITIONS.get(current, frozenset())
        if to_status not in allowed:
            raise ResearchCandidateError(
                "invalid_status_transition",
                f"Cannot transition from {current.value!r} to {to_status.value!r}",
                details={"from_status": current.value, "to_status": to_status.value},
            )

        now = _now_iso()
        conn.execute(
            """
            UPDATE research_candidates
            SET status = ?, notes = COALESCE(?, notes), updated_at = ?
            WHERE id = ?
            """,
            (to_status.value, notes, now, candidate_id),
        )
        conn.execute(
            """
            INSERT INTO research_candidate_status_history
                (candidate_id, from_status, to_status, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (candidate_id, current.value, to_status.value, notes, now),
        )
        conn.commit()
        updated = _load_candidate(conn, candidate_id)
        return StatusTransitionResult(
            candidate=updated,
            from_status=current.value,
            to_status=to_status.value,
        )
    finally:
        conn.close()


def mark_candidate_reviewed(
    candidate_id: str,
    *,
    notes: str | None = None,
    db_path: Path | None = None,
) -> StatusTransitionResult:
    return _transition_status(
        candidate_id,
        to_status=CandidateStatus.REVIEWED,
        notes=notes,
        db_path=db_path,
    )


def reject_candidate(
    candidate_id: str,
    *,
    notes: str | None = None,
    db_path: Path | None = None,
) -> StatusTransitionResult:
    path = db_path or default_db_path()
    initialize(path)
    conn = connect(path)
    try:
        candidate = _load_candidate(conn, candidate_id)
        current = CandidateStatus(candidate.status)
        if current not in {CandidateStatus.CANDIDATE, CandidateStatus.REVIEWED}:
            raise ResearchCandidateError(
                "invalid_status_transition",
                f"Cannot reject candidate in status {current.value!r}",
            )
    finally:
        conn.close()
    return _transition_status(
        candidate_id,
        to_status=CandidateStatus.REJECTED,
        notes=notes,
        db_path=db_path,
    )


def _derive_min_max(
    *,
    signed: bool,
    bit_length: int,
    minimum: float | None,
    maximum: float | None,
    factor: float,
    offset: float,
) -> tuple[float, float]:
    if minimum is not None and maximum is not None:
        return minimum, maximum

    raw_max = (1 << bit_length) - 1
    if signed:
        raw_min = -(1 << (bit_length - 1))
        raw_max = (1 << (bit_length - 1)) - 1
    else:
        raw_min = 0

    return raw_min * factor + offset, raw_max * factor + offset


def confirm_candidate(
    candidate_id: str,
    *,
    name: str,
    factor: float,
    offset: float,
    signedness: str | None = None,
    unit: str | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    classification: str | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> ConfirmCandidateResult:
    """Confirm a reviewed candidate after metadata and overlap validation."""
    path = db_path or default_db_path()
    initialize(path)

    if not name.strip():
        raise ResearchCandidateError("candidate_not_ready", "signal name is required")

    conn = connect(path)
    try:
        candidate = _load_candidate(conn, candidate_id)
        if candidate.status != CandidateStatus.REVIEWED.value:
            raise ResearchCandidateError(
                "invalid_status_transition",
                "Candidate must be reviewed before confirmation",
                details={"status": candidate.status},
            )

        signedness_value = _validate_signedness(signedness or candidate.signedness)
        if signedness_value == Signedness.UNKNOWN.value:
            raise ResearchCandidateError(
                "candidate_not_ready",
                "signedness must be explicit (signed or unsigned) before confirmation",
            )

        classification_value = (
            _validate_classification(classification)
            if classification is not None
            else candidate.classification
        )

        requested_name = name.strip()
        dbc_signal_name = sanitize_dbc_identifier(requested_name)
        name_sanitized = requested_name != dbc_signal_name

        standard_ranges = load_standard_signal_ranges_for_can_id(
            candidate.can_id,
            is_extended=candidate.is_extended,
            db_path=path,
        )
        conflicts = _collect_overlap_conflicts(
            conn,
            asset_id=candidate.asset_id,
            can_id=candidate.can_id,
            start_bit=candidate.start_bit,
            bit_length=candidate.bit_length,
            exclude_candidate_id=candidate_id,
            standard_ranges=standard_ranges,
        )
        if conflicts:
            raise ResearchCandidateError(
                "signal_overlap",
                "Candidate field overlaps an existing confirmed or reference-backed signal",
                details={
                    "conflicts": [
                        {
                            "id": c.conflicting_id,
                            "signal_name": c.conflicting_signal_name,
                            "start_bit": c.conflicting_start_bit,
                            "bit_length": c.conflicting_bit_length,
                            "source": c.source,
                        }
                        for c in conflicts
                    ]
                },
            )

        duplicate_name = conn.execute(
            """
            SELECT id FROM research_candidates
            WHERE asset_id = ? AND can_id = ? AND status = ?
              AND signal_name = ? AND id != ?
            """,
            (
                candidate.asset_id,
                candidate.can_id,
                CandidateStatus.CONFIRMED.value,
                dbc_signal_name,
                candidate_id,
            ),
        ).fetchone()
        if duplicate_name is not None:
            raise ResearchCandidateError(
                "duplicate_signal_name",
                f"Signal name {dbc_signal_name!r} already confirmed on this CAN ID",
                details={"conflicting_id": duplicate_name["id"]},
            )

        signed = signedness_value == Signedness.SIGNED.value
        min_val, max_val = _derive_min_max(
            signed=signed,
            bit_length=candidate.bit_length,
            minimum=minimum if minimum is not None else candidate.minimum,
            maximum=maximum if maximum is not None else candidate.maximum,
            factor=factor,
            offset=offset,
        )

        now = _now_iso()
        conn.execute(
            """
            UPDATE research_candidates
            SET status = ?, signal_name = ?, signedness = ?, classification = ?,
                unit = ?, factor = ?, offset = ?, minimum = ?, maximum = ?,
                notes = COALESCE(?, notes), confirmed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                CandidateStatus.CONFIRMED.value,
                dbc_signal_name,
                signedness_value,
                classification_value,
                unit if unit is not None else candidate.unit,
                factor,
                offset,
                min_val,
                max_val,
                notes,
                now,
                now,
                candidate_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO research_candidate_status_history
                (candidate_id, from_status, to_status, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                CandidateStatus.REVIEWED.value,
                CandidateStatus.CONFIRMED.value,
                notes,
                now,
            ),
        )
        conn.commit()
        updated = _load_candidate(conn, candidate_id)
        return ConfirmCandidateResult(
            candidate=updated,
            requested_name=requested_name,
            dbc_signal_name=dbc_signal_name,
            name_sanitized=name_sanitized,
        )
    finally:
        conn.close()


def candidate_to_dict(record: ResearchCandidateRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "asset_id": record.asset_id,
        "asset_key": record.asset_key,
        "origin_session_id": record.origin_session_id,
        "can_id": record.can_id,
        "can_id_hex": f"0x{record.can_id:X}",
        "is_extended": record.is_extended,
        "pgn": record.pgn,
        "source_address": record.source_address,
        "destination_address": record.destination_address,
        "start_bit": record.start_bit,
        "bit_length": record.bit_length,
        "byte_order": record.byte_order,
        "signedness": record.signedness,
        "classification": record.classification,
        "status": record.status,
        "suggested_name": record.suggested_name,
        "signal_name": record.signal_name,
        "unit": record.unit,
        "factor": record.factor,
        "offset": record.offset,
        "minimum": record.minimum,
        "maximum": record.maximum,
        "notes": record.notes,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
