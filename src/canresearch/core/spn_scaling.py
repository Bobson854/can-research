"""Normalize J1939 SPN resolution/offset text into numeric scaling factors."""

from __future__ import annotations

import re

PER_BIT_RE = re.compile(
    r"(-?\d+(?:\.\d+)?).*?(?:per|/)\s*bit",
    re.IGNORECASE,
)
UNITY_RE = re.compile(r"^1(?:\s*(?:count|unit))?/bit\b", re.IGNORECASE)
BINARY_STATE_RE = re.compile(r"^\d+\s*bit(s)?\s*/\s*bit", re.IGNORECASE)


def parse_numeric(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = text.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_scaling(
    resolution: str | None,
    offset: str | None,
    unit: str | None,
) -> tuple[float | None, float, str | None, str | None]:
    """Parse catalogue scaling fields into (factor, offset, unit, error).

    Returns factor=None when scaling cannot be determined reliably.
    """
    parsed_offset = parse_numeric(offset) or 0.0
    parsed_unit = unit.strip() if unit and unit.strip() else None

    if not resolution or not resolution.strip():
        return None, parsed_offset, parsed_unit, "missing resolution"

    text = " ".join(resolution.split())

    if UNITY_RE.match(text) or BINARY_STATE_RE.match(text):
        return 1.0, parsed_offset, parsed_unit, None

    match = PER_BIT_RE.search(text)
    if match:
        factor = parse_numeric(match.group(1))
        if factor is None:
            return None, parsed_offset, parsed_unit, f"unparseable resolution: {text!r}"
        if parsed_unit is None:
            unit_match = re.search(r"/\s*([A-Za-z][\w/.-]*)", text)
            if unit_match:
                parsed_unit = unit_match.group(1).strip()
        return factor, parsed_offset, parsed_unit, None

    return None, parsed_offset, parsed_unit, f"unsupported resolution format: {text!r}"
