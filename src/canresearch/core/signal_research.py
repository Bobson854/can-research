"""Proprietary signal research primitives — deterministic evidence only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canresearch.core.candidate_fields import generate_field_candidates
from canresearch.core.checksum_detection import detect_checksum_candidates
from canresearch.core.counter_detection import detect_counter_candidates
from canresearch.core.j1939_nodes import resolve_source_addresses_for_asset
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.live_research import (
    DEFAULT_COMPARE_WINDOW_S,
    MAX_COMPARE_WINDOW_S,
    build_session_sa_asset_map,
    compare_experiment_windows,
)
from canresearch.core.reference_correlation import (
    DEFAULT_ALIGNMENT_TOLERANCE_US,
    correlate_field_with_reference,
)
from canresearch.core.research_frames import (
    collect_payload_series,
    format_can_id,
    load_session_frames,
    resolve_event_window_us,
)
from canresearch.core.session_events import get_session_event_by_label
from canresearch.core.signal_models import ReferenceSample

DEFAULT_CANDIDATE_IDS = 20
MAX_CANDIDATE_IDS = 100
MAX_REPEATED_PAIRS = 20
MAX_SAMPLE_VALUES = 10

MOST_COMMON_LIMIT = 5


def _dominant_bit(payloads: list[bytes], bit_index: int) -> int:
    ones = sum(1 for p in payloads if (p[bit_index // 8] >> (bit_index % 8)) & 1)
    return 1 if ones >= len(payloads) / 2 else 0


def _byte_stats(payloads: list[bytes], byte_index: int) -> dict[str, Any]:
    values = [p[byte_index] for p in payloads]
    if not values:
        return {
            "byte": byte_index,
            "unique_values": 0,
            "min": None,
            "max": None,
            "change_count": 0,
            "change_rate": 0.0,
            "most_common": [],
        }
    changes = sum(1 for i in range(1, len(values)) if values[i] != values[i - 1])
    transitions = max(len(values) - 1, 1)
    freq: dict[int, int] = {}
    for v in values:
        freq[v] = freq.get(v, 0) + 1
    common = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:MOST_COMMON_LIMIT]
    return {
        "byte": byte_index,
        "unique_values": len(freq),
        "min": min(values),
        "max": max(values),
        "change_count": changes,
        "change_rate": round(changes / transitions, 4),
        "most_common": [{"value": v, "count": c} for v, c in common],
    }


def _bit_stats(
    payloads: list[bytes],
    bit_index: int,
    *,
    payload_len: int,
) -> dict[str, Any] | None:
    if bit_index >= payload_len * 8:
        return None
    zeros = ones = toggles = 0
    prev: int | None = None
    for p in payloads:
        bit = (p[bit_index // 8] >> (bit_index % 8)) & 1
        if bit:
            ones += 1
        else:
            zeros += 1
        if prev is not None and bit != prev:
            toggles += 1
        prev = bit
    total = max(len(payloads), 1)
    transitions = max(len(payloads) - 1, 1)
    return {
        "bit_index": bit_index,
        "zero_count": zeros,
        "one_count": ones,
        "toggle_count": toggles,
        "toggle_rate": round(toggles / transitions, 4),
        "one_probability": round(ones / total, 4),
    }


def _resolve_sa_filter(
    session_id: str,
    *,
    asset_key: str | None,
    source_address: int | None,
    db_path: Path | None,
) -> set[int] | None:
    if source_address is not None:
        return {source_address}
    if asset_key is None:
        return None
    try:
        resolved = resolve_source_addresses_for_asset(
            session_id, asset_key, db_path=db_path
        )
    except ValueError as exc:
        raise LiveResearchError("asset_not_resolved", str(exc)) from exc
    return set(resolved.source_addresses)


def rank_candidate_ids(
    session_id: str,
    *,
    baseline_event: str,
    action_event: str,
    window_seconds: float = DEFAULT_COMPARE_WINDOW_S,
    source_address: int | None = None,
    asset_key: str | None = None,
    can_id: int | None = None,
    pgn: int | None = None,
    limit: int = DEFAULT_CANDIDATE_IDS,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Rank CAN IDs by deterministic baseline/action change evidence."""
    if limit <= 0 or limit > MAX_CANDIDATE_IDS:
        raise LiveResearchError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_CANDIDATE_IDS}, got {limit}",
        )

    comparison = compare_experiment_windows(
        session_id,
        baseline_event=baseline_event,
        action_event=action_event,
        window_seconds=window_seconds,
        db_path=db_path,
        top_n=MAX_CANDIDATE_IDS,
    )

    sa_filter = _resolve_sa_filter(
        session_id, asset_key=asset_key, source_address=source_address, db_path=db_path
    )

    ranked: list[dict[str, Any]] = []
    for index, item in enumerate(comparison.get("top_changes", []), start=1):
        cid_int = int(item["can_id"], 16)
        if can_id is not None and cid_int != can_id:
            continue
        if pgn is not None and item.get("pgn") != pgn:
            continue
        sa = item.get("source_address")
        if sa_filter is not None and sa not in sa_filter:
            continue
        if asset_key is not None and item.get("asset_key") != asset_key:
            continue

        base_stats = item.get("baseline_stats", {})
        act_stats = item.get("action_stats", {})
        base_rates = base_stats.get("byte_change_rate", [0.0] * 8)
        act_rates = act_stats.get("byte_change_rate", [0.0] * 8)
        baseline_activity = (
            sum(base_rates) / len(base_rates) if base_rates else 0.0
        )
        action_activity = sum(act_rates) / len(act_rates) if act_rates else 0.0

        ranked.append(
            {
                "rank": index,
                "can_id": item["can_id"],
                "pgn": item.get("pgn"),
                "source_address": sa,
                "destination_address": item.get("destination_address"),
                "asset_key": item.get("asset_key"),
                "baseline_count": item.get("baseline_count", 0),
                "action_count": item.get("action_count", 0),
                "changed_byte_indices": item.get("changed_byte_indices", []),
                "change_score": item.get("change_score", 0.0),
                "evidence": {
                    "changed_bytes": item.get("changed_byte_indices", []),
                    "baseline_activity": round(baseline_activity, 4),
                    "action_activity": round(action_activity, 4),
                    "action_only": item["can_id"] in comparison.get("action_only_can_ids", []),
                },
            }
        )

    return {
        "session_id": session_id,
        "baseline_event": baseline_event,
        "action_event": action_event,
        "window_seconds": window_seconds,
        "candidates": ranked[:limit],
        "truncated": len(ranked) > limit,
    }


def analyze_byte_activity(
    payloads: list[bytes],
    *,
    payload_len: int | None = None,
) -> list[dict[str, Any]]:
    """Per-byte activity statistics for a payload series."""
    if not payloads:
        return []
    length = payload_len or max(len(p) for p in payloads)
    return [_byte_stats(payloads, i) for i in range(min(length, 8))]


def analyze_bit_activity(
    payloads: list[bytes],
    *,
    payload_len: int | None = None,
) -> list[dict[str, Any]]:
    """Per-bit activity statistics (valid bits only, not padding)."""
    if not payloads:
        return []
    length = payload_len or min(max(len(p) for p in payloads), 8)
    stats: list[dict[str, Any]] = []
    for bit_index in range(length * 8):
        row = _bit_stats(payloads, bit_index, payload_len=length)
        if row is not None:
            stats.append(row)
    return stats


def analyze_can_id_activity(
    session_id: str,
    can_id: int,
    *,
    baseline_event: str | None = None,
    action_event: str | None = None,
    window_seconds: float = DEFAULT_COMPARE_WINDOW_S,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Byte and bit activity for one CAN ID across baseline/action windows."""
    if window_seconds <= 0 or window_seconds > MAX_COMPARE_WINDOW_S:
        raise LiveResearchError("limit_out_of_range", "window_seconds out of range")

    frames = load_session_frames(session_id, db_path=db_path)
    sa_map = build_session_sa_asset_map(session_id, db_path=db_path)

    if baseline_event and action_event:
        base_start, base_end = resolve_event_window_us(
            session_id, baseline_event, window_seconds=window_seconds, db_path=db_path
        )
        act_start, act_end = resolve_event_window_us(
            session_id, action_event, window_seconds=window_seconds, db_path=db_path
        )
        base_series = collect_payload_series(frames, can_id, start_us=base_start, end_us=base_end)
        act_series = collect_payload_series(frames, can_id, start_us=act_start, end_us=act_end)
    else:
        base_series = collect_payload_series(frames, can_id)
        act_series = base_series

    payload_len = 8
    if base_series.payloads:
        payload_len = min(len(base_series.payloads[0]), 8)

    base_bytes = analyze_byte_activity(list(base_series.payloads), payload_len=payload_len)
    act_bytes = analyze_byte_activity(list(act_series.payloads), payload_len=payload_len)
    base_bits = analyze_bit_activity(list(base_series.payloads), payload_len=payload_len)
    act_bits = analyze_bit_activity(list(act_series.payloads), payload_len=payload_len)

    sa = base_series.source_address or act_series.source_address
    field_candidates = generate_field_candidates(
        list(act_series.payloads or base_series.payloads),
        can_id=format_can_id(can_id),
        active_bytes=set(
            b["byte"]
            for b in act_bytes
            if b["change_rate"] > 0.05 or b["unique_values"] > 1
        ),
        pgn=base_series.pgn,
        source_address=sa,
        destination_address=base_series.destination_address,
        asset_key=sa_map.get(sa) if sa is not None else None,
    )

    return {
        "session_id": session_id,
        "can_id": format_can_id(can_id),
        "pgn": base_series.pgn,
        "source_address": sa,
        "destination_address": base_series.destination_address,
        "asset_key": sa_map.get(sa) if sa is not None else None,
        "baseline": {
            "byte_activity": base_bytes,
            "bit_activity": base_bits,
            "frame_count": len(base_series.payloads),
        },
        "action": {
            "byte_activity": act_bytes,
            "bit_activity": act_bits,
            "frame_count": len(act_series.payloads),
        },
        "field_candidates": [c.to_dict() for c in field_candidates],
    }


def compare_repeated_actions(
    session_id: str,
    *,
    baseline_events: list[str],
    action_events: list[str],
    window_seconds: float = DEFAULT_COMPARE_WINDOW_S,
    can_id: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Compare repeated baseline/action experiment pairs for consistency evidence."""
    if len(baseline_events) != len(action_events):
        msg = "baseline_events and action_events must have the same length"
        raise LiveResearchError("invalid_event_pairs", msg)
    if not baseline_events:
        raise LiveResearchError("invalid_event_pairs", "At least one event pair is required")
    if len(baseline_events) > MAX_REPEATED_PAIRS:
        raise LiveResearchError(
            "limit_out_of_range",
            f"Maximum {MAX_REPEATED_PAIRS} repeated pairs allowed",
        )

    frames = load_session_frames(session_id, db_path=db_path)
    window_us = int(window_seconds * 1_000_000)

    bit_evidence: dict[tuple[int, int], dict[str, int]] = {}
    byte_evidence: dict[tuple[int, int], dict[str, int]] = {}

    for base_label, act_label in zip(baseline_events, action_events, strict=True):
        base_marker = get_session_event_by_label(session_id, base_label, db_path=db_path)
        act_marker = get_session_event_by_label(session_id, act_label, db_path=db_path)
        base_end = base_marker.timestamp_us + window_us
        act_end = act_marker.timestamp_us + window_us

        ids: set[int] = set()
        if can_id is not None:
            ids.add(can_id)
        else:
            for frame in frames:
                if frame.can_id is not None:
                    if base_marker.timestamp_us <= frame.timestamp_us < base_end:
                        ids.add(frame.can_id)
                    if act_marker.timestamp_us <= frame.timestamp_us < act_end:
                        ids.add(frame.can_id)

        for cid in ids:
            base_series = collect_payload_series(
                frames, cid, start_us=base_marker.timestamp_us, end_us=base_end
            )
            act_series = collect_payload_series(
                frames, cid, start_us=act_marker.timestamp_us, end_us=act_end
            )
            base_payloads = list(base_series.payloads)
            act_payloads = list(act_series.payloads)
            if not base_payloads or not act_payloads:
                continue

            payload_len = min(len(base_payloads[0]), len(act_payloads[0]), 8)
            for bit_index in range(payload_len * 8):
                key = (cid, bit_index)
                entry = bit_evidence.setdefault(
                    key, {"changed_in_action": 0, "changed_in_baseline": 0, "repetitions": 0}
                )
                entry["repetitions"] += 1
                base_dom = _dominant_bit(base_payloads, bit_index)
                act_dom = _dominant_bit(act_payloads, bit_index)
                if base_dom != act_dom:
                    entry["changed_in_action"] += 1
                base_toggles = sum(
                    1
                    for i in range(1, len(base_payloads))
                    if ((base_payloads[i][bit_index // 8] >> (bit_index % 8)) & 1)
                    != ((base_payloads[i - 1][bit_index // 8] >> (bit_index % 8)) & 1)
                )
                if base_toggles > 0:
                    entry["changed_in_baseline"] += 1

            for byte_index in range(payload_len):
                key = (cid, byte_index)
                entry = byte_evidence.setdefault(
                    key, {"changed_in_action": 0, "changed_in_baseline": 0, "repetitions": 0}
                )
                base_vals = {p[byte_index] for p in base_payloads}
                act_vals = {p[byte_index] for p in act_payloads}
                if base_vals != act_vals:
                    entry["changed_in_action"] += 1

    sa_map = build_session_sa_asset_map(session_id, db_path=db_path)
    bit_results: list[dict[str, Any]] = []
    for (cid, bit_index), counts in bit_evidence.items():
        reps = counts["repetitions"]
        if reps == 0:
            continue
        consistency = counts["changed_in_action"] / reps
        baseline_noise = counts["changed_in_baseline"] / reps
        specificity = consistency * (1.0 - baseline_noise)
        fields = collect_payload_series(frames, cid)
        sa = fields.source_address
        bit_results.append(
            {
                "can_id": format_can_id(cid),
                "pgn": fields.pgn,
                "source_address": sa,
                "asset_key": sa_map.get(sa) if sa is not None else None,
                "bit_index": bit_index,
                "repetitions": reps,
                "changed_in_action": counts["changed_in_action"],
                "changed_in_baseline": counts["changed_in_baseline"],
                "consistency": round(consistency, 4),
                "baseline_false_positive_rate": round(baseline_noise, 4),
                "action_specificity_score": round(specificity, 4),
            }
        )

    bit_results.sort(
        key=lambda r: (-r["action_specificity_score"], -r["consistency"], r["can_id"])
    )

    return {
        "session_id": session_id,
        "pair_count": len(baseline_events),
        "window_seconds": window_seconds,
        "bit_consistency": bit_results[:100],
        "byte_consistency_count": len(byte_evidence),
    }


def detect_counters_for_can_id(
    session_id: str,
    can_id: int,
    *,
    db_path: Path | None = None,
    max_candidates: int = 32,
) -> dict[str, Any]:
    frames = load_session_frames(session_id, db_path=db_path)
    series = collect_payload_series(frames, can_id)
    candidates = detect_counter_candidates(
        list(series.payloads), max_candidates=max_candidates
    )
    return {
        "session_id": session_id,
        "can_id": format_can_id(can_id),
        "candidates": [c.to_dict() for c in candidates],
        "sample_count": len(series.payloads),
        "truncated": series.truncated,
    }


def detect_checksums_for_can_id(
    session_id: str,
    can_id: int,
    *,
    db_path: Path | None = None,
    max_candidates: int = 32,
) -> dict[str, Any]:
    frames = load_session_frames(session_id, db_path=db_path)
    series = collect_payload_series(frames, can_id)
    candidates = detect_checksum_candidates(
        list(series.payloads), max_candidates=max_candidates
    )
    return {
        "session_id": session_id,
        "can_id": format_can_id(can_id),
        "candidates": [c.to_dict() for c in candidates],
        "sample_count": len(series.payloads),
        "truncated": series.truncated,
    }


def correlate_candidate_field(
    session_id: str,
    can_id: int,
    *,
    start_bit: int,
    length: int,
    reference_series: list[dict[str, Any]],
    signed: bool = False,
    tolerance_us: int = DEFAULT_ALIGNMENT_TOLERANCE_US,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Correlate a candidate field against a timestamped reference series."""
    frames = load_session_frames(session_id, db_path=db_path)
    series = collect_payload_series(frames, can_id)
    ref = [
        ReferenceSample(timestamp_us=int(item["timestamp_us"]), value=float(item["value"]))
        for item in reference_series[:10_000]
    ]
    result = correlate_field_with_reference(
        series,
        ref,
        start_bit=start_bit,
        length=length,
        signed=signed,
        tolerance_us=tolerance_us,
    )
    return {
        "session_id": session_id,
        "can_id": format_can_id(can_id),
        "start_bit": start_bit,
        "length": length,
        **result.to_dict(),
    }


def analyze_state_transitions(
    baseline_payloads: list[bytes],
    action_payloads: list[bytes],
    *,
    bit_index: int,
) -> dict[str, Any]:
    """Direction/state transition evidence for a boolean bit candidate."""
    base_dom = _dominant_bit(baseline_payloads, bit_index) if baseline_payloads else 0
    act_dom = _dominant_bit(action_payloads, bit_index) if action_payloads else 0
    transition = None
    if base_dom == 0 and act_dom == 1:
        transition = "0_to_1"
    elif base_dom == 1 and act_dom == 0:
        transition = "1_to_0"
    elif base_dom == act_dom:
        transition = "stable"
    else:
        transition = "mixed"
    return {
        "bit_index": bit_index,
        "baseline_dominant": base_dom,
        "action_dominant": act_dom,
        "transition_direction": transition,
        "consistency": 1.0 if base_dom != act_dom else 0.0,
    }
