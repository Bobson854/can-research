"""Shared helpers for normalized reference bundles."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CAN_ID_RE = re.compile(r"^0[xX][0-9a-fA-F]+$")
BUNDLE_SCHEMA_VERSION = 1
SQLITE_INTEGER_MIN = -(2**63)
SQLITE_INTEGER_MAX = 2**63 - 1


class BundleFormatError(Exception):
    """Reference bundle format error."""


def load_bundle_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        msg = f"Bundle file not found: {path}"
        raise BundleFormatError(msg)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in bundle {path}: {exc}"
        raise BundleFormatError(msg) from exc
    if not isinstance(payload, dict):
        msg = f"Bundle root must be an object: {path}"
        raise BundleFormatError(msg)
    return payload


def parse_can_id(value: Any, *, field: str, max_value: int = 0x1FFFFFFF) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        msg = f"{field}: boolean is not a valid CAN ID"
        raise BundleFormatError(msg)
    if isinstance(value, int):
        if value < 0 or value > max_value:
            msg = f"{field}: value out of range: {value}"
            raise BundleFormatError(msg)
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if CAN_ID_RE.match(text):
            parsed = int(text, 16)
        elif text.isdigit():
            parsed = int(text)
        else:
            msg = f"{field}: invalid CAN ID {text!r}"
            raise BundleFormatError(msg)
        if parsed < 0 or parsed > max_value:
            msg = f"{field}: value out of range: {text}"
            raise BundleFormatError(msg)
        return parsed
    msg = f"{field}: CAN ID must be integer or hex string"
    raise BundleFormatError(msg)


def parse_mask_value(value: Any, *, field: str) -> int | None:
    """Parse a message-family mask (may use upper bits beyond 29-bit CAN ID)."""
    return parse_can_id(value, field=field, max_value=0xFFFFFFFF)


def parse_mask_pair(pattern: Any, mask: Any, *, field: str) -> tuple[int, int]:
    pattern_id = parse_can_id(pattern, field=f"{field}.pattern")
    mask_id = parse_mask_value(mask, field=f"{field}.mask")
    if pattern_id is None or mask_id is None:
        msg = f"{field}: pattern and mask are required"
        raise BundleFormatError(msg)
    if mask_id == 0:
        msg = f"{field}: mask must not be zero"
        raise BundleFormatError(msg)
    return pattern_id, mask_id


def family_matches(can_id: int, pattern: int, mask: int) -> bool:
    effective_mask = mask & 0x1FFFFFFF
    return (can_id & effective_mask) == (pattern & effective_mask)


def normalize_byte_order(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return "intel" if value == 1 else "motorola"
    text = str(value).strip().lower()
    if text in {"1", "intel", "little", "lsb"}:
        return "intel"
    if text in {"0", "motorola", "big", "msb"}:
        return "motorola"
    msg = f"invalid byte_order {value!r}"
    raise BundleFormatError(msg)


def normalize_signedness(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"signed", "+", "s"}:
        return "signed"
    if text in {"unsigned", "-", "u"}:
        return "unsigned"
    if text in {"unknown", ""}:
        return "unknown"
    msg = f"invalid signedness {value!r}"
    raise BundleFormatError(msg)


def source_location_to_json(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.dumps({"section": value}, separators=(",", ":"))
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    msg = "source_location must be object or string"
    raise BundleFormatError(msg)


def finite_float(value: Any, *, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        msg = f"{field}: invalid number {value!r}"
        raise BundleFormatError(msg) from exc
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        msg = f"{field}: must be finite"
        raise BundleFormatError(msg)
    return parsed


def coerce_storable_integer(value: Any) -> int | None:
    """Return an integer if value would be stored in SQLite INTEGER, else None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.lower().startswith("0x"):
                return int(text, 16)
            return int(text, 10)
        except ValueError:
            return None
    return None


def sqlite_integer_out_of_range(value: int) -> bool:
    return value < SQLITE_INTEGER_MIN or value > SQLITE_INTEGER_MAX
