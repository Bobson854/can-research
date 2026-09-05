"""Tests for J1939 SPN scaling normalization."""

from __future__ import annotations

from canresearch.core.spn_scaling import parse_scaling


def test_parse_rpm_per_bit() -> None:
    factor, offset, unit, error = parse_scaling("0.125 rpm per bit", "0", "rpm")
    assert error is None
    assert factor == 0.125
    assert offset == 0.0
    assert unit == "rpm"


def test_parse_unity_resolution() -> None:
    factor, offset, unit, error = parse_scaling("1 unit/bit, 0 offset", None, None)
    assert error is None
    assert factor == 1.0
    assert offset == 0.0


def test_parse_degree_per_bit() -> None:
    factor, offset, unit, error = parse_scaling("1 deg C per bit", "-40", "deg C")
    assert error is None
    assert factor == 1.0
    assert offset == -40.0
    assert unit == "deg C"


def test_parse_unsupported_resolution() -> None:
    factor, _, _, error = parse_scaling("variable", None, None)
    assert factor is None
    assert error is not None
