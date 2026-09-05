"""Reference-value correlation and linear scale/offset inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from canresearch.core.dbc_position import decode_intel_dbc_signal
from canresearch.core.research_frames import PayloadSeries
from canresearch.core.signal_models import ReferenceSample

DEFAULT_ALIGNMENT_TOLERANCE_US = 250_000
MAX_REFERENCE_SAMPLES = 10_000


@dataclass(frozen=True, slots=True)
class AlignedPair:
    timestamp_us: int
    raw_value: float
    reference_value: float


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    pearson: float | None
    sample_count: int
    matched_samples: int
    unmatched_samples: int
    alignment_tolerance_us: int
    raw_min: float | None
    raw_max: float | None
    reference_min: float | None
    reference_max: float | None
    factor: float | None
    offset: float | None
    r_squared: float | None
    pairs: tuple[AlignedPair, ...]

    def to_dict(self, *, include_pairs: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "pearson": round(self.pearson, 4) if self.pearson is not None else None,
            "sample_count": self.sample_count,
            "matched_samples": self.matched_samples,
            "unmatched_samples": self.unmatched_samples,
            "alignment_tolerance_us": self.alignment_tolerance_us,
            "raw_min": self.raw_min,
            "raw_max": self.raw_max,
            "reference_min": self.reference_min,
            "reference_max": self.reference_max,
            "factor": round(self.factor, 6) if self.factor is not None else None,
            "offset": round(self.offset, 6) if self.offset is not None else None,
            "r_squared": round(self.r_squared, 4) if self.r_squared is not None else None,
        }
        if include_pairs:
            result["pairs"] = [
                {
                    "timestamp_us": p.timestamp_us,
                    "raw_value": p.raw_value,
                    "reference_value": p.reference_value,
                }
                for p in self.pairs
            ]
        return result


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float | None]:
    """Return factor, offset, R² for y ≈ factor * x + offset."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, mean_y, None
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    factor = ss_xy / ss_xx
    offset = mean_y - factor * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (factor * x + offset)) ** 2 for x, y in zip(xs, ys, strict=True))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    return factor, offset, r_squared


def align_reference_nearest(
    series: PayloadSeries,
    reference: list[ReferenceSample],
    *,
    tolerance_us: int = DEFAULT_ALIGNMENT_TOLERANCE_US,
    max_reference: int = MAX_REFERENCE_SAMPLES,
) -> tuple[list[AlignedPair], int]:
    """Nearest-neighbor alignment within tolerance (deterministic)."""
    if not series.timestamps_us or not reference:
        return [], len(series.timestamps_us)

    ref = reference[:max_reference]
    ref_sorted = sorted(ref, key=lambda s: s.timestamp_us)
    pairs: list[AlignedPair] = []
    unmatched = 0

    for ts, _payload in zip(series.timestamps_us, series.payloads, strict=True):
        best: ReferenceSample | None = None
        best_delta = tolerance_us + 1
        for sample in ref_sorted:
            delta = abs(sample.timestamp_us - ts)
            if delta < best_delta:
                best_delta = delta
                best = sample
            if sample.timestamp_us > ts + tolerance_us:
                break
        if best is None or best_delta > tolerance_us:
            unmatched += 1
            continue
        pairs.append(
            AlignedPair(
                timestamp_us=ts,
                raw_value=0.0,
                reference_value=best.value,
            )
        )
    return pairs, unmatched


def extract_raw_series(
    series: PayloadSeries,
    *,
    start_bit: int,
    length: int,
    signed: bool = False,
) -> list[tuple[int, int]]:
    """Extract raw field values with timestamps."""
    values: list[tuple[int, int]] = []
    for ts, payload in zip(series.timestamps_us, series.payloads, strict=True):
        try:
            raw = decode_intel_dbc_signal(
                payload,
                start_bit=start_bit,
                bit_length=length,
                signed=signed,
            )
        except ValueError:
            continue
        values.append((ts, raw))
    return values


def correlate_field_with_reference(
    series: PayloadSeries,
    reference: list[ReferenceSample],
    *,
    start_bit: int,
    length: int,
    signed: bool = False,
    tolerance_us: int = DEFAULT_ALIGNMENT_TOLERANCE_US,
) -> CorrelationResult:
    """Correlate a candidate Intel field against a timestamped reference series."""
    raw_points = extract_raw_series(
        series, start_bit=start_bit, length=length, signed=signed
    )
    if not raw_points:
        return CorrelationResult(
            pearson=None,
            sample_count=0,
            matched_samples=0,
            unmatched_samples=len(series.timestamps_us),
            alignment_tolerance_us=tolerance_us,
            raw_min=None,
            raw_max=None,
            reference_min=None,
            reference_max=None,
            factor=None,
            offset=None,
            r_squared=None,
            pairs=(),
        )

    ref_sorted = sorted(reference, key=lambda s: s.timestamp_us)

    aligned: list[AlignedPair] = []
    unmatched = 0
    for ts, raw in raw_points:
        best_val: float | None = None
        best_delta = tolerance_us + 1
        for sample in ref_sorted:
            delta = abs(sample.timestamp_us - ts)
            if delta < best_delta:
                best_delta = delta
                best_val = sample.value
            if sample.timestamp_us > ts + tolerance_us:
                break
        if best_val is None or best_delta > tolerance_us:
            unmatched += 1
            continue
        aligned.append(
            AlignedPair(timestamp_us=ts, raw_value=float(raw), reference_value=best_val)
        )

    if not aligned:
        return CorrelationResult(
            pearson=None,
            sample_count=0,
            matched_samples=0,
            unmatched_samples=unmatched,
            alignment_tolerance_us=tolerance_us,
            raw_min=None,
            raw_max=None,
            reference_min=None,
            reference_max=None,
            factor=None,
            offset=None,
            r_squared=None,
            pairs=(),
        )

    xs = [p.raw_value for p in aligned]
    ys = [p.reference_value for p in aligned]
    pearson = _pearson(xs, ys)
    factor, offset, r_squared = _linear_fit(xs, ys)

    return CorrelationResult(
        pearson=pearson,
        sample_count=len(aligned),
        matched_samples=len(aligned),
        unmatched_samples=unmatched,
        alignment_tolerance_us=tolerance_us,
        raw_min=min(xs),
        raw_max=max(xs),
        reference_min=min(ys),
        reference_max=max(ys),
        factor=factor,
        offset=offset,
        r_squared=r_squared,
        pairs=tuple(aligned),
    )
