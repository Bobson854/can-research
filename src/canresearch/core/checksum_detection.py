"""Deterministic checksum heuristics for CAN payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChecksumCandidate:
    algorithm: str
    checksum_byte: int
    match_ratio: float
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "checksum_byte": self.checksum_byte,
            "match_ratio": round(self.match_ratio, 4),
            "sample_count": self.sample_count,
        }


def _xor8(data: bytes) -> int:
    result = 0
    for byte in data:
        result ^= byte
    return result & 0xFF


def _sum8(data: bytes) -> int:
    return sum(data) & 0xFF


def _twos_complement_sum8(data: bytes) -> int:
    return (-sum(data)) & 0xFF


_ALGORITHMS = {
    "xor8": _xor8,
    "sum8": _sum8,
    "twos_complement_sum8": _twos_complement_sum8,
}


def detect_checksum_candidates(
    payloads: list[bytes],
    *,
    max_candidates: int = 32,
    min_match_ratio: float = 0.95,
) -> list[ChecksumCandidate]:
    """Try common checksum algorithms at each payload byte position."""
    if len(payloads) < 2:
        return []

    candidates: list[ChecksumCandidate] = []
    for checksum_byte in range(8):
        for algorithm, fn in _ALGORITHMS.items():
            matches = 0
            for payload in payloads:
                body = bytes(payload[index] for index in range(8) if index != checksum_byte)
                expected = fn(body)
                if payload[checksum_byte] == expected:
                    matches += 1
            ratio = matches / len(payloads)
            if ratio >= min_match_ratio:
                candidates.append(
                    ChecksumCandidate(
                        algorithm=algorithm,
                        checksum_byte=checksum_byte,
                        match_ratio=ratio,
                        sample_count=len(payloads),
                    )
                )

    candidates.sort(key=lambda c: (-c.match_ratio, c.checksum_byte))
    return candidates[:max_candidates]
