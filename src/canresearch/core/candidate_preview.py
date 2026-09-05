"""Bounded preview of candidate field values from stored session frames."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canresearch.core.dbc_position import (
    decode_intel_dbc_signal,
    decode_motorola_dbc_signal,
    validate_classic_payload_field,
)
from canresearch.core.research_candidates import ResearchCandidateError
from canresearch.core.research_frames import (
    format_can_id,
    load_session_frames,
    normalize_payload,
    sample_deterministic,
)
from canresearch.core.sessions import CanFrame

DEFAULT_PREVIEW_LIMIT = 50
MAX_PREVIEW_LIMIT = 200


def _validate_signedness(signedness: str) -> bool:
    value = signedness.strip().lower()
    if value == "signed":
        return True
    if value == "unsigned":
        return False
    msg = f"signedness must be 'signed' or 'unsigned', got {signedness!r}"
    raise ResearchCandidateError("invalid_field_definition", msg)


def _validate_byte_order(byte_order: str) -> str:
    value = byte_order.strip().lower()
    if value in {"intel", "motorola"}:
        return value
    msg = f"byte_order must be 'intel' or 'motorola', got {byte_order!r}"
    raise ResearchCandidateError("invalid_field_definition", msg)


def _validate_scale(
    factor: float | None,
    offset: float | None,
) -> tuple[float | None, float | None]:
    if factor is None and offset is None:
        return None, None
    if factor is None or offset is None:
        raise ResearchCandidateError(
            "invalid_field_definition",
            "factor and offset must both be supplied when scaling is requested",
        )
    return factor, offset


def _decode_field_value(
    payload: bytes,
    *,
    start_bit: int,
    bit_length: int,
    byte_order: str,
    signed: bool,
) -> int:
    if byte_order == "intel":
        return decode_intel_dbc_signal(
            payload,
            start_bit=start_bit,
            bit_length=bit_length,
            signed=signed,
        )
    return decode_motorola_dbc_signal(
        payload,
        start_bit=start_bit,
        bit_length=bit_length,
        signed=signed,
    )


def _filter_matching_frames(
    frames: list[CanFrame],
    *,
    can_id: int,
    is_extended: bool,
) -> list[CanFrame]:
    return [
        frame
        for frame in frames
        if not frame.is_error_frame
        and frame.can_id == can_id
        and frame.is_extended == is_extended
    ]


def preview_candidate_field_values(
    session_id: str,
    *,
    can_id: int,
    is_extended: bool,
    start_bit: int,
    bit_length: int,
    byte_order: str,
    signedness: str,
    factor: float | None = None,
    offset: float | None = None,
    limit: int = DEFAULT_PREVIEW_LIMIT,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Preview raw (and optional scaled) values for a proposed field in a session."""
    if limit <= 0 or limit > MAX_PREVIEW_LIMIT:
        raise ResearchCandidateError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_PREVIEW_LIMIT}, got {limit}",
        )

    byte_order_value = _validate_byte_order(byte_order)
    signed = _validate_signedness(signedness)
    scale_factor, scale_offset = _validate_scale(factor, offset)

    try:
        validate_classic_payload_field(
            start_bit=start_bit,
            bit_length=bit_length,
            byte_order=byte_order_value,
        )
    except ValueError as exc:
        raise ResearchCandidateError("invalid_field_definition", str(exc)) from exc

    frames = load_session_frames(session_id, db_path=db_path)
    matching = _filter_matching_frames(frames, can_id=can_id, is_extended=is_extended)

    decoded: list[tuple[int, int]] = []
    for frame in matching:
        payload = normalize_payload(frame.data, frame.dlc)
        try:
            raw = _decode_field_value(
                payload,
                start_bit=start_bit,
                bit_length=bit_length,
                byte_order=byte_order_value,
                signed=signed,
            )
        except ValueError:
            continue
        decoded.append((frame.timestamp_us, raw))

    matching_frame_count = len(matching)
    raw_values = [value for _, value in decoded]
    raw_change_count = sum(
        1 for index in range(1, len(raw_values)) if raw_values[index] != raw_values[index - 1]
    )
    change_rate = (
        round(raw_change_count / (len(raw_values) - 1), 4) if len(raw_values) > 1 else 0.0
    )

    sampled_pairs = sample_deterministic(decoded, limit)
    samples: list[dict[str, Any]] = []
    for timestamp_us, raw in sampled_pairs:
        entry: dict[str, Any] = {
            "timestamp_us": timestamp_us,
            "raw": raw,
        }
        if scale_factor is not None and scale_offset is not None:
            entry["scaled"] = raw * scale_factor + scale_offset
        samples.append(entry)

    scaled_min: float | None = None
    scaled_max: float | None = None
    if scale_factor is not None and scale_offset is not None and raw_values:
        scaled_values = [raw * scale_factor + scale_offset for raw in raw_values]
        scaled_min = min(scaled_values)
        scaled_max = max(scaled_values)

    return {
        "session_id": session_id,
        "can_id": can_id,
        "can_id_hex": format_can_id(can_id),
        "is_extended": is_extended,
        "field": {
            "start_bit": start_bit,
            "bit_length": bit_length,
            "byte_order": byte_order_value,
            "signedness": signedness.strip().lower(),
            "factor": scale_factor,
            "offset": scale_offset,
        },
        "matching_frame_count": matching_frame_count,
        "sampled_value_count": len(samples),
        "raw_min": min(raw_values) if raw_values else None,
        "raw_max": max(raw_values) if raw_values else None,
        "raw_unique_count": len(set(raw_values)),
        "raw_change_count": raw_change_count,
        "change_rate": change_rate,
        "scaled_min": scaled_min,
        "scaled_max": scaled_max,
        "samples": samples,
    }
