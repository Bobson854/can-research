"""Deterministic counter pattern detection in CAN payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CounterCandidate:
    byte_index: int
    is_counter_candidate: bool
    modulus: int
    step: int
    wrap_count: int
    match_ratio: float
    sample_count: int
    field_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "byte_index": self.byte_index,
            "is_counter_candidate": self.is_counter_candidate,
            "modulus": self.modulus,
            "step": self.step,
            "wrap_count": self.wrap_count,
            "match_ratio": round(self.match_ratio, 4),
            "sample_count": self.sample_count,
            "field_type": self.field_type,
        }


def _extract_nibble(value: int, *, high: bool) -> int:
    return (value >> 4) & 0xF if high else value & 0xF


def _score_increment_series(values: list[int], *, modulus: int, step: int) -> tuple[float, int]:
    if len(values) < 3:
        return 0.0, 0
    matches = 0
    wraps = 0
    total = len(values) - 1
    for index in range(1, len(values)):
        prev = values[index - 1]
        curr = values[index]
        expected = (prev + step) % modulus
        if curr == expected:
            matches += 1
            if prev + step >= modulus:
                wraps += 1
    return matches / total, wraps


def detect_counter_candidates(
    payloads: list[bytes],
    *,
    max_candidates: int = 32,
    min_match_ratio: float = 0.85,
) -> list[CounterCandidate]:
    """Detect bounded counter patterns in a payload series."""
    if len(payloads) < 3:
        return []

    candidates: list[CounterCandidate] = []

    for byte_index in range(8):
        byte_values = [payload[byte_index] for payload in payloads]
        match_ratio, wraps = _score_increment_series(byte_values, modulus=256, step=1)
        if match_ratio >= min_match_ratio:
            candidates.append(
                CounterCandidate(
                    byte_index=byte_index,
                    is_counter_candidate=True,
                    modulus=256,
                    step=1,
                    wrap_count=wraps,
                    match_ratio=match_ratio,
                    sample_count=len(byte_values),
                    field_type="8-bit",
                )
            )

        for high in (True, False):
            nibble_values = [_extract_nibble(v, high=high) for v in byte_values]
            n_match, n_wraps = _score_increment_series(nibble_values, modulus=16, step=1)
            if n_match >= min_match_ratio:
                candidates.append(
                    CounterCandidate(
                        byte_index=byte_index,
                        is_counter_candidate=True,
                        modulus=16,
                        step=1,
                        wrap_count=n_wraps,
                        match_ratio=n_match,
                        sample_count=len(nibble_values),
                        field_type="4-bit-high" if high else "4-bit-low",
                    )
                )

        for shift in (0, 2, 4, 6):
            two_bit = [(v >> shift) & 0x3 for v in byte_values]
            t_match, t_wraps = _score_increment_series(two_bit, modulus=4, step=1)
            if t_match >= min_match_ratio:
                candidates.append(
                    CounterCandidate(
                        byte_index=byte_index,
                        is_counter_candidate=True,
                        modulus=4,
                        step=1,
                        wrap_count=t_wraps,
                        match_ratio=t_match,
                        sample_count=len(two_bit),
                        field_type=f"2-bit@{shift}",
                    )
                )

    candidates.sort(key=lambda c: (-c.match_ratio, c.byte_index))
    return candidates[:max_candidates]
