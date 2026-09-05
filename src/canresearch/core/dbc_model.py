"""Internal DBC representation for session-backed generation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DbcProvenance:
    """Metadata describing how and for which asset a DBC was generated."""

    asset_key: str
    asset_id: str
    session_id: str
    dbc_type: str
    reference_origins: tuple[str, ...]
    generator_version: str
    generated_at: str
    source_addresses: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DbcSignal:
    name: str
    start_bit: int
    bit_length: int
    byte_order: int  # 0 = Motorola, 1 = Intel
    signed: bool
    factor: float
    offset: float
    minimum: float
    maximum: float
    unit: str
    pgn: int
    spn: int
    origin: str
    reference_backed: bool = True


@dataclass(frozen=True, slots=True)
class DbcMessage:
    name: str
    can_id: int
    dbc_frame_id: int
    dlc: int
    transmitter: str
    pgn: int
    source_address: int
    destination_address: int | None
    origin: str
    signals: tuple[DbcSignal, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DbcDatabase:
    version: str
    nodes: tuple[str, ...]
    messages: tuple[DbcMessage, ...] = field(default_factory=tuple)
    provenance: DbcProvenance | None = None
    comments: tuple[str, ...] = field(default_factory=tuple)
