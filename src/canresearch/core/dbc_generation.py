"""Build a reference-backed DBC model from a saved capture session."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from canresearch.core.analysis import analyze_session
from canresearch.core.dbc_identifiers import sanitize_dbc_identifier, unique_signal_identifier
from canresearch.core.dbc_model import DbcDatabase, DbcMessage, DbcSignal
from canresearch.core.dbc_position import (
    encode_dbc_extended_id,
    j1939_position_to_dbc_start_bit,
    signal_bit_range,
)
from canresearch.core.j1939_mappings import MappingSpec, MappingWarning, load_pgn_mapping_specs
from canresearch.core.session_decode import J1939_ORIGINS, TRANSPORT_PGNS
from canresearch.core.spn_scaling import parse_numeric
from canresearch.references.service import ReferenceService
from canresearch.storage.database import default_db_path, initialize

DEFAULT_DLC = 8
DEFAULT_NODE = "Vector__XXX"


@dataclass(frozen=True, slots=True)
class GenerationWarning:
    category: str
    message: str
    pgn: int | None = None
    spn: int | None = None
    can_id: int | None = None


@dataclass(frozen=True, slots=True)
class SessionDbcSummary:
    session_id: str
    session_name: str | None
    frames_examined: int
    observed_j1939_pgns: int
    reference_backed_pgns: int
    messages_generated: int
    signals_generated: int
    signals_skipped: int
    warnings: tuple[GenerationWarning, ...] = field(default_factory=tuple)
    database: DbcDatabase = field(default_factory=lambda: DbcDatabase(version="", nodes=()))

    @property
    def warning_counts(self) -> dict[str, int]:
        return dict(Counter(w.category for w in self.warnings))


def generate_session_dbc(
    session_id: str,
    *,
    db_path: Path | None = None,
    pgn_filter: int | None = None,
) -> SessionDbcSummary:
    """Build a DBC database from observed reference-backed J1939 traffic."""
    path = db_path or default_db_path()
    analysis = analyze_session(session_id, db_path=path, persist=False)

    conn = initialize(path)
    try:
        service = ReferenceService(conn)
        return _build_database(
            session_id=session_id,
            session_name=analysis.session_name,
            analysis=analysis,
            service=service,
            pgn_filter=pgn_filter,
        )
    finally:
        conn.close()


def _build_database(
    *,
    session_id: str,
    session_name: str | None,
    analysis,
    service: ReferenceService,
    pgn_filter: int | None,
) -> SessionDbcSummary:
    observed_pgns = {item.pgn for item in analysis.observed}
    warnings: list[GenerationWarning] = []
    messages: list[DbcMessage] = []
    signals_generated = 0
    signals_skipped = 0
    reference_pgns: set[int] = set()

    eligible = [
        item
        for item in analysis.observed
        if item.classification in J1939_ORIGINS
        and (pgn_filter is None or item.pgn == pgn_filter)
    ]
    reference_pgns = {item.pgn for item in eligible}

    for item in sorted(eligible, key=lambda row: (row.can_id, row.pgn, row.source_address)):
        if item.pgn in TRANSPORT_PGNS:
            warnings.append(
                GenerationWarning(
                    category="transport_unsupported",
                    message="Transport-protocol PGN omitted from DBC",
                    pgn=item.pgn,
                    can_id=item.can_id,
                )
            )
            continue

        specs, spec_warnings = load_pgn_mapping_specs(service, item.pgn, item.classification)
        for warning in spec_warnings:
            warnings.append(_from_mapping_warning(warning, can_id=item.can_id))
        if not specs:
            continue

        message_name = _message_name(item)
        dbc_signals, built, skipped, build_warnings = _build_signals(
            specs,
            pgn=item.pgn,
            can_id=item.can_id,
        )
        signals_generated += built
        signals_skipped += skipped
        warnings.extend(build_warnings)

        if not dbc_signals:
            continue

        messages.append(
            DbcMessage(
                name=message_name,
                can_id=item.can_id,
                dbc_frame_id=encode_dbc_extended_id(item.can_id),
                dlc=DEFAULT_DLC,
                transmitter=DEFAULT_NODE,
                pgn=item.pgn,
                source_address=item.source_address,
                destination_address=item.destination_address,
                origin=item.classification,
                signals=tuple(
                    sorted(dbc_signals, key=lambda sig: (sig.start_bit, sig.spn, sig.name))
                ),
            )
        )

    database = DbcDatabase(
        version="",
        nodes=(DEFAULT_NODE,),
        messages=tuple(sorted(messages, key=lambda msg: msg.dbc_frame_id)),
    )

    return SessionDbcSummary(
        session_id=session_id,
        session_name=session_name,
        frames_examined=analysis.total_frames,
        observed_j1939_pgns=len(observed_pgns),
        reference_backed_pgns=len(reference_pgns),
        messages_generated=len(messages),
        signals_generated=signals_generated,
        signals_skipped=signals_skipped,
        warnings=tuple(warnings),
        database=database,
    )


def _from_mapping_warning(warning: MappingWarning, *, can_id: int) -> GenerationWarning:
    return GenerationWarning(
        category=warning.category,
        message=warning.message,
        pgn=warning.pgn,
        spn=warning.spn,
        can_id=can_id,
    )


def _message_name(item) -> str:
    base = item.display_name or f"PGN_{item.pgn}"
    parts = [sanitize_dbc_identifier(base), f"SA{item.source_address:02X}"]
    if item.destination_address is not None:
        parts.append(f"DA{item.destination_address:02X}")
    return sanitize_dbc_identifier("_".join(parts))


def _build_signals(
    specs: tuple[MappingSpec, ...],
    *,
    pgn: int,
    can_id: int,
) -> tuple[list[DbcSignal], int, int, list[GenerationWarning]]:
    signals: list[DbcSignal] = []
    warnings: list[GenerationWarning] = []
    used_names: set[str] = set()
    occupied: list[tuple[int, int]] = []
    built = 0
    skipped = 0

    for spec in sorted(specs, key=lambda row: (row.start_byte, row.start_bit or 0, row.spn)):
        dbc_start = j1939_position_to_dbc_start_bit(
            start_byte=spec.start_byte,
            start_bit=spec.start_bit,
            bit_length=spec.bit_length,
            byte_order=spec.byte_order,
        )
        if dbc_start is None:
            skipped += 1
            warnings.append(
                GenerationWarning(
                    category="unsupported_byte_order",
                    message=f"SPN {spec.spn} position not supported for DBC export",
                    pgn=pgn,
                    spn=spec.spn,
                    can_id=can_id,
                )
            )
            continue

        bit_range = signal_bit_range(dbc_start, spec.bit_length)
        if _overlaps(occupied, bit_range):
            skipped += 1
            warnings.append(
                GenerationWarning(
                    category="signal_overlap",
                    message=f"SPN {spec.spn} overlaps an existing signal in the message",
                    pgn=pgn,
                    spn=spec.spn,
                    can_id=can_id,
                )
            )
            continue

        byte_order = 1 if spec.byte_order == "intel" else 0
        minimum, maximum = _signal_min_max(spec)
        base_name = spec.spn_name or f"SPN_{spec.spn}"
        signal_name = unique_signal_identifier(base_name, spec.spn, used_names)

        signals.append(
            DbcSignal(
                name=signal_name,
                start_bit=dbc_start,
                bit_length=spec.bit_length,
                byte_order=byte_order,
                signed=spec.signed,
                factor=spec.factor,
                offset=spec.offset,
                minimum=minimum,
                maximum=maximum,
                unit=spec.unit or "",
                pgn=pgn,
                spn=spec.spn,
                origin=spec.origin,
            )
        )
        occupied.append(bit_range)
        built += 1

    return signals, built, skipped, warnings


def _overlaps(ranges: list[tuple[int, int]], candidate: tuple[int, int]) -> bool:
    start, end = candidate
    for existing_start, existing_end in ranges:
        if start < existing_end and end > existing_start:
            return True
    return False


def _signal_min_max(spec: MappingSpec) -> tuple[float, float]:
    eng_min = parse_numeric(spec.minimum)
    eng_max = parse_numeric(spec.maximum)
    if eng_min is not None and eng_max is not None:
        return eng_min, eng_max

    if spec.signed:
        raw_min = -(1 << (spec.bit_length - 1))
        raw_max = (1 << (spec.bit_length - 1)) - 1
    else:
        raw_min = 0
        raw_max = (1 << spec.bit_length) - 1
    return raw_min * spec.factor + spec.offset, raw_max * spec.factor + spec.offset
