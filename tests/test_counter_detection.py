"""Unit tests for counter detection."""

from __future__ import annotations

from canresearch.core.counter_detection import detect_counter_candidates


def test_8bit_counter_wrap() -> None:
    payloads = [bytes([(250 + i) % 256, 0, 0, 0, 0, 0, 0, 0]) for i in range(20)]
    candidates = detect_counter_candidates(payloads)
    match = next(c for c in candidates if c.byte_index == 0 and c.modulus == 256)
    assert match.wrap_count >= 1


def test_nibble_counter() -> None:
    payloads = []
    nibble = 0
    for _ in range(20):
        payloads.append(bytes([nibble, 0, 0, 0, 0, 0, 0, 0]))
        nibble = (nibble + 1) % 16
    candidates = detect_counter_candidates(payloads)
    assert any("4-bit-low" in c.field_type for c in candidates)


def test_static_byte_not_counter() -> None:
    payloads = [bytes([5, 0, 0, 0, 0, 0, 0, 0]) for _ in range(10)]
    candidates = detect_counter_candidates(payloads, min_match_ratio=0.95)
    assert not any(c.byte_index == 0 and c.is_counter_candidate for c in candidates)
