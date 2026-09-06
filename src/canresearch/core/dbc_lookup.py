"""Lookup helpers over loaded DBC knowledge sources."""

from __future__ import annotations

from dataclasses import dataclass

from canresearch.core.dbc_knowledge import DbcKnowledgeError, LoadedDbcSource
from canresearch.core.dbc_model import DbcMessage, DbcSignal


@dataclass(frozen=True, slots=True)
class DbcMessageMatch:
    source_key: str
    message: DbcMessage


@dataclass(frozen=True, slots=True)
class DbcSignalMatch:
    source_key: str
    message: DbcMessage
    signal: DbcSignal


class DbcLookupError(DbcKnowledgeError):
    """Lookup miss or ambiguity."""


def _frame_key(is_extended: bool, can_id: int) -> tuple[bool, int]:
    return is_extended, can_id


def lookup_message_by_can_id(
    sources: tuple[LoadedDbcSource, ...],
    *,
    can_id: int,
    is_extended: bool,
) -> tuple[DbcMessageMatch, ...]:
    """Exact CAN ID lookup across sources (may return multiple)."""
    key = _frame_key(is_extended, can_id)
    matches: list[DbcMessageMatch] = []
    for source in sources:
        for message in source.database.messages:
            msg_extended = message.dbc_frame_id >= 0x80000000 or message.can_id > 0x7FF
            if _frame_key(msg_extended, message.can_id) == key:
                matches.append(DbcMessageMatch(source_key=source.meta.key, message=message))
    return tuple(matches)


def lookup_message_by_name(
    sources: tuple[LoadedDbcSource, ...],
    message_name: str,
) -> tuple[DbcMessageMatch, ...]:
    cleaned = message_name.strip()
    matches: list[DbcMessageMatch] = []
    for source in sources:
        for message in source.database.messages:
            if message.name == cleaned:
                matches.append(DbcMessageMatch(source_key=source.meta.key, message=message))
    return tuple(matches)


def lookup_signal_by_name(
    sources: tuple[LoadedDbcSource, ...],
    signal_name: str,
) -> tuple[DbcSignalMatch, ...]:
    cleaned = signal_name.strip()
    matches: list[DbcSignalMatch] = []
    for source in sources:
        for message in source.database.messages:
            for signal in message.signals:
                if signal.name == cleaned:
                    matches.append(
                        DbcSignalMatch(
                            source_key=source.meta.key,
                            message=message,
                            signal=signal,
                        )
                    )
    return tuple(matches)


def lookup_signals_for_can_id(
    sources: tuple[LoadedDbcSource, ...],
    *,
    can_id: int,
    is_extended: bool,
) -> tuple[DbcSignalMatch, ...]:
    matches: list[DbcSignalMatch] = []
    for item in lookup_message_by_can_id(sources, can_id=can_id, is_extended=is_extended):
        for signal in item.message.signals:
            matches.append(
                DbcSignalMatch(
                    source_key=item.source_key,
                    message=item.message,
                    signal=signal,
                )
            )
    return tuple(matches)
