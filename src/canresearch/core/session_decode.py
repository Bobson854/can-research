"""Offline J1939 SPN value decoding for known standard PGNs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from canresearch.core.analysis import _categorize_frame, _resolve_frames_path, classify_pgn
from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.jsonl_capture_store import iter_frames_from_path
from canresearch.core.sessions import get_session
from canresearch.core.spn_bits import extract_raw_value, normalize_byte_order
from canresearch.core.spn_scaling import parse_scaling
from canresearch.references.service import ReferenceService
from canresearch.storage.database import default_db_path, initialize

TRANSPORT_PGNS: frozenset[int] = frozenset({59392, 60160, 60415, 60416})
J1939_ORIGINS: frozenset[str] = frozenset({"j1939_base_2001", "j1939_addition"})


@dataclass(frozen=True, slots=True)
class DecodeWarning:
    category: str
    message: str
    pgn: int | None = None
    spn: int | None = None
    timestamp_us: int | None = None


@dataclass(frozen=True, slots=True)
class DecodedSignal:
    timestamp_us: int
    can_id: int
    pgn: int
    source_address: int
    destination_address: int | None
    spn: int
    spn_name: str | None
    raw_value: int
    engineering_value: float | None
    unit: str | None
    origin: str
    status: str


@dataclass(frozen=True, slots=True)
class SessionDecodeSummary:
    session_id: str
    session_name: str | None
    total_frames: int
    j1939_frames: int
    known_pgn_frames: int
    unknown_pgn_frames: int
    skipped_non_j1939: int
    decoded_signals: tuple[DecodedSignal, ...] = field(default_factory=tuple)
    warnings: tuple[DecodeWarning, ...] = field(default_factory=tuple)

    @property
    def decoded_signal_count(self) -> int:
        return len(self.decoded_signals)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


@dataclass(frozen=True, slots=True)
class _MappingSpec:
    spn: int
    spn_name: str | None
    start_byte: int
    start_bit: int | None
    bit_length: int
    byte_order: str
    signed: bool
    factor: float
    offset: float
    unit: str | None
    origin: str
    source_id: int
    raw_position_text: str | None


def infer_signed(data_type: str | None) -> bool | None:
    if not data_type:
        return False
    lowered = data_type.lower()
    if "signed" in lowered:
        return True
    if lowered in {"measured", "status", "identifier", "binary"}:
        return False
    return None


def decode_session(
    session_id: str,
    *,
    db_path: Path | None = None,
    pgn_filter: int | None = None,
    spn_filter: int | None = None,
    limit: int | None = None,
) -> SessionDecodeSummary:
    """Decode SPN values for known standard J1939 PGNs in a saved session."""
    return SessionDecoder(db_path).decode(
        session_id,
        pgn_filter=pgn_filter,
        spn_filter=spn_filter,
        limit=limit,
    )


class SessionDecoder:
    """Decode SPN engineering values from saved JSONL capture sessions."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_db_path()

    def decode(
        self,
        session_id: str,
        *,
        pgn_filter: int | None = None,
        spn_filter: int | None = None,
        limit: int | None = None,
    ) -> SessionDecodeSummary:
        record = get_session(session_id, db_path=self.db_path)
        frames_path = _resolve_frames_path(record)
        if not frames_path.exists():
            msg = f"Frame store not found: {frames_path}"
            raise FileNotFoundError(msg)

        conn = initialize(self.db_path)
        try:
            service = ReferenceService(conn)
            return self._decode_frames(
                session_id=session_id,
                session_name=record.name,
                frames_path=frames_path,
                service=service,
                pgn_filter=pgn_filter,
                spn_filter=spn_filter,
                limit=limit,
            )
        finally:
            conn.close()

    def _decode_frames(
        self,
        *,
        session_id: str,
        session_name: str | None,
        frames_path: Path,
        service: ReferenceService,
        pgn_filter: int | None,
        spn_filter: int | None,
        limit: int | None,
    ) -> SessionDecodeSummary:
        _ = session_id
        total_frames = 0
        j1939_frames = 0
        known_pgn_frames = 0
        unknown_pgn_frames = 0
        skipped_non_j1939 = 0
        decoded: list[DecodedSignal] = []
        warnings: list[DecodeWarning] = []
        mapping_cache: dict[tuple[int, str], tuple[_MappingSpec, ...] | None] = {}

        for frame in iter_frames_from_path(frames_path):
            total_frames += 1
            category = _categorize_frame(frame)
            if category != "j1939":
                if category in {"non_j1939", "error", "malformed"}:
                    skipped_non_j1939 += 1
                continue

            assert frame.can_id is not None
            try:
                parsed = parse_j1939_id(frame.can_id)
            except ValueError:
                skipped_non_j1939 += 1
                continue

            j1939_frames += 1
            if pgn_filter is not None and parsed.pgn != pgn_filter:
                continue

            classification, _, _ = classify_pgn(parsed.pgn, service)
            if classification == "unknown" or classification not in J1939_ORIGINS:
                unknown_pgn_frames += 1
                continue

            known_pgn_frames += 1

            if parsed.pgn in TRANSPORT_PGNS:
                warnings.append(
                    DecodeWarning(
                        category="transport_unsupported",
                        message="Transport-protocol PGN; single-frame decode not supported",
                        pgn=parsed.pgn,
                        timestamp_us=frame.timestamp_us,
                    )
                )
                continue

            cache_key = (parsed.pgn, classification)
            if cache_key not in mapping_cache:
                mapping_cache[cache_key] = self._load_mapping_specs(
                    service,
                    parsed.pgn,
                    classification,
                    warnings,
                )
            specs = mapping_cache[cache_key]
            if not specs:
                continue

            payload = frame.data
            if frame.dlc is not None and len(payload) > frame.dlc:
                payload = payload[: frame.dlc]

            used_ranges: set[tuple[int, int]] = set()
            for spec in specs:
                if spn_filter is not None and spec.spn != spn_filter:
                    continue
                range_key = (spec.start_byte, spec.start_bit, spec.bit_length)
                if range_key in used_ranges:
                    warnings.append(
                        DecodeWarning(
                            category="overlapping_mapping",
                            message=f"Skipping duplicate bit mapping for SPN {spec.spn}",
                            pgn=parsed.pgn,
                            spn=spec.spn,
                            timestamp_us=frame.timestamp_us,
                        )
                    )
                    continue

                try:
                    raw_value = extract_raw_value(
                        payload,
                        start_byte=spec.start_byte,
                        start_bit=spec.start_bit,
                        bit_length=spec.bit_length,
                        byte_order=spec.byte_order,
                        signed=spec.signed,
                    )
                except ValueError as exc:
                    warnings.append(
                        DecodeWarning(
                            category="extract_failed",
                            message=str(exc),
                            pgn=parsed.pgn,
                            spn=spec.spn,
                            timestamp_us=frame.timestamp_us,
                        )
                    )
                    continue

                engineering_value = raw_value * spec.factor + spec.offset
                decoded.append(
                    DecodedSignal(
                        timestamp_us=frame.timestamp_us,
                        can_id=frame.can_id,
                        pgn=parsed.pgn,
                        source_address=parsed.source_address,
                        destination_address=parsed.destination_address,
                        spn=spec.spn,
                        spn_name=spec.spn_name,
                        raw_value=raw_value,
                        engineering_value=engineering_value,
                        unit=spec.unit,
                        origin=spec.origin,
                        status="ok",
                    )
                )
                used_ranges.add(range_key)

                if limit is not None and len(decoded) >= limit:
                    return SessionDecodeSummary(
                        session_id=session_id,
                        session_name=session_name,
                        total_frames=total_frames,
                        j1939_frames=j1939_frames,
                        known_pgn_frames=known_pgn_frames,
                        unknown_pgn_frames=unknown_pgn_frames,
                        skipped_non_j1939=skipped_non_j1939,
                        decoded_signals=tuple(decoded),
                        warnings=tuple(warnings),
                    )

        return SessionDecodeSummary(
            session_id=session_id,
            session_name=session_name,
            total_frames=total_frames,
            j1939_frames=j1939_frames,
            known_pgn_frames=known_pgn_frames,
            unknown_pgn_frames=unknown_pgn_frames,
            skipped_non_j1939=skipped_non_j1939,
            decoded_signals=tuple(decoded),
            warnings=tuple(warnings),
        )

    def _load_mapping_specs(
        self,
        service: ReferenceService,
        pgn: int,
        origin: str,
        warnings: list[DecodeWarning],
    ) -> tuple[_MappingSpec, ...] | None:
        rows = service.pgn_decode_mappings(pgn, origin)
        if not rows:
            warnings.append(
                DecodeWarning(
                    category="missing_mappings",
                    message=f"No PGN-SPN mappings for known PGN {pgn} ({origin})",
                    pgn=pgn,
                )
            )
            return None

        specs: list[_MappingSpec] = []
        for row in rows:
            spec, warning = self._row_to_spec(row, pgn)
            if warning:
                warnings.append(warning)
                continue
            if spec is not None:
                specs.append(spec)

        if not specs:
            return None
        return tuple(specs)

    def _row_to_spec(self, row, pgn: int) -> tuple[_MappingSpec | None, DecodeWarning | None]:
        spn = int(row["spn"])
        start_byte = row["start_byte"]
        bit_length = row["bit_length"]
        if start_byte is None or bit_length is None:
            return None, DecodeWarning(
                category="incomplete_mapping",
                message=f"SPN {spn} missing start_byte or bit_length",
                pgn=pgn,
                spn=spn,
            )

        byte_order = normalize_byte_order(row["byte_order"], default_intel=True)
        if byte_order is None:
            return None, DecodeWarning(
                category="unknown_byte_order",
                message=f"SPN {spn} byte order is unknown",
                pgn=pgn,
                spn=spn,
            )

        signedness = infer_signed(row["data_type"])
        if signedness is None:
            return None, DecodeWarning(
                category="unknown_signedness",
                message=f"SPN {spn} signedness cannot be determined from data_type",
                pgn=pgn,
                spn=spn,
            )

        factor, offset, unit, scale_error = parse_scaling(
            row["resolution"],
            row["offset"],
            row["unit"],
        )
        if factor is None:
            return None, DecodeWarning(
                category="missing_scaling",
                message=scale_error or f"SPN {spn} scaling unavailable",
                pgn=pgn,
                spn=spn,
            )

        start_bit = row["start_bit"]
        if start_bit is not None and (start_bit < 1 or start_bit > 8):
            return None, DecodeWarning(
                category="invalid_start_bit",
                message=f"SPN {spn} has invalid start_bit {start_bit}",
                pgn=pgn,
                spn=spn,
            )

        return _MappingSpec(
            spn=spn,
            spn_name=row["spn_name"],
            start_byte=int(start_byte),
            start_bit=int(start_bit) if start_bit is not None else None,
            bit_length=int(bit_length),
            byte_order=byte_order,
            signed=signedness,
            factor=factor,
            offset=offset,
            unit=unit,
            origin=str(row["origin"]),
            source_id=int(row["source_id"]),
            raw_position_text=row["raw_position_text"],
        ), None
