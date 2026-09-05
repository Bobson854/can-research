"""Unit tests for checksum detection."""

from __future__ import annotations

from canresearch.core.checksum_detection import detect_checksum_candidates


def _xor_body(payload: bytes, checksum_byte: int) -> bytes:
    body = bytes(payload[i] for i in range(8) if i != checksum_byte)
    checksum = 0
    for byte in body:
        checksum ^= byte
    result = bytearray(payload)
    result[checksum_byte] = checksum & 0xFF
    return bytes(result)


def test_xor8_detected() -> None:
    payloads = []
    for i in range(15):
        base = bytes([i, 0, i + 1, i + 2, 0, 0, 0, 0])
        payloads.append(_xor_body(base, checksum_byte=1))
    candidates = detect_checksum_candidates(payloads)
    assert any(c.algorithm == "xor8" and c.checksum_byte == 1 for c in candidates)


def test_sum8_detected() -> None:
    payloads = []
    for i in range(15):
        body = bytes([i, 0, 1, 2, 3, 0, 0, 0])
        total = sum(body[j] for j in range(8) if j != 1) & 0xFF
        row = bytearray(body)
        row[1] = total
        payloads.append(bytes(row))
    candidates = detect_checksum_candidates(payloads)
    assert any(c.algorithm == "sum8" for c in candidates)
