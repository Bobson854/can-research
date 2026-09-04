"""Typed models for reference catalogue import and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ReferenceOrigin(StrEnum):
    J1939_BASE_2001 = "j1939_base_2001"
    J1939_ADDITION = "j1939_addition"
    ISOBUS_ADDITION = "isobus_addition"


class IssueSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(slots=True)
class ParsedSpn:
    spn: int
    name: str
    definition: str | None = None
    description: str | None = None
    data_length_bits: int | None = None
    data_length_text: str | None = None
    resolution: str | None = None
    offset: str | None = None
    minimum: str | None = None
    maximum: str | None = None
    unit: str | None = None
    data_type: str | None = None
    status: str | None = None
    source_page: int | None = None
    raw_text: str | None = None
    pgns: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ParsedPgnSpnMapping:
    spn: int
    position_order: int | None = None
    start_byte: int | None = None
    start_bit: int | None = None
    bit_length: int | None = None
    byte_order: str | None = None
    raw_position_text: str | None = None
    spn_description: str | None = None
    length_text: str | None = None
    source_page: int | None = None


@dataclass(slots=True)
class ParsedPgn:
    pgn: int
    name: str
    acronym: str | None = None
    description: str | None = None
    transmission_rate: str | None = None
    payload_length: int | None = None
    default_priority: int | None = None
    data_page: int | None = None
    pdu_format: int | None = None
    pdu_specific: int | None = None
    source_page: int | None = None
    raw_text: str | None = None
    mappings: list[ParsedPgnSpnMapping] = field(default_factory=list)


@dataclass(slots=True)
class ParsedDdi:
    ddi: int
    name: str
    definition: str | None = None
    comment: str | None = None
    unit_symbol: str | None = None
    unit_description: str | None = None
    resolution: str | None = None
    can_min: str | None = None
    can_max: str | None = None
    display_min: str | None = None
    display_max: str | None = None
    sae_spn: int | None = None
    submit_by: str | None = None
    submit_date: str | None = None
    submit_company: str | None = None
    revision_number: int | None = None
    current_status: str | None = None
    status_date: str | None = None
    status_comments: str | None = None
    device_classes: list[tuple[int, str | None]] = field(default_factory=list)
    source_page: int | None = None
    raw_text: str | None = None


@dataclass(slots=True)
class ImportReport:
    source_key: str
    source_path: str | None = None
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    spns_parsed: int = 0
    pgns_parsed: int = 0
    mappings_parsed: int = 0
    ddis_parsed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.errors)


@dataclass(slots=True)
class ValidationIssue:
    severity: IssueSeverity
    category: str
    message: str
    pgn: int | None = None
    spn: int | None = None
    ddi: int | None = None
    source_id: int | None = None


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.INFO]
