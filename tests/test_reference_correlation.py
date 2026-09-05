"""Unit tests for reference correlation and scale inference."""

from __future__ import annotations

from canresearch.core.reference_correlation import correlate_field_with_reference
from canresearch.core.research_frames import PayloadSeries
from canresearch.core.signal_models import ReferenceSample
from tests.fixtures.synthetic_proprietary import build_payload


def test_linear_correlation_exact() -> None:
    payloads = []
    timestamps = []
    reference = []
    for i in range(50):
        ts = i * 100_000
        raw = 1000 + i * 10
        payloads.append(build_payload(counter=i, pressure_raw=raw, action_on=False))
        timestamps.append(ts)
        reference.append(ReferenceSample(timestamp_us=ts, value=raw * 0.1))

    series = PayloadSeries(
        can_id=0x18FF748A,
        timestamps_us=tuple(timestamps),
        payloads=tuple(payloads),
        pgn=65396,
        source_address=138,
        destination_address=None,
    )
    result = correlate_field_with_reference(
        series,
        reference,
        start_bit=16,
        length=16,
        tolerance_us=50_000,
    )
    assert result.sample_count >= 40
    assert result.pearson is not None and result.pearson > 0.99
    assert result.factor is not None and abs(result.factor - 0.1) < 0.01
    assert result.r_squared is not None and result.r_squared > 0.99


def test_poor_correlation() -> None:
    payloads = [
        build_payload(counter=i, pressure_raw=1000, action_on=i % 2 == 0) for i in range(30)
    ]
    timestamps = [i * 100_000 for i in range(30)]
    reference = [
        ReferenceSample(timestamp_us=ts, value=float(i * 17))
        for i, ts in enumerate(timestamps)
    ]
    series = PayloadSeries(
        can_id=0x100,
        timestamps_us=tuple(timestamps),
        payloads=tuple(payloads),
        pgn=None,
        source_address=None,
        destination_address=None,
    )
    result = correlate_field_with_reference(
        series,
        reference,
        start_bit=32,
        length=1,
        tolerance_us=50_000,
    )
    assert result.pearson is None or abs(result.pearson) < 0.9


def test_alignment_tolerance() -> None:
    payloads = [build_payload(counter=0, pressure_raw=1000, action_on=False)]
    series = PayloadSeries(
        can_id=0x18FF748A,
        timestamps_us=(1_000_000,),
        payloads=(payloads[0],),
        pgn=None,
        source_address=None,
        destination_address=None,
    )
    ref = [ReferenceSample(timestamp_us=1_500_000, value=100.0)]
    result = correlate_field_with_reference(
        series,
        ref,
        start_bit=16,
        length=16,
        tolerance_us=100_000,
    )
    assert result.matched_samples == 0
    assert result.unmatched_samples == 1
