"""Read-only MCP handlers for persisted research candidates and research DBC preview."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canresearch.core.research_candidates import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    ResearchCandidateError,
    candidate_to_dict,
    get_research_candidate,
    list_candidate_evidence,
    list_research_candidates,
)
from canresearch.core.research_dbc import preview_research_dbc_text
from canresearch.mcp.errors import McpToolError
from canresearch.mcp.limits import (
    DEFAULT_DBC_PREVIEW_LINES,
    DEFAULT_LIST_RESEARCH_CANDIDATES,
    MAX_DBC_PREVIEW_LINES,
    MAX_LIST_RESEARCH_CANDIDATES,
)
from canresearch.storage.database import default_db_path


def _resolve_db(db_path: Path | None) -> Path:
    return db_path or default_db_path()


def _to_mcp_error(exc: ResearchCandidateError) -> McpToolError:
    return McpToolError(exc.code, exc.message)


def handle_list_research_candidates(
    *,
    asset_key: str | None = None,
    status: str | None = None,
    session_id: str | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    row_limit = limit if limit is not None else DEFAULT_LIST_RESEARCH_CANDIDATES
    if row_limit <= 0 or row_limit > MAX_LIST_RESEARCH_CANDIDATES:
        raise McpToolError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_LIST_RESEARCH_CANDIDATES}, got {row_limit}",
        )
    try:
        rows = list_research_candidates(
            asset_key=asset_key,
            status=status,
            session_id=session_id,
            limit=row_limit,
            db_path=_resolve_db(db_path),
        )
    except ResearchCandidateError as exc:
        raise _to_mcp_error(exc) from exc
    return {
        "count": len(rows),
        "candidates": [candidate_to_dict(row) for row in rows],
    }


def handle_get_research_candidate(
    candidate_id: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    try:
        candidate = get_research_candidate(candidate_id, db_path=_resolve_db(db_path))
    except ResearchCandidateError as exc:
        raise _to_mcp_error(exc) from exc
    return {"candidate": candidate_to_dict(candidate)}


def handle_list_candidate_evidence(
    candidate_id: str,
    *,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    row_limit = limit if limit is not None else DEFAULT_LIST_LIMIT
    if row_limit <= 0 or row_limit > MAX_LIST_LIMIT:
        raise McpToolError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_LIST_LIMIT}, got {row_limit}",
        )
    try:
        rows = list_candidate_evidence(
            candidate_id,
            limit=row_limit,
            db_path=_resolve_db(db_path),
        )
    except ResearchCandidateError as exc:
        raise _to_mcp_error(exc) from exc
    return {
        "candidate_id": candidate_id,
        "count": len(rows),
        "evidence": [
            {
                "id": row.id,
                "evidence_type": row.evidence_type,
                "evidence": row.evidence,
                "session_id": row.session_id,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


def handle_preview_research_dbc(
    asset_key: str,
    *,
    preview_lines: int | None = None,
    include_protocol_fields: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    line_limit = preview_lines if preview_lines is not None else DEFAULT_DBC_PREVIEW_LINES
    if line_limit <= 0 or line_limit > MAX_DBC_PREVIEW_LINES:
        raise McpToolError(
            "limit_out_of_range",
            f"preview_lines must be between 1 and {MAX_DBC_PREVIEW_LINES}, got {line_limit}",
        )
    summary, preview = preview_research_dbc_text(
        asset_key,
        preview_lines=line_limit,
        db_path=_resolve_db(db_path),
        include_protocol_fields=include_protocol_fields,
    )
    return {
        "asset_key": summary.asset_key,
        "dbc_type": summary.dbc_type,
        "confirmed_signal_count": summary.confirmed_signal_count,
        "message_count": summary.messages_generated,
        "signal_count": summary.signals_generated,
        "skipped": summary.signals_skipped,
        "warnings": [
            {"category": w.category, "message": w.message, "can_id": w.can_id}
            for w in summary.warnings
        ],
        "dbc_preview": preview,
    }
