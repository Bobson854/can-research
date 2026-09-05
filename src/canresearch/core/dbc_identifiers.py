"""Sanitise identifiers for strict DBC compatibility."""

from __future__ import annotations

import re

_INVALID_CHARS = re.compile(r"[^A-Za-z0-9_]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


def sanitize_dbc_identifier(name: str, *, prefix_if_digit: str = "CAN") -> str:
    """Return a conservative DBC identifier (letters, digits, underscores only)."""
    cleaned = _INVALID_CHARS.sub("_", name.strip())
    cleaned = _MULTI_UNDERSCORE.sub("_", cleaned).strip("_")
    if not cleaned:
        return "Unnamed"
    if cleaned[0].isdigit():
        cleaned = f"{prefix_if_digit}{cleaned}"
    return cleaned


def unique_signal_identifier(base: str, spn: int, used: set[str]) -> str:
    """Resolve duplicate signal names within one message deterministically."""
    candidate = sanitize_dbc_identifier(base)
    if candidate not in used:
        used.add(candidate)
        return candidate

    with_spn = sanitize_dbc_identifier(f"{base}_SPN{spn}")
    if with_spn not in used:
        used.add(with_spn)
        return with_spn

    suffix = 2
    while True:
        candidate = sanitize_dbc_identifier(f"{base}_SPN{spn}_{suffix}")
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1
