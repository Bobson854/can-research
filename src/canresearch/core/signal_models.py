"""Data models for proprietary signal research candidates (evidence only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SignednessCandidate = Literal["unsigned", "signed", "unknown"]
ByteOrderCandidate = Literal["intel", "motorola"]


@dataclass
class SignalCandidate:
    """On-demand candidate field evidence — not a confirmed signal."""

    can_id: str
    start_bit: int
    length: int
    byte_order: ByteOrderCandidate = "intel"
    signedness: SignednessCandidate = "unknown"
    pgn: int | None = None
    source_address: int | None = None
    destination_address: int | None = None
    asset_key: str | None = None
    raw_min: int | None = None
    raw_max: int | None = None
    unique_values: int | None = None
    activity_score: float | None = None
    rank: int | None = None
    repeat_consistency: float | None = None
    counter_likelihood: float | None = None
    checksum_likelihood: float | None = None
    correlation: float | None = None
    factor: float | None = None
    offset: float | None = None
    r_squared: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_id": self.can_id,
            "pgn": self.pgn,
            "source_address": self.source_address,
            "destination_address": self.destination_address,
            "asset_key": self.asset_key,
            "start_bit": self.start_bit,
            "length": self.length,
            "byte_order": self.byte_order,
            "signedness": self.signedness,
            "raw_min": self.raw_min,
            "raw_max": self.raw_max,
            "unique_values": self.unique_values,
            "activity_score": self.activity_score,
            "rank": self.rank,
            "repeat_consistency": self.repeat_consistency,
            "counter_likelihood": self.counter_likelihood,
            "checksum_likelihood": self.checksum_likelihood,
            "correlation": self.correlation,
            "factor": self.factor,
            "offset": self.offset,
            "r_squared": self.r_squared,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class ReferenceSample:
    timestamp_us: int
    value: float
