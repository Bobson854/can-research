"""Offline J1939 session classification and aggregation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from canresearch.core.j1939 import J1939Identifier, parse_j1939_id
from canresearch.core.j1939_logical_messages import categorize_j1939_frame
from canresearch.core.j1939_nodes import scan_session_j1939_nodes
from canresearch.core.j1939_tp import reassemble_j1939_transport
from canresearch.core.jsonl_capture_store import iter_frames_from_path
from canresearch.core.sessions import (
    CanFrame,
    SessionRecord,
    SessionStatus,
    get_session,
    resolve_session_frames_path,
)
from canresearch.references.service import ReferenceService
from canresearch.storage.database import default_db_path, initialize

ORIGIN_PRECEDENCE: tuple[str, ...] = (
    "j1939_base_2001",
    "j1939_addition",
    "isobus_addition",
)

MAX_29BIT_CAN_ID = 0x1FFFFFFF


@dataclass(frozen=True, slots=True)
class PgnReferenceMatch:
    """One reference catalogue row matching an observed PGN."""

    origin: str
    name: str | None
    acronym: str | None
    source_title: str | None


@dataclass(frozen=True, slots=True)
class ObservedTraffic:
    """Aggregated J1939 traffic for one PGN + source (+ destination for PDU1)."""

    can_id: int
    pgn: int
    priority: int
    source_address: int
    destination_address: int | None
    pdu_format: int
    is_pdu1: bool
    frame_count: int
    first_timestamp_us: int
    last_timestamp_us: int
    classification: str
    display_name: str | None
    reference_matches: tuple[PgnReferenceMatch, ...] = ()


@dataclass(frozen=True, slots=True)
class TransportedPgnSummary:
    """One completed transport-reassembled application PGN."""

    transported_pgn: int
    source_address: int
    destination_address: int
    payload_length: int
    transport_mode: str
    packet_count: int


@dataclass(frozen=True, slots=True)
class SessionAnalysisSummary:
    """Result of offline analysis for one capture session."""

    session_id: str
    session_name: str | None
    total_frames: int
    j1939_frames: int
    non_j1939_frames: int
    error_frames: int
    malformed_frames: int
    duration_s: float | None
    observed: tuple[ObservedTraffic, ...] = field(default_factory=tuple)
    transport_tp_cm_frames: int = 0
    transport_tp_dt_frames: int = 0
    transport_transfers_started: int = 0
    transport_transfers_completed: int = 0
    transport_transfers_incomplete: int = 0
    transport_transfers_aborted: int = 0
    completed_transport_pgns: tuple[TransportedPgnSummary, ...] = field(default_factory=tuple)
    transport_warning_count: int = 0
    identity_address_claim_frames: int = 0
    identity_unique_nodes: int = 0
    identity_claimed_addresses: tuple[int, ...] = field(default_factory=tuple)
    identity_address_conflicts: int = 0

    @property
    def unique_pgns(self) -> int:
        return len({item.pgn for item in self.observed})

    @property
    def unique_source_addresses(self) -> int:
        return len({item.source_address for item in self.observed})

    @property
    def known_pgn_count(self) -> int:
        return len({item.pgn for item in self.observed if item.classification != "unknown"})

    @property
    def unknown_pgn_count(self) -> int:
        return len({item.pgn for item in self.observed if item.classification == "unknown"})


@dataclass
class _AggregateBucket:
    can_id: int
    parsed: J1939Identifier
    frame_count: int = 0
    first_timestamp_us: int = 0
    last_timestamp_us: int = 0


def classify_pgn(
    pgn: int,
    service: ReferenceService,
) -> tuple[str, str | None, tuple[PgnReferenceMatch, ...]]:
    """Classify a PGN using deterministic origin precedence."""
    rows = service.lookup_pgn(pgn)
    if not rows:
        return "unknown", None, ()

    matches = tuple(
        PgnReferenceMatch(
            origin=str(row["origin"]),
            name=row["name"],
            acronym=row["acronym"],
            source_title=row["source_title"],
        )
        for row in rows
    )
    origins = {match.origin for match in matches}

    def _precedence(origin: str) -> int:
        try:
            return ORIGIN_PRECEDENCE.index(origin)
        except ValueError:
            return len(ORIGIN_PRECEDENCE)

    primary_origin = min(origins, key=_precedence)
    primary_match = next(match for match in matches if match.origin == primary_origin)
    display_name = primary_match.acronym or primary_match.name
    return primary_origin, display_name, matches


def _timestamp_to_iso(timestamp_us: int) -> str:
    return datetime.fromtimestamp(timestamp_us / 1_000_000, tz=UTC).isoformat()


def _resolve_frames_path(record: SessionRecord) -> Path:
    return resolve_session_frames_path(record)


def _categorize_frame(frame: CanFrame) -> str:
    return categorize_j1939_frame(frame)


def _aggregate_key(parsed: J1939Identifier) -> tuple[int, int, int | None]:
    return (parsed.pgn, parsed.source_address, parsed.destination_address)


class SessionAnalyzer:
    """Analyze saved JSONL capture sessions for J1939 traffic."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_db_path()

    def analyze(self, session_id: str, *, persist: bool = True) -> SessionAnalysisSummary:
        record = get_session(session_id, db_path=self.db_path)
        frames_path = _resolve_frames_path(record)
        if not frames_path.exists():
            msg = f"Frame store not found: {frames_path}"
            raise FileNotFoundError(msg)

        duration_s: float | None = None
        if record.stopped_at is not None:
            duration_s = (record.stopped_at - record.started_at).total_seconds()

        buckets: dict[tuple[int, int, int | None], _AggregateBucket] = {}
        total_frames = 0
        j1939_frames = 0
        non_j1939_frames = 0
        error_frames = 0
        malformed_frames = 0

        for frame in iter_frames_from_path(frames_path):
            total_frames += 1
            category = _categorize_frame(frame)
            if category == "error":
                error_frames += 1
                continue
            if category == "malformed":
                malformed_frames += 1
                continue
            if category == "non_j1939":
                non_j1939_frames += 1
                continue

            assert frame.can_id is not None
            try:
                parsed = parse_j1939_id(frame.can_id)
            except ValueError:
                malformed_frames += 1
                continue

            j1939_frames += 1
            key = _aggregate_key(parsed)
            bucket = buckets.get(key)
            if bucket is None:
                buckets[key] = _AggregateBucket(
                    can_id=frame.can_id,
                    parsed=parsed,
                    frame_count=1,
                    first_timestamp_us=frame.timestamp_us,
                    last_timestamp_us=frame.timestamp_us,
                )
            else:
                bucket.frame_count += 1
                bucket.first_timestamp_us = min(bucket.first_timestamp_us, frame.timestamp_us)
                bucket.last_timestamp_us = max(bucket.last_timestamp_us, frame.timestamp_us)

        conn = initialize(self.db_path)
        try:
            service = ReferenceService(conn)
            observed = self._build_observed(buckets, service, duration_s)
            if persist:
                self._persist_observed_pgns(conn, session_id, observed)
                conn.execute(
                    "UPDATE sessions SET status = ? WHERE id = ?",
                    (SessionStatus.ANALYZED.value, session_id),
                )
                conn.commit()
        finally:
            conn.close()

        transport = reassemble_j1939_transport(iter_frames_from_path(frames_path))
        node_result = scan_session_j1939_nodes(
            session_id,
            db_path=self.db_path,
            persist=persist,
        )
        claimed_addresses = tuple(
            sorted(
                {
                    obs.source_address
                    for node in node_result.nodes
                    for obs in node.observations
                    if not obs.cannot_claim
                }
            )
        )
        completed_transport = tuple(
            TransportedPgnSummary(
                transported_pgn=message.transported_pgn or message.pgn,
                source_address=message.source_address,
                destination_address=message.destination_address or 0xFF,
                payload_length=message.payload_length or len(message.payload),
                transport_mode=message.transport_mode.value if message.transport_mode else "",
                packet_count=message.packet_count or 0,
            )
            for message in transport.completed_messages
        )

        return SessionAnalysisSummary(
            session_id=session_id,
            session_name=record.name,
            total_frames=total_frames,
            j1939_frames=j1939_frames,
            non_j1939_frames=non_j1939_frames,
            error_frames=error_frames,
            malformed_frames=malformed_frames,
            duration_s=duration_s,
            observed=tuple(observed),
            transport_tp_cm_frames=transport.stats.tp_cm_frames,
            transport_tp_dt_frames=transport.stats.tp_dt_frames,
            transport_transfers_started=transport.stats.transfers_started,
            transport_transfers_completed=transport.stats.transfers_completed,
            transport_transfers_incomplete=transport.stats.transfers_incomplete,
            transport_transfers_aborted=transport.stats.transfers_aborted,
            completed_transport_pgns=completed_transport,
            transport_warning_count=len(transport.warnings),
            identity_address_claim_frames=node_result.stats.address_claim_frames,
            identity_unique_nodes=node_result.stats.unique_names,
            identity_claimed_addresses=claimed_addresses,
            identity_address_conflicts=node_result.stats.address_conflicts,
        )

    def _build_observed(
        self,
        buckets: dict[tuple[int, int, int | None], _AggregateBucket],
        service: ReferenceService,
        duration_s: float | None,
    ) -> list[ObservedTraffic]:
        observed: list[ObservedTraffic] = []
        for bucket in buckets.values():
            parsed = bucket.parsed
            classification, display_name, matches = classify_pgn(parsed.pgn, service)
            observed.append(
                ObservedTraffic(
                    can_id=bucket.can_id,
                    pgn=parsed.pgn,
                    priority=parsed.priority,
                    source_address=parsed.source_address,
                    destination_address=parsed.destination_address,
                    pdu_format=parsed.pdu_format,
                    is_pdu1=parsed.is_pdu1,
                    frame_count=bucket.frame_count,
                    first_timestamp_us=bucket.first_timestamp_us,
                    last_timestamp_us=bucket.last_timestamp_us,
                    classification=classification,
                    display_name=display_name,
                    reference_matches=matches,
                )
            )

        observed.sort(key=lambda item: (-item.frame_count, item.pgn, item.source_address))
        _ = duration_s  # rate is derived at display time from frame_count / duration_s
        return observed

    def _persist_observed_pgns(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        observed: list[ObservedTraffic],
    ) -> None:
        conn.execute("DELETE FROM observed_pgns WHERE session_id = ?", (session_id,))
        for item in observed:
            conn.execute(
                """
                INSERT INTO observed_pgns (
                    session_id, pgn, can_id, source_address, destination_address,
                    frame_count, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.pgn,
                    item.can_id,
                    item.source_address,
                    item.destination_address,
                    item.frame_count,
                    _timestamp_to_iso(item.first_timestamp_us),
                    _timestamp_to_iso(item.last_timestamp_us),
                ),
            )


def analyze_session(
    session_id: str,
    *,
    db_path: Path | None = None,
    persist: bool = True,
) -> SessionAnalysisSummary:
    """Analyze a capture session and classify observed J1939 traffic."""
    return SessionAnalyzer(db_path).analyze(session_id, persist=persist)
