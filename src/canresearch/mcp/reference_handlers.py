"""MCP handlers for reference source registry and bundle knowledge."""

from __future__ import annotations

from typing import Any

from canresearch.mcp.errors import McpToolError
from canresearch.mcp.limits import (
    DEFAULT_REFERENCE_SEARCH_LIMIT,
    MAX_LIST_REFERENCE_SOURCES,
    MAX_REFERENCE_SEARCH_LIMIT,
    clamp_limit,
)
from canresearch.references.bundle_knowledge import (
    knowledge_stats,
    lookup_message_by_can_id,
    lookup_message_by_pgn,
    lookup_message_families_by_can_id,
    lookup_signals_for_message,
    search_reference_knowledge,
)
from canresearch.references.source_registry import (
    ReferenceSourceNotFoundError,
    ReferenceSourceRegistryError,
    get_reference_source,
    list_reference_sources,
)
from canresearch.storage.database import default_db_path, initialize


def _source_meta(record: Any) -> dict[str, Any]:
    return {
        "key": record.key,
        "display_name": record.display_name,
        "source_type": record.source_type,
        "visibility": record.visibility,
        "original_filename": record.original_filename,
        "vendor": record.vendor,
        "version": record.version,
        "document_date": record.document_date,
        "registered_at": record.registered_at,
        "notes": record.notes,
    }


def handle_list_reference_sources() -> dict[str, Any]:
    try:
        records = list_reference_sources()
    except ReferenceSourceRegistryError as exc:
        raise McpToolError("reference_source_error", str(exc)) from exc
    limited = records[:MAX_LIST_REFERENCE_SOURCES]
    return {
        "sources": [_source_meta(record) for record in limited],
        "count": len(limited),
        "total": len(records),
    }


def handle_inspect_reference_source(*, source_key: str) -> dict[str, Any]:
    try:
        record = get_reference_source(source_key)
    except ReferenceSourceNotFoundError as exc:
        raise McpToolError("reference_source_not_found", str(exc)) from exc
    conn = initialize(default_db_path())
    try:
        stats = knowledge_stats(conn, source_key=source_key)
    finally:
        conn.close()
    payload = _source_meta(record)
    payload["imported_knowledge"] = stats
    return payload


def handle_search_reference_knowledge(
    *,
    query: str,
    source_key: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    bounded = clamp_limit(limit, DEFAULT_REFERENCE_SEARCH_LIMIT, MAX_REFERENCE_SEARCH_LIMIT)
    conn = initialize(default_db_path())
    try:
        return search_reference_knowledge(
            conn,
            query=query,
            source_key=source_key,
            limit=bounded,
        )
    finally:
        conn.close()


def handle_lookup_reference_message(
    *,
    can_id: int | None = None,
    is_extended: bool | None = None,
    pgn: int | None = None,
    source_key: str | None = None,
) -> dict[str, Any]:
    if can_id is None and pgn is None:
        raise McpToolError(
            "invalid_arguments",
            "Provide can_id or pgn",
        )
    conn = initialize(default_db_path())
    try:
        exact: list[dict[str, Any]] = []
        families: list[dict[str, Any]] = []
        if can_id is not None:
            ext = bool(is_extended) if is_extended is not None else can_id > 0x7FF
            exact = lookup_message_by_can_id(
                conn,
                can_id=can_id,
                is_extended=ext,
                source_key=source_key,
            )
            families = lookup_message_families_by_can_id(
                conn,
                can_id=can_id,
                source_key=source_key,
            )
            for message in exact:
                message["match_type"] = "exact_can_id"
                message["signals"] = lookup_signals_for_message(
                    conn,
                    source_key=message["source_key"],
                    message_object_key=message["object_key"],
                )
        if pgn is not None:
            pgn_rows = lookup_message_by_pgn(conn, pgn=pgn, source_key=source_key)
            for row in pgn_rows:
                row["match_type"] = "pgn"
                row["signals"] = lookup_signals_for_message(
                    conn,
                    source_key=row["source_key"],
                    message_object_key=row["object_key"],
                )
            exact.extend(pgn_rows)
        return {
            "can_id": can_id,
            "is_extended": is_extended,
            "pgn": pgn,
            "exact_matches": exact,
            "family_matches": families,
            "match_count": len(exact) + len(families),
        }
    finally:
        conn.close()
