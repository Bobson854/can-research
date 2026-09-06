"""Session coverage analysis against DBC knowledge sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from canresearch.core.dbc_knowledge import LoadedDbcSource
from canresearch.core.dbc_lookup import lookup_message_by_can_id
from canresearch.core.dbc_registry import load_dbc_sources
from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.research_frames import load_session_frames, parse_can_id_fields


@dataclass(frozen=True, slots=True)
class ObservedCanTraffic:
    is_extended: bool
    can_id: int
    frame_count: int
    max_dlc: int
    pgn: int | None
    source_address: int | None
    destination_address: int | None


@dataclass(frozen=True, slots=True)
class DbcCoverageRow:
    is_extended: bool
    can_id: int
    frame_count: int
    max_dlc: int
    pgn: int | None
    source_address: int | None
    destination_address: int | None
    classification: str
    reason: str
    dbc_source_key: str | None
    message_name: str | None
    signal_count: int | None


@dataclass(frozen=True, slots=True)
class DbcCoverageSummary:
    session_id: str
    dbc_sources: tuple[str, ...]
    asset_key: str | None
    rows: tuple[DbcCoverageRow, ...] = field(default_factory=tuple)
    unique_ids_observed: int = 0
    unique_ids_covered: int = 0
    unique_ids_partially_covered: int = 0
    unique_ids_unknown: int = 0
    frames_observed: int = 0
    frames_covered: int = 0
    frames_partially_covered: int = 0
    frames_unknown: int = 0
    unique_id_coverage_pct: float = 0.0
    frame_coverage_pct: float = 0.0
    known_can_ids: tuple[str, ...] = field(default_factory=tuple)
    unknown_can_ids: tuple[str, ...] = field(default_factory=tuple)
    partially_covered_can_ids: tuple[str, ...] = field(default_factory=tuple)


def _format_can_key(is_extended: bool, can_id: int) -> str:
    if is_extended:
        return f"0x{can_id:08X}"
    return f"0x{can_id:03X}"


def aggregate_session_traffic(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> tuple[ObservedCanTraffic, ...]:
    frames = load_session_frames(session_id, db_path=db_path)
    buckets: dict[tuple[bool, int], ObservedCanTraffic] = {}
    for frame in frames:
        if frame.can_id is None or frame.is_error_frame:
            continue
        key = (frame.is_extended, frame.can_id)
        dlc = frame.dlc if frame.dlc is not None else len(frame.data)
        fields = parse_can_id_fields(frame.can_id, is_extended=frame.is_extended)
        if key in buckets:
            existing = buckets[key]
            buckets[key] = ObservedCanTraffic(
                is_extended=existing.is_extended,
                can_id=existing.can_id,
                frame_count=existing.frame_count + 1,
                max_dlc=max(existing.max_dlc, dlc),
                pgn=existing.pgn,
                source_address=existing.source_address,
                destination_address=existing.destination_address,
            )
        else:
            buckets[key] = ObservedCanTraffic(
                is_extended=frame.is_extended,
                can_id=frame.can_id,
                frame_count=1,
                max_dlc=dlc,
                pgn=fields.get("pgn"),
                source_address=fields.get("source_address"),
                destination_address=fields.get("destination_address"),
            )
    rows = sorted(buckets.values(), key=lambda item: (-item.frame_count, item.can_id))
    return tuple(rows)


def _pgn_lookup_candidates(
    sources: tuple[LoadedDbcSource, ...],
    *,
    pgn: int,
) -> list[tuple[str, str, int]]:
    """Return (source_key, message_name, can_id) for extended J1939 PGN matches."""
    matches: list[tuple[str, str, int]] = []
    for source in sources:
        for message in source.database.messages:
            if message.dbc_frame_id < 0x80000000 and message.can_id <= 0x7FF:
                continue
            try:
                parsed = parse_j1939_id(message.can_id)
            except ValueError:
                continue
            if parsed.pgn == pgn:
                matches.append((source.meta.key, message.name, message.can_id))
    return matches


def _classify_observed(
    observed: ObservedCanTraffic,
    sources: tuple[LoadedDbcSource, ...],
) -> DbcCoverageRow:
    exact = lookup_message_by_can_id(
        sources,
        can_id=observed.can_id,
        is_extended=observed.is_extended,
    )
    if exact:
        names = {match.message.name for match in exact}
        signal_counts = {len(match.message.signals) for match in exact}
        source_keys = {match.source_key for match in exact}
        primary = exact[0]
        if len(names) > 1 or len(signal_counts) > 1:
            return DbcCoverageRow(
                is_extended=observed.is_extended,
                can_id=observed.can_id,
                frame_count=observed.frame_count,
                max_dlc=observed.max_dlc,
                pgn=observed.pgn,
                source_address=observed.source_address,
                destination_address=observed.destination_address,
                classification="partially_covered",
                reason="conflicting_definitions_across_sources",
                dbc_source_key=primary.source_key,
                message_name=primary.message.name,
                signal_count=len(primary.message.signals),
            )
        if observed.max_dlc > primary.message.dlc:
            return DbcCoverageRow(
                is_extended=observed.is_extended,
                can_id=observed.can_id,
                frame_count=observed.frame_count,
                max_dlc=observed.max_dlc,
                pgn=observed.pgn,
                source_address=observed.source_address,
                destination_address=observed.destination_address,
                classification="partially_covered",
                reason="payload_exceeds_message_dlc",
                dbc_source_key=primary.source_key,
                message_name=primary.message.name,
                signal_count=len(primary.message.signals),
            )
        reason = "exact_can_id_match"
        if len(source_keys) > 1:
            reason = "exact_can_id_match_multiple_sources"
        return DbcCoverageRow(
            is_extended=observed.is_extended,
            can_id=observed.can_id,
            frame_count=observed.frame_count,
            max_dlc=observed.max_dlc,
            pgn=observed.pgn,
            source_address=observed.source_address,
            destination_address=observed.destination_address,
            classification="covered",
            reason=reason,
            dbc_source_key=primary.source_key,
            message_name=primary.message.name,
            signal_count=len(primary.message.signals),
        )

    if observed.is_extended and observed.pgn is not None:
        pgn_matches = _pgn_lookup_candidates(sources, pgn=observed.pgn)
        unique_messages = {(key, name) for key, name, _ in pgn_matches}
        if len(unique_messages) == 1:
            source_key, message_name = next(iter(unique_messages))
            signal_count = next(
                len(message.signals)
                for source in sources
                if source.meta.key == source_key
                for message in source.database.messages
                if message.name == message_name
            )
            return DbcCoverageRow(
                is_extended=observed.is_extended,
                can_id=observed.can_id,
                frame_count=observed.frame_count,
                max_dlc=observed.max_dlc,
                pgn=observed.pgn,
                source_address=observed.source_address,
                destination_address=observed.destination_address,
                classification="partially_covered",
                reason="address_variant_pgn_match",
                dbc_source_key=source_key,
                message_name=message_name,
                signal_count=signal_count,
            )
        if len(unique_messages) > 1:
            first_key, first_name = next(iter(unique_messages))
            return DbcCoverageRow(
                is_extended=observed.is_extended,
                can_id=observed.can_id,
                frame_count=observed.frame_count,
                max_dlc=observed.max_dlc,
                pgn=observed.pgn,
                source_address=observed.source_address,
                destination_address=observed.destination_address,
                classification="partially_covered",
                reason="address_variant_ambiguous",
                dbc_source_key=first_key,
                message_name=first_name,
                signal_count=None,
            )

    return DbcCoverageRow(
        is_extended=observed.is_extended,
        can_id=observed.can_id,
        frame_count=observed.frame_count,
        max_dlc=observed.max_dlc,
        pgn=observed.pgn,
        source_address=observed.source_address,
        destination_address=observed.destination_address,
        classification="unknown",
        reason="no_dbc_message_match",
        dbc_source_key=None,
        message_name=None,
        signal_count=None,
    )


def analyze_dbc_coverage(
    session_id: str,
    *,
    source_keys: tuple[str, ...] | None = None,
    asset_key: str | None = None,
    db_path: Path | None = None,
    cwd: Path | None = None,
    row_limit: int | None = None,
) -> DbcCoverageSummary:
    """Compare observed session traffic against one or more DBC knowledge sources."""
    from canresearch.config import resolve_data_dir

    data_dir = resolve_data_dir()
    sources = load_dbc_sources(
        source_keys=source_keys,
        asset_key=asset_key,
        data_dir=data_dir,
        cwd=cwd,
    )
    if not sources:
        msg = "No DBC sources available for coverage analysis"
        raise ValueError(msg)

    observed_rows = aggregate_session_traffic(session_id, db_path=db_path)
    coverage_rows = [_classify_observed(row, sources) for row in observed_rows]
    if row_limit is not None and row_limit > 0:
        coverage_rows = coverage_rows[:row_limit]

    unique_observed = len(observed_rows)
    frames_observed = sum(row.frame_count for row in observed_rows)
    frames_covered = sum(
        row.frame_count for row in coverage_rows if row.classification == "covered"
    )
    frames_partial = sum(
        row.frame_count for row in coverage_rows if row.classification == "partially_covered"
    )
    frames_unknown = sum(
        row.frame_count for row in coverage_rows if row.classification == "unknown"
    )

    unique_covered = sum(1 for row in coverage_rows if row.classification == "covered")
    unique_partial = sum(1 for row in coverage_rows if row.classification == "partially_covered")
    unique_unknown = sum(1 for row in coverage_rows if row.classification == "unknown")

    known_ids = tuple(
        _format_can_key(row.is_extended, row.can_id)
        for row in coverage_rows
        if row.classification == "covered"
    )
    unknown_ids = tuple(
        _format_can_key(row.is_extended, row.can_id)
        for row in coverage_rows
        if row.classification == "unknown"
    )
    partial_ids = tuple(
        _format_can_key(row.is_extended, row.can_id)
        for row in coverage_rows
        if row.classification == "partially_covered"
    )

    unique_pct = (100.0 * unique_covered / unique_observed) if unique_observed else 0.0
    frame_pct = (100.0 * frames_covered / frames_observed) if frames_observed else 0.0

    return DbcCoverageSummary(
        session_id=session_id,
        dbc_sources=tuple(source.meta.key for source in sources),
        asset_key=asset_key,
        rows=tuple(coverage_rows),
        unique_ids_observed=unique_observed,
        unique_ids_covered=unique_covered,
        unique_ids_partially_covered=unique_partial,
        unique_ids_unknown=unique_unknown,
        frames_observed=frames_observed,
        frames_covered=frames_covered,
        frames_partially_covered=frames_partial,
        frames_unknown=frames_unknown,
        unique_id_coverage_pct=round(unique_pct, 2),
        frame_coverage_pct=round(frame_pct, 2),
        known_can_ids=known_ids,
        unknown_can_ids=unknown_ids,
        partially_covered_can_ids=partial_ids,
    )
