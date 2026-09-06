"""DBC knowledge source metadata and loaded library models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from canresearch.core.dbc_model import DbcDatabase

DbcSourceType = Literal[
    "user_supplied",
    "oem",
    "supplier",
    "standard",
    "confirmed_research",
]

VALID_DBC_SOURCE_TYPES: frozenset[str] = frozenset(
    {"user_supplied", "oem", "supplier", "standard", "confirmed_research"}
)


@dataclass(frozen=True, slots=True)
class DbcSourceMeta:
    """Registered or discovered DBC knowledge source (metadata only)."""

    key: str
    display_name: str
    path: str
    source_type: str
    asset_key: str | None = None
    message_count: int | None = None
    signal_count: int | None = None


@dataclass(frozen=True, slots=True)
class DbcLoadWarning:
    category: str
    message: str
    line_number: int | None = None


@dataclass(frozen=True, slots=True)
class LoadedDbcSource:
    """Parsed DBC knowledge source ready for lookup and coverage."""

    meta: DbcSourceMeta
    database: DbcDatabase
    warnings: tuple[DbcLoadWarning, ...] = field(default_factory=tuple)


class DbcKnowledgeError(Exception):
    """Base error for DBC library operations."""


class DbcSourceNotFoundError(DbcKnowledgeError):
    """Requested DBC source key does not exist."""


class DbcLoadError(DbcKnowledgeError):
    """DBC file could not be parsed or validated."""
