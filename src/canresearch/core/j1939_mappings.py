"""Shared J1939 PGN-SPN mapping spec loading for decode and DBC generation."""

from __future__ import annotations

from dataclasses import dataclass

from canresearch.core.spn_bits import normalize_byte_order
from canresearch.core.spn_scaling import parse_scaling
from canresearch.references.service import ReferenceService


@dataclass(frozen=True, slots=True)
class MappingWarning:
    category: str
    message: str
    pgn: int | None = None
    spn: int | None = None


@dataclass(frozen=True, slots=True)
class MappingSpec:
    spn: int
    spn_name: str | None
    start_byte: int
    start_bit: int | None
    bit_length: int
    byte_order: str
    signed: bool
    factor: float
    offset: float
    unit: str | None
    origin: str
    source_id: int
    raw_position_text: str | None
    minimum: str | None = None
    maximum: str | None = None


def infer_signed(data_type: str | None) -> bool | None:
    if not data_type:
        return False
    lowered = data_type.lower()
    if "signed" in lowered:
        return True
    if lowered in {"measured", "status", "identifier", "binary"}:
        return False
    return None


def mapping_spec_from_row(row, pgn: int) -> tuple[MappingSpec | None, MappingWarning | None]:
    spn = int(row["spn"])
    start_byte = row["start_byte"]
    bit_length = row["bit_length"]
    if start_byte is None or bit_length is None:
        return None, MappingWarning(
            category="incomplete_mapping",
            message=f"SPN {spn} missing start_byte or bit_length",
            pgn=pgn,
            spn=spn,
        )

    byte_order = normalize_byte_order(row["byte_order"], default_intel=True)
    if byte_order is None:
        return None, MappingWarning(
            category="unknown_byte_order",
            message=f"SPN {spn} byte order is unknown",
            pgn=pgn,
            spn=spn,
        )

    signedness = infer_signed(row["data_type"])
    if signedness is None:
        return None, MappingWarning(
            category="unknown_signedness",
            message=f"SPN {spn} signedness cannot be determined from data_type",
            pgn=pgn,
            spn=spn,
        )

    factor, offset, unit, scale_error = parse_scaling(
        row["resolution"],
        row["offset"],
        row["unit"],
    )
    if factor is None:
        return None, MappingWarning(
            category="missing_scaling",
            message=scale_error or f"SPN {spn} scaling unavailable",
            pgn=pgn,
            spn=spn,
        )

    start_bit = row["start_bit"]
    if start_bit is not None and (start_bit < 1 or start_bit > 8):
        return None, MappingWarning(
            category="invalid_start_bit",
            message=f"SPN {spn} has invalid start_bit {start_bit}",
            pgn=pgn,
            spn=spn,
        )

    return MappingSpec(
        spn=spn,
        spn_name=row["spn_name"],
        start_byte=int(start_byte),
        start_bit=int(start_bit) if start_bit is not None else None,
        bit_length=int(bit_length),
        byte_order=byte_order,
        signed=signedness,
        factor=factor,
        offset=offset,
        unit=unit,
        origin=str(row["origin"]),
        source_id=int(row["source_id"]),
        raw_position_text=row["raw_position_text"],
        minimum=row["minimum"],
        maximum=row["maximum"],
    ), None


def load_pgn_mapping_specs(
    service: ReferenceService,
    pgn: int,
    origin: str,
) -> tuple[tuple[MappingSpec, ...], tuple[MappingWarning, ...]]:
    rows = service.pgn_decode_mappings(pgn, origin)
    if not rows:
        return (), (
            MappingWarning(
                category="missing_mappings",
                message=f"No PGN-SPN mappings for known PGN {pgn} ({origin})",
                pgn=pgn,
            ),
        )

    specs: list[MappingSpec] = []
    warnings: list[MappingWarning] = []
    for row in rows:
        spec, warning = mapping_spec_from_row(row, pgn)
        if warning:
            warnings.append(warning)
        elif spec is not None:
            specs.append(spec)

    return tuple(specs), tuple(warnings)
