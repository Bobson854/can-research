"""Deterministic candidate field generation and endianness testing."""

from __future__ import annotations

from typing import Any

from canresearch.core.dbc_position import decode_intel_dbc_signal
from canresearch.core.research_frames import effective_payload_length
from canresearch.core.signal_models import SignalCandidate

DEFAULT_FIELD_CANDIDATES = 50
MAX_FIELD_CANDIDATES = 200

CANDIDATE_LENGTHS = (1, 2, 4, 8, 16, 24, 32)


def _decode_intel(payload: bytes, start_bit: int, length: int, signed: bool = False) -> int | None:
    try:
        return decode_intel_dbc_signal(
            payload,
            start_bit=start_bit,
            bit_length=length,
            signed=signed,
        )
    except ValueError:
        return None


def _decode_motorola_whole_bytes(payload: bytes, start_byte: int, num_bytes: int) -> int | None:
    start_idx = start_byte
    end_idx = start_byte + num_bytes
    if end_idx > len(payload):
        return None
    return int.from_bytes(payload[start_idx:end_idx], "big")


def _field_activity(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    unique = len(set(values))
    changes = sum(1 for i in range(1, len(values)) if values[i] != values[i - 1])
    return min(1.0, (unique / max(len(values), 1)) * 0.5 + (changes / (len(values) - 1)) * 0.5)


def _series_summary(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"min": None, "max": None, "unique_count": 0, "monotonic_segments": 0}
    monotonic = 0
    direction = 0
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        if delta == 0:
            continue
        sign = 1 if delta > 0 else -1
        if direction == 0:
            direction = sign
            monotonic = 1
        elif sign == direction:
            monotonic += 1
        else:
            direction = sign
            monotonic = 1
    return {
        "min": min(values),
        "max": max(values),
        "unique_count": len(set(values)),
        "monotonic_segments": monotonic,
    }


def generate_field_candidates(
    payloads: list[bytes],
    *,
    can_id: str,
    active_bytes: set[int] | None = None,
    active_bits: set[int] | None = None,
    pgn: int | None = None,
    source_address: int | None = None,
    destination_address: int | None = None,
    asset_key: str | None = None,
    limit: int = DEFAULT_FIELD_CANDIDATES,
    min_activity: float = 0.05,
) -> list[SignalCandidate]:
    """Generate pruned bitfield candidates from payload activity."""
    if not payloads:
        return []

    payload_len = max(effective_payload_length(None, p) for p in payloads)
    valid_bits = payload_len * 8

    if active_bytes is None:
        active_bytes = set()
        for byte_index in range(payload_len):
            vals = [p[byte_index] for p in payloads]
            if _field_activity(vals) >= min_activity:
                active_bytes.add(byte_index)

    if active_bits is None:
        active_bits = set()
        for bit_index in range(valid_bits):
            vals = [(p[bit_index // 8] >> (bit_index % 8)) & 1 for p in payloads]
            if _field_activity(vals) >= min_activity:
                active_bits.add(bit_index)

    candidates: list[SignalCandidate] = []
    seen: set[tuple[int, int, str]] = set()

    for bit_index in sorted(active_bits):
        if bit_index >= valid_bits:
            continue
        key = (bit_index, 1, "intel")
        if key in seen:
            continue
        seen.add(key)
        values = [
            decode_intel_dbc_signal(p, start_bit=bit_index, bit_length=1, signed=False)
            for p in payloads
        ]
        activity = _field_activity(values)
        if activity < min_activity:
            continue
        candidates.append(
            SignalCandidate(
                can_id=can_id,
                start_bit=bit_index,
                length=1,
                byte_order="intel",
                signedness="unknown",
                pgn=pgn,
                source_address=source_address,
                destination_address=destination_address,
                asset_key=asset_key,
                raw_min=min(values),
                raw_max=max(values),
                unique_values=len(set(values)),
                activity_score=round(activity, 4),
                evidence={"type": "1-bit boolean"},
            )
        )

    for byte_index in sorted(active_bytes):
        if byte_index >= payload_len:
            continue
        for length in (2, 4, 8):
            start_bit = byte_index * 8
            if start_bit + length > valid_bits:
                continue
            key = (start_bit, length, "intel")
            if key in seen:
                continue
            seen.add(key)
            values = [
                v
                for p in payloads
                if (v := _decode_intel(p, start_bit, length)) is not None
            ]
            if not values:
                continue
            activity = _field_activity(values)
            if activity < min_activity:
                continue
            candidates.append(
                SignalCandidate(
                    can_id=can_id,
                    start_bit=start_bit,
                    length=length,
                    byte_order="intel",
                    signedness="unknown",
                    pgn=pgn,
                    source_address=source_address,
                    destination_address=destination_address,
                    asset_key=asset_key,
                    raw_min=min(values),
                    raw_max=max(values),
                    unique_values=len(set(values)),
                    activity_score=round(activity, 4),
                    evidence={"type": f"{length}-bit aligned"},
                )
            )

    for byte_index in sorted(active_bytes):
        for length in (16, 24, 32):
            num_bytes = length // 8
            start_bit = byte_index * 8
            if byte_index + num_bytes > payload_len:
                continue
            key = (start_bit, length, "intel")
            if key in seen:
                continue
            seen.add(key)
            values = [
                v
                for p in payloads
                if (v := _decode_intel(p, start_bit, length)) is not None
            ]
            if not values:
                continue
            activity = _field_activity(values)
            if activity < min_activity:
                continue
            candidates.append(
                SignalCandidate(
                    can_id=can_id,
                    start_bit=start_bit,
                    length=length,
                    byte_order="intel",
                    signedness="unknown",
                    pgn=pgn,
                    source_address=source_address,
                    destination_address=destination_address,
                    asset_key=asset_key,
                    raw_min=min(values),
                    raw_max=max(values),
                    unique_values=len(set(values)),
                    activity_score=round(activity, 4),
                    evidence={"type": f"{length}-bit Intel"},
                )
            )

    candidates.sort(key=lambda c: (-(c.activity_score or 0), c.start_bit))
    capped = candidates[: min(limit, MAX_FIELD_CANDIDATES)]
    for rank, candidate in enumerate(capped, start=1):
        candidate.rank = rank
    return capped


def evaluate_endianness_candidates(
    payloads: list[bytes],
    *,
    start_bit: int,
    length: int,
) -> dict[str, Any]:
    """Return Intel and Motorola interpretation summaries for a multi-byte field."""
    if length % 8 != 0 or length < 16:
        return {
            "intel": None,
            "motorola": None,
            "note": "endianness test requires >=16-bit whole bytes",
        }

    start_byte = start_bit // 8
    num_bytes = length // 8

    intel_values = [
        v for p in payloads if (v := _decode_intel(p, start_bit, length)) is not None
    ]
    motorola_values = [
        v
        for p in payloads
        if (v := _decode_motorola_whole_bytes(p, start_byte, num_bytes)) is not None
    ]

    return {
        "start_bit": start_bit,
        "length": length,
        "intel": _series_summary(intel_values),
        "motorola": _series_summary(motorola_values) if motorola_values else None,
    }
