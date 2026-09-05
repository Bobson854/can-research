"""J1939 Address Claim discovery, persistence, and asset linkage."""

from __future__ import annotations

import sqlite3
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.j1939_logical_messages import categorize_j1939_frame
from canresearch.core.j1939_name import (
    INVALID_NODE_SOURCE_ADDRESSES,
    NULL_SOURCE_ADDRESS,
    PGN_ADDRESS_CLAIM,
    J1939Name,
    parse_j1939_name_payload,
    parse_j1939_name_text,
)
from canresearch.core.jsonl_capture_store import iter_frames_from_path
from canresearch.core.sessions import CanFrame, get_session, resolve_session_frames_path
from canresearch.storage.database import default_db_path, initialize

SOURCE_ADDRESS_ORIGIN_MANUAL = "manual"
SOURCE_ADDRESS_ORIGIN_ASSET_NODE = "asset_node_resolution"


@dataclass(frozen=True, slots=True)
class NodeObservation:
    session_id: str
    source_address: int
    first_seen_at_us: int
    last_seen_at_us: int
    claim_count: int
    cannot_claim: bool


@dataclass(frozen=True, slots=True)
class J1939NodeRecord:
    id: str
    name: J1939Name
    created_at: datetime
    updated_at: datetime
    observations: tuple[NodeObservation, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SessionNodeView:
    node_id: str
    name: J1939Name
    latest_source_address: int | None
    cannot_claim: bool
    claim_count: int
    observations: tuple[NodeObservation, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NodeDiscoveryWarning:
    category: str
    message: str
    session_id: str | None = None
    source_address: int | None = None
    name_hex: str | None = None


@dataclass
class NodeDiscoveryStats:
    address_claim_frames: int = 0
    unique_names: int = 0
    unique_source_addresses: int = 0
    address_conflicts: int = 0


@dataclass(frozen=True, slots=True)
class NodeDiscoveryResult:
    session_id: str
    nodes: tuple[SessionNodeView, ...]
    warnings: tuple[NodeDiscoveryWarning, ...]
    stats: NodeDiscoveryStats


@dataclass(frozen=True, slots=True)
class ResolvedSourceAddresses:
    source_addresses: tuple[int, ...]
    origin: str
    j1939_names: tuple[str, ...]


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _timestamp_iso(timestamp_us: int) -> str:
    return datetime.fromtimestamp(timestamp_us / 1_000_000, tz=UTC).isoformat()


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    return datetime.fromisoformat(value)


def _name_key(name: J1939Name) -> str:
    return name.name_hex.upper()


def discover_j1939_nodes(
    frames: Iterable[CanFrame],
    *,
    session_id: str,
) -> NodeDiscoveryResult:
    """Scan frames for Address Claim traffic and return discovered nodes."""
    claims: list[tuple[int, int, J1939Name, bool]] = []
    warnings: list[NodeDiscoveryWarning] = []
    stats = NodeDiscoveryStats()

    for frame in frames:
        if categorize_j1939_frame(frame) != "j1939" or frame.can_id is None:
            continue
        try:
            parsed = parse_j1939_id(frame.can_id)
        except ValueError:
            continue
        if parsed.pgn != PGN_ADDRESS_CLAIM:
            continue

        stats.address_claim_frames += 1
        payload = frame.data
        if frame.dlc is not None and len(payload) > frame.dlc:
            payload = payload[: frame.dlc]
        try:
            name = parse_j1939_name_payload(payload)
        except ValueError as exc:
            warnings.append(
                NodeDiscoveryWarning(
                    category="invalid_address_claim",
                    message=str(exc),
                    session_id=session_id,
                )
            )
            continue

        source_address = parsed.source_address
        if source_address in INVALID_NODE_SOURCE_ADDRESSES:
            warnings.append(
                NodeDiscoveryWarning(
                    category="invalid_source_address",
                    message=f"Ignoring Address Claim with invalid SA 0x{source_address:02X}",
                    session_id=session_id,
                    name_hex=name.name_hex,
                )
            )
            continue

        cannot_claim = source_address == NULL_SOURCE_ADDRESS
        claims.append((frame.timestamp_us, source_address, name, cannot_claim))

    sa_to_names: dict[int, set[str]] = defaultdict(set)
    for _ts, sa, name, _cc in claims:
        sa_to_names[sa].add(_name_key(name))

    for sa, names in sa_to_names.items():
        if len(names) > 1:
            stats.address_conflicts += 1
            formatted = ", ".join(sorted(names))
            warnings.append(
                NodeDiscoveryWarning(
                    category="source_address_conflict",
                    message=(
                        f"Source address 0x{sa:02X} claimed by multiple NAMEs: {formatted}"
                    ),
                    session_id=session_id,
                    source_address=sa,
                )
            )

    grouped: dict[str, dict[int, dict[str, object]]] = defaultdict(dict)
    for timestamp_us, source_address, name, cannot_claim in claims:
        key = _name_key(name)
        bucket = grouped[key].setdefault(
            source_address,
            {
                "name": name,
                "first_seen_at_us": timestamp_us,
                "last_seen_at_us": timestamp_us,
                "claim_count": 0,
                "cannot_claim": cannot_claim,
            },
        )
        bucket["last_seen_at_us"] = max(int(bucket["last_seen_at_us"]), timestamp_us)
        bucket["first_seen_at_us"] = min(int(bucket["first_seen_at_us"]), timestamp_us)
        bucket["claim_count"] = int(bucket["claim_count"]) + 1
        bucket["cannot_claim"] = bool(bucket["cannot_claim"]) or cannot_claim

    nodes: list[SessionNodeView] = []
    all_sas: set[int] = set()
    for _group_key, sa_map in sorted(grouped.items()):
        first = next(iter(sa_map.values()))
        name: J1939Name = first["name"]  # type: ignore[assignment]
        observations = tuple(
            NodeObservation(
                session_id=session_id,
                source_address=sa,
                first_seen_at_us=int(data["first_seen_at_us"]),
                last_seen_at_us=int(data["last_seen_at_us"]),
                claim_count=int(data["claim_count"]),
                cannot_claim=bool(data["cannot_claim"]),
            )
            for sa, data in sorted(sa_map.items())
        )
        usable = [obs for obs in observations if not obs.cannot_claim]
        latest = max(usable, key=lambda obs: obs.last_seen_at_us) if usable else None
        latest_sa = latest.source_address if latest else None
        if latest_sa is not None:
            all_sas.add(latest_sa)
        nodes.append(
            SessionNodeView(
                node_id="",
                name=name,
                latest_source_address=latest_sa,
                cannot_claim=all(obs.cannot_claim for obs in observations),
                claim_count=sum(obs.claim_count for obs in observations),
                observations=observations,
            )
        )

    stats.unique_names = len(nodes)
    stats.unique_source_addresses = len(all_sas)
    return NodeDiscoveryResult(
        session_id=session_id,
        nodes=tuple(nodes),
        warnings=tuple(warnings),
        stats=stats,
    )


def persist_session_nodes(
    result: NodeDiscoveryResult,
    *,
    db_path: Path | None = None,
) -> NodeDiscoveryResult:
    """Persist discovered nodes and session observations idempotently."""
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        persisted_nodes: list[SessionNodeView] = []
        for node in result.nodes:
            node_id = _upsert_node(conn, node.name)
            observations: list[NodeObservation] = []
            for obs in node.observations:
                observations.append(
                    _upsert_observation(
                        conn,
                        node_id=node_id,
                        session_id=result.session_id,
                        observation=obs,
                    )
                )
            latest = _latest_usable_observation(observations)
            persisted_nodes.append(
                SessionNodeView(
                    node_id=node_id,
                    name=node.name,
                    latest_source_address=latest.source_address if latest else None,
                    cannot_claim=node.cannot_claim,
                    claim_count=sum(item.claim_count for item in observations),
                    observations=tuple(observations),
                )
            )
        conn.commit()
    finally:
        conn.close()

    return NodeDiscoveryResult(
        session_id=result.session_id,
        nodes=tuple(persisted_nodes),
        warnings=result.warnings,
        stats=result.stats,
    )


def scan_session_j1939_nodes(
    session_id: str,
    *,
    db_path: Path | None = None,
    persist: bool = True,
) -> NodeDiscoveryResult:
    """Discover (and optionally persist) J1939 nodes from a saved session."""
    path = db_path or default_db_path()
    record = get_session(session_id, db_path=path)
    frames_path = resolve_session_frames_path(record)
    if not frames_path.exists():
        msg = f"Frame store not found: {frames_path}"
        raise FileNotFoundError(msg)

    result = discover_j1939_nodes(
        iter_frames_from_path(frames_path),
        session_id=session_id,
    )
    if persist:
        return persist_session_nodes(result, db_path=path)
    return result


def list_session_nodes(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> list[SessionNodeView]:
    """Return persisted node observations for a session."""
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        rows = conn.execute(
            """
            SELECT n.id, n.name_value, n.manufacturer_code, n.identity_number,
                   n.function, n.function_instance, n.ecu_instance, n.vehicle_system,
                   n.vehicle_system_instance, n.industry_group, n.arbitrary_address_capable,
                   o.source_address, o.first_seen_at, o.last_seen_at, o.claim_count,
                   o.cannot_claim
            FROM j1939_node_observations o
            JOIN j1939_nodes n ON n.id = o.node_id
            WHERE o.session_id = ?
            ORDER BY n.name_value ASC, o.source_address ASC
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        node_id = row["id"]
        if node_id not in grouped:
            name = _row_to_name(row)
            grouped[node_id] = {"name": name, "observations": []}
        grouped[node_id]["observations"].append(
            NodeObservation(
                session_id=session_id,
                source_address=int(row["source_address"]),
                first_seen_at_us=_iso_to_us(row["first_seen_at"]),
                last_seen_at_us=_iso_to_us(row["last_seen_at"]),
                claim_count=int(row["claim_count"]),
                cannot_claim=bool(row["cannot_claim"]),
            )
        )

    views: list[SessionNodeView] = []
    for node_id, data in grouped.items():
        observations: list[NodeObservation] = data["observations"]  # type: ignore[assignment]
        name: J1939Name = data["name"]  # type: ignore[assignment]
        latest = _latest_usable_observation(observations)
        views.append(
            SessionNodeView(
                node_id=node_id,
                name=name,
                latest_source_address=latest.source_address if latest else None,
                cannot_claim=all(obs.cannot_claim for obs in observations),
                claim_count=sum(obs.claim_count for obs in observations),
                observations=tuple(observations),
            )
        )
    return views


def lookup_asset_keys_for_nodes(
    node_ids: Iterable[str],
    *,
    db_path: Path | None = None,
) -> dict[str, str]:
    """Map node IDs to linked asset keys (read-only)."""
    ids = tuple(node_ids)
    if not ids:
        return {}
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"""
            SELECT n.id, a.asset_key
            FROM j1939_nodes n
            JOIN asset_j1939_nodes aj ON aj.node_id = n.id
            JOIN assets a ON a.id = aj.asset_id
            WHERE n.id IN ({placeholders})
            """,
            ids,
        ).fetchall()
    finally:
        conn.close()
    return {str(row["id"]): str(row["asset_key"]) for row in rows}


def link_asset_node(
    asset_key: str,
    name_text: str,
    *,
    db_path: Path | None = None,
    require_observed: bool = True,
) -> str:
    """Link a J1939 NAME to an asset."""
    from canresearch.core.assets import get_asset_by_key

    name = parse_j1939_name_text(name_text)
    asset = get_asset_by_key(asset_key, db_path=db_path)
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        existing_node = conn.execute(
            "SELECT id FROM j1939_nodes WHERE name_value = ?",
            (_name_key(name),),
        ).fetchone()
        if require_observed and existing_node is None:
            msg = f"J1939 NAME {name.name_hex} has not been observed yet"
            raise ValueError(msg)
        node_id = _get_or_create_node(conn, name)
        existing = conn.execute(
            "SELECT asset_id FROM asset_j1939_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if existing is not None and existing["asset_id"] != asset.id:
            msg = (
                f"J1939 NAME {name.name_hex} is already linked to another asset; "
                "remove the existing link first"
            )
            raise ValueError(msg)
        try:
            conn.execute(
                """
                INSERT INTO asset_j1939_nodes (asset_id, node_id, created_at)
                VALUES (?, ?, ?)
                """,
                (asset.id, node_id, _utc_now_iso()),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            msg = f"J1939 NAME {name.name_hex} is already linked to asset {asset_key!r}"
            raise ValueError(msg) from exc
    finally:
        conn.close()
    return node_id


def unlink_asset_node(
    asset_key: str,
    name_text: str,
    *,
    db_path: Path | None = None,
) -> None:
    from canresearch.core.assets import get_asset_by_key

    name = parse_j1939_name_text(name_text)
    asset = get_asset_by_key(asset_key, db_path=db_path)
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        row = conn.execute(
            "SELECT id FROM j1939_nodes WHERE name_value = ?",
            (_name_key(name),),
        ).fetchone()
        if row is None:
            msg = f"J1939 NAME {name.name_hex} not found"
            raise KeyError(msg)
        cursor = conn.execute(
            "DELETE FROM asset_j1939_nodes WHERE asset_id = ? AND node_id = ?",
            (asset.id, row["id"]),
        )
        conn.commit()
        if cursor.rowcount == 0:
            msg = f"J1939 NAME {name.name_hex} is not linked to asset {asset_key!r}"
            raise KeyError(msg)
    finally:
        conn.close()


def list_asset_nodes(
    asset_key: str,
    *,
    db_path: Path | None = None,
) -> list[J1939NodeRecord]:
    from canresearch.core.assets import get_asset_by_key

    asset = get_asset_by_key(asset_key, db_path=db_path)
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        rows = conn.execute(
            """
            SELECT n.* FROM j1939_nodes n
            JOIN asset_j1939_nodes aj ON aj.node_id = n.id
            WHERE aj.asset_id = ?
            ORDER BY n.name_value ASC
            """,
            (asset.id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_node_record(row, observations=()) for row in rows]


def resolve_source_addresses_for_asset(
    session_id: str,
    asset_key: str,
    *,
    db_path: Path | None = None,
) -> ResolvedSourceAddresses:
    """Resolve session source addresses from J1939 nodes linked to an asset."""
    from canresearch.core.assets import get_asset_by_key

    asset = get_asset_by_key(asset_key, db_path=db_path)
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        rows = conn.execute(
            """
            SELECT n.name_value, o.source_address, o.cannot_claim
            FROM asset_j1939_nodes aj
            JOIN j1939_nodes n ON n.id = aj.node_id
            LEFT JOIN j1939_node_observations o
                ON o.node_id = n.id AND o.session_id = ?
            WHERE aj.asset_id = ?
            ORDER BY n.name_value ASC, o.last_seen_at ASC
            """,
            (session_id, asset.id),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        msg = (
            f"No J1939 nodes linked to asset {asset_key!r}; "
            "use `canresearch asset node add` or provide --source-address"
        )
        raise ValueError(msg)

    names: list[str] = []
    source_addresses: set[int] = set()
    for row in rows:
        if row["source_address"] is None:
            continue
        if bool(row["cannot_claim"]):
            continue
        sa = int(row["source_address"])
        if sa in INVALID_NODE_SOURCE_ADDRESSES:
            continue
        names.append(str(row["name_value"]))
        source_addresses.add(sa)

    if not source_addresses:
        linked = sorted({str(row["name_value"]) for row in rows})
        formatted = ", ".join(linked)
        msg = (
            f"No source addresses could be resolved for asset {asset_key!r} "
            f"in session {session_id!r}. Linked NAMEs: {formatted}. "
            "Run `canresearch session nodes` or provide --source-address."
        )
        raise ValueError(msg)

    return ResolvedSourceAddresses(
        source_addresses=tuple(sorted(source_addresses)),
        origin=SOURCE_ADDRESS_ORIGIN_ASSET_NODE,
        j1939_names=tuple(sorted(set(names))),
    )


def _upsert_node(conn: sqlite3.Connection, name: J1939Name) -> str:
    return _get_or_create_node(conn, name)


def _get_or_create_node(conn: sqlite3.Connection, name: J1939Name) -> str:
    key = _name_key(name)
    row = conn.execute(
        "SELECT id FROM j1939_nodes WHERE name_value = ?",
        (key,),
    ).fetchone()
    now = _utc_now_iso()
    if row is not None:
        conn.execute(
            """
            UPDATE j1939_nodes
            SET manufacturer_code = ?, identity_number = ?, function = ?,
                function_instance = ?, ecu_instance = ?, vehicle_system = ?,
                vehicle_system_instance = ?, industry_group = ?,
                arbitrary_address_capable = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name.manufacturer_code,
                name.identity_number,
                name.function,
                name.function_instance,
                name.ecu_instance,
                name.vehicle_system,
                name.vehicle_system_instance,
                name.industry_group,
                int(name.arbitrary_address_capable),
                now,
                row["id"],
            ),
        )
        return str(row["id"])

    node_id = uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO j1939_nodes (
            id, name_value, manufacturer_code, identity_number, function,
            function_instance, ecu_instance, vehicle_system,
            vehicle_system_instance, industry_group, arbitrary_address_capable,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id,
            key,
            name.manufacturer_code,
            name.identity_number,
            name.function,
            name.function_instance,
            name.ecu_instance,
            name.vehicle_system,
            name.vehicle_system_instance,
            name.industry_group,
            int(name.arbitrary_address_capable),
            now,
            now,
        ),
    )
    return node_id


def _upsert_observation(
    conn: sqlite3.Connection,
    *,
    node_id: str,
    session_id: str,
    observation: NodeObservation,
) -> NodeObservation:
    row = conn.execute(
        """
        SELECT id, first_seen_at, last_seen_at, claim_count
        FROM j1939_node_observations
        WHERE node_id = ? AND session_id = ? AND source_address = ?
        """,
        (node_id, session_id, observation.source_address),
    ).fetchone()
    first_iso = _timestamp_iso(observation.first_seen_at_us)
    last_iso = _timestamp_iso(observation.last_seen_at_us)
    if row is None:
        conn.execute(
            """
            INSERT INTO j1939_node_observations (
                node_id, session_id, source_address, first_seen_at, last_seen_at,
                claim_count, cannot_claim
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                session_id,
                observation.source_address,
                first_iso,
                last_iso,
                observation.claim_count,
                int(observation.cannot_claim),
            ),
        )
        return observation

    merged_first = min(row["first_seen_at"], first_iso)
    merged_last = max(row["last_seen_at"], last_iso)
    merged_count = int(row["claim_count"]) + observation.claim_count
    cannot_claim = bool(observation.cannot_claim)
    conn.execute(
        """
        UPDATE j1939_node_observations
        SET first_seen_at = ?, last_seen_at = ?, claim_count = ?, cannot_claim = ?
        WHERE id = ?
        """,
        (merged_first, merged_last, merged_count, int(cannot_claim), row["id"]),
    )
    return NodeObservation(
        session_id=session_id,
        source_address=observation.source_address,
        first_seen_at_us=_iso_to_us(merged_first),
        last_seen_at_us=_iso_to_us(merged_last),
        claim_count=merged_count,
        cannot_claim=cannot_claim,
    )


def _latest_usable_observation(
    observations: Iterable[NodeObservation],
) -> NodeObservation | None:
    usable = [obs for obs in observations if not obs.cannot_claim]
    if not usable:
        return None
    return max(usable, key=lambda obs: obs.last_seen_at_us)


def _row_to_name(row: sqlite3.Row) -> J1939Name:
    return parse_j1939_name_text(str(row["name_value"]))


def _row_to_node_record(
    row: sqlite3.Row,
    *,
    observations: tuple[NodeObservation, ...],
) -> J1939NodeRecord:
    return J1939NodeRecord(
        id=row["id"],
        name=_row_to_name(row),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        observations=observations,
    )


def _iso_to_us(value: str) -> int:
    return int(_parse_datetime(value).timestamp() * 1_000_000)
