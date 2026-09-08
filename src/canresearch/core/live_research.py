"""Live CANsub research: status, bounded observation, events, window comparison.

Change-score heuristic (ranking only, not statistical confidence)::

    freq_delta = |action_count - baseline_count| / max(baseline_count, action_count, 1)
    payload_change_delta = unique_payloads / max(action_count, 1)  (action window)
    new_id_bonus = 1.0 if CAN ID appears only in action window else 0.0
    byte_change_rate = changed_byte_indices_count / 8

    change_score = min(1.0, 0.25*freq_delta + 0.35*payload_change_delta
                           + 0.15*new_id_bonus + 0.25*byte_change_rate)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from canresearch.cansub.capture import cansub_frame_to_can_frame
from canresearch.cansub.client import CansubClient, get_channel_info, probe_host
from canresearch.cansub.exceptions import (
    CansubApiError,
    CansubConnectionError,
    CansubWebSocketError,
)
from canresearch.cansub.live_capture import LiveCaptureRegistry, get_live_capture_registry
from canresearch.cansub.ws_client import ConnectFn, receive_frames_sync
from canresearch.cansub.ws_protocol import CansubFrame
from canresearch.core.assets import list_session_assets
from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.j1939_logical_messages import categorize_j1939_frame
from canresearch.core.j1939_nodes import list_session_nodes, lookup_asset_keys_for_nodes
from canresearch.core.jsonl_capture_store import iter_frames_from_path
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.session_events import (
    SessionEvent,
    add_session_event,
    get_session_event_by_label,
    list_session_events,
)
from canresearch.core.sessions import CanFrame, get_session, resolve_session_frames_path

MAX_SAMPLE_PAYLOADS_PER_ID = 3

DEFAULT_OBSERVE_DURATION_S = 3.0
MIN_OBSERVE_DURATION_S = 0.5
MAX_OBSERVE_DURATION_S = 15.0

DEFAULT_COMPARE_WINDOW_S = 3.0
MAX_COMPARE_WINDOW_S = 30.0

DEFAULT_TRAFFIC_ROWS = 50
MAX_TRAFFIC_ROWS = 200


def _timestamp_iso(timestamp_us: int) -> str:
    return datetime.fromtimestamp(timestamp_us / 1_000_000, tz=UTC).isoformat()


def _format_can_id(can_id: int) -> str:
    return f"0x{can_id:08X}" if can_id > 0x7FF else f"0x{can_id:03X}"


def _payload_hex(data: bytes) -> str:
    return data.hex().upper()


def _normalize_payload(data: bytes, dlc: int | None) -> bytes:
    length = dlc if dlc is not None else len(data)
    length = min(max(length, 0), 8)
    trimmed = data[:length]
    return trimmed.ljust(8, b"\x00")


def get_cansub_device_status(
    host: str,
    *,
    timeout: float = 5.0,
    verify_tls: bool = False,
) -> dict[str, Any]:
    """Return compact CANsub.2 device status from the REST API."""
    try:
        info = probe_host(host, timeout=timeout, verify_tls=verify_tls)
    except CansubConnectionError as exc:
        raise LiveResearchError("cansub_unreachable", str(exc)) from exc
    except CansubApiError as exc:
        raise LiveResearchError("cansub_api_error", str(exc)) from exc
    except Exception as exc:
        raise LiveResearchError("cansub_api_error", str(exc)) from exc

    return {
        "configured_host": host,
        "device_id": info.device_id,
        "firmware_version": info.firmware_version,
        "hardware_version": info.hardware_version,
        "api_version": info.api_version,
        "connection_state": info.status,
        "channel_count": len(info.channels),
        "channels": info.channels,
    }


def get_cansub_channel_status(
    host: str,
    channel: int,
    *,
    timeout: float = 5.0,
    verify_tls: bool = False,
) -> dict[str, Any]:
    """Return read-only CAN channel status from the REST API."""
    try:
        client = CansubClient(host, timeout=timeout, verify_tls=verify_tls)
        channels = client.list_channels()
    except CansubConnectionError as exc:
        raise LiveResearchError("cansub_unreachable", str(exc)) from exc
    except CansubApiError as exc:
        raise LiveResearchError("cansub_api_error", str(exc)) from exc

    if channel not in channels:
        available = ", ".join(map(str, channels))
        msg = f"CAN channel {channel} not found (available: {available})"
        raise LiveResearchError("channel_not_found", msg)

    try:
        status = get_channel_info(host, channel, timeout=timeout, verify_tls=verify_tls)
    except CansubConnectionError as exc:
        raise LiveResearchError("cansub_unreachable", str(exc)) from exc
    except CansubApiError as exc:
        raise LiveResearchError("cansub_api_error", str(exc)) from exc

    result: dict[str, Any] = {
        "channel": status.channel,
        "host": status.host,
        "state": status.state,
        "frame_count": status.frame_count,
        "frame_rate": status.frame_rate,
        "bus_load": status.bus_load,
        "rx_error_count": status.rx_error_count,
        "tx_error_count": status.tx_error_count,
        "bus_error_count": status.bus_error_count,
    }
    if status.phy is not None:
        result["phy"] = status.phy

    from canresearch.core.timing_preflight import check_channel_timing_preflight

    timing = check_channel_timing_preflight(
        host,
        channel,
        timeout=timeout,
        verify_tls=verify_tls,
        phy=status.phy,
    )
    result["timing_preflight"] = timing.to_dict()
    return result


@dataclass
class _TrafficBucket:
    can_id: int
    is_extended: bool
    frame_count: int = 0
    first_timestamp_us: int = 0
    last_timestamp_us: int = 0
    payloads: set[bytes] = field(default_factory=set)
    sample_payloads: list[str] = field(default_factory=list)
    pgn: int | None = None
    source_address: int | None = None
    destination_address: int | None = None


def observe_live_traffic(
    host: str,
    channel: int,
    *,
    duration_seconds: float = DEFAULT_OBSERVE_DURATION_S,
    pgn: int | None = None,
    source_address: int | None = None,
    can_id: int | None = None,
    limit: int = DEFAULT_TRAFFIC_ROWS,
    timeout: float = 5.0,
    verify_tls: bool = False,
    connect: ConnectFn | None = None,
    registry: LiveCaptureRegistry | None = None,
) -> dict[str, Any]:
    """Observe live CAN traffic for a bounded duration; return aggregated summary."""
    from canresearch.core.timing_preflight import enforce_channel_timing_preflight

    enforce_channel_timing_preflight(
        host,
        channel,
        timeout=timeout,
        verify_tls=verify_tls,
    )

    if duration_seconds < MIN_OBSERVE_DURATION_S or duration_seconds > MAX_OBSERVE_DURATION_S:
        msg = (
            f"duration_seconds must be between {MIN_OBSERVE_DURATION_S} and "
            f"{MAX_OBSERVE_DURATION_S}, got {duration_seconds}"
        )
        raise LiveResearchError("limit_out_of_range", msg)
    if limit <= 0 or limit > MAX_TRAFFIC_ROWS:
        msg = f"limit must be between 1 and {MAX_TRAFFIC_ROWS}, got {limit}"
        raise LiveResearchError("limit_out_of_range", msg)

    reg = registry or get_live_capture_registry()
    if reg.is_channel_active(channel):
        msg = f"Channel {channel} RX is in use by an active capture"
        raise LiveResearchError("channel_rx_in_use", msg)

    buckets: dict[int, _TrafficBucket] = {}
    frames_seen = 0
    unique_j1939_pgns: set[int] = set()

    def on_frame(frame: CansubFrame) -> None:
        nonlocal frames_seen
        if frame.is_error_frame or frame.can_id is None:
            return
        frames_seen += 1
        cid = frame.can_id
        bucket = buckets.get(cid)
        if bucket is None:
            bucket = _TrafficBucket(
                can_id=cid,
                is_extended=frame.extended,
                frame_count=1,
                first_timestamp_us=frame.timestamp_us,
                last_timestamp_us=frame.timestamp_us,
            )
            can_frame = cansub_frame_to_can_frame(frame)
            if frame.extended and categorize_j1939_frame(can_frame) == "j1939":
                try:
                    parsed = parse_j1939_id(cid)
                    bucket.pgn = parsed.pgn
                    bucket.source_address = parsed.source_address
                    bucket.destination_address = parsed.destination_address
                    unique_j1939_pgns.add(parsed.pgn)
                except ValueError:
                    pass
            buckets[cid] = bucket
        else:
            bucket.frame_count += 1
            bucket.last_timestamp_us = max(bucket.last_timestamp_us, frame.timestamp_us)
            bucket.first_timestamp_us = min(bucket.first_timestamp_us, frame.timestamp_us)

        payload = _normalize_payload(frame.data, frame.dlc)
        bucket.payloads.add(payload)
        if len(bucket.sample_payloads) < MAX_SAMPLE_PAYLOADS_PER_ID:
            hex_payload = _payload_hex(payload)
            if hex_payload not in bucket.sample_payloads:
                bucket.sample_payloads.append(hex_payload)

    try:
        rx = receive_frames_sync(
            host,
            channel,
            duration=duration_seconds,
            timeout=timeout,
            verify_tls=verify_tls,
            on_frame=on_frame,
            connect=connect,
        )
        actual_duration = rx.duration_s
    except CansubWebSocketError as exc:
        lowered = str(exc).lower()
        if "not found" in lowered:
            raise LiveResearchError("channel_not_found", str(exc)) from exc
        if "in use by another client" in lowered:
            raise LiveResearchError("channel_rx_in_use", str(exc)) from exc
        if "timeout" in lowered or "timed out" in lowered:
            raise LiveResearchError("observation_timeout", str(exc)) from exc
        if "unable to connect" in lowered or "resolve" in lowered:
            raise LiveResearchError("cansub_unreachable", str(exc)) from exc
        raise LiveResearchError("cansub_api_error", str(exc)) from exc

    rows: list[dict[str, Any]] = []
    for bucket in sorted(buckets.values(), key=lambda b: (-b.frame_count, b.can_id)):
        if pgn is not None and bucket.pgn != pgn:
            continue
        if source_address is not None and bucket.source_address != source_address:
            continue
        if can_id is not None and bucket.can_id != can_id:
            continue
        rows.append(
            {
                "can_id": _format_can_id(bucket.can_id),
                "pgn": bucket.pgn,
                "source_address": bucket.source_address,
                "destination_address": bucket.destination_address,
                "count": bucket.frame_count,
                "first_seen": _timestamp_iso(bucket.first_timestamp_us),
                "last_seen": _timestamp_iso(bucket.last_timestamp_us),
                "data_changes": max(len(bucket.payloads) - 1, 0),
                "sample_payloads": list(bucket.sample_payloads),
            }
        )

    truncated = len(rows) > limit
    traffic = rows[:limit]

    return {
        "channel": channel,
        "duration_seconds": round(actual_duration, 3),
        "frames_seen": frames_seen,
        "unique_can_ids": len(buckets),
        "unique_j1939_pgns": len(unique_j1939_pgns),
        "traffic": traffic,
        "truncated": truncated,
    }


def mark_experiment_event(
    session_id: str,
    label: str,
    *,
    notes: str | None = None,
    db_path: Path | None = None,
    registry: LiveCaptureRegistry | None = None,
) -> dict[str, Any]:
    """Persist an experiment marker against a session."""
    reg = registry or get_live_capture_registry()
    timestamp_us: int | None = None
    active = reg.get_active(session_id)
    if active is not None:
        timestamp_us = reg.latest_timestamp_us(session_id)
    try:
        event = add_session_event(
            session_id,
            label,
            notes=notes,
            timestamp_us=timestamp_us,
            db_path=db_path,
        )
    except KeyError as exc:
        raise LiveResearchError("capture_session_not_found", str(exc)) from exc
    return _event_dict(event)


def list_experiment_events(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return experiment markers for a session."""
    try:
        events = list_session_events(session_id, db_path=db_path)
    except KeyError as exc:
        raise LiveResearchError("capture_session_not_found", str(exc)) from exc
    return [_event_dict(event) for event in events]


def _event_dict(event: SessionEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "session_id": event.session_id,
        "timestamp": _timestamp_iso(event.timestamp_us),
        "timestamp_us": event.timestamp_us,
        "label": event.label,
        "notes": event.notes,
        "origin": event.origin,
        "created_at": event.created_at.isoformat(),
    }


def build_session_sa_asset_map(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> dict[int, str]:
    """Map source address to asset_key when resolvable via session NAME claims."""
    session_asset_keys = {
        record.asset_key for record in list_session_assets(session_id, db_path=db_path)
    }
    if not session_asset_keys:
        return {}

    nodes = list_session_nodes(session_id, db_path=db_path)
    asset_links = lookup_asset_keys_for_nodes(
        [node.node_id for node in nodes if node.node_id],
        db_path=db_path,
    )

    mapping: dict[int, str] = {}
    for node in nodes:
        asset_key = asset_links.get(node.node_id or "")
        if asset_key is None or asset_key not in session_asset_keys:
            continue
        for obs in node.observations:
            if obs.cannot_claim:
                continue
            if obs.source_address in mapping and mapping[obs.source_address] != asset_key:
                continue
            mapping[obs.source_address] = asset_key
    return mapping


@dataclass
class _WindowStats:
    can_id: int
    frame_count: int = 0
    payloads: list[bytes] = field(default_factory=list)
    pgn: int | None = None
    source_address: int | None = None
    destination_address: int | None = None
    is_extended: bool = True


def _collect_window_frames(
    frames: Iterable[CanFrame],
    start_us: int,
    end_us: int,
) -> dict[int, _WindowStats]:
    buckets: dict[int, _WindowStats] = {}
    for frame in frames:
        if frame.is_error_frame or frame.can_id is None:
            continue
        if frame.timestamp_us < start_us or frame.timestamp_us >= end_us:
            continue
        cid = frame.can_id
        bucket = buckets.get(cid)
        if bucket is None:
            bucket = _WindowStats(can_id=cid, is_extended=frame.is_extended)
            if frame.is_extended and categorize_j1939_frame(frame) == "j1939":
                try:
                    parsed = parse_j1939_id(cid)
                    bucket.pgn = parsed.pgn
                    bucket.source_address = parsed.source_address
                    bucket.destination_address = parsed.destination_address
                except ValueError:
                    pass
            buckets[cid] = bucket
        bucket.frame_count += 1
        bucket.payloads.append(_normalize_payload(frame.data, frame.dlc))
    return buckets


def _byte_change_stats(payloads: list[bytes]) -> dict[str, Any]:
    if not payloads:
        return {
            "byte_changed_count": [0] * 8,
            "byte_unique_values": [0] * 8,
            "byte_change_rate": [0.0] * 8,
            "bit_toggle_count": [0] * 64,
        }

    byte_changed_count = [0] * 8
    byte_unique_values = [len({p[i] for p in payloads}) for i in range(8)]
    bit_toggle_count = [0] * 64

    for index in range(1, len(payloads)):
        prev = payloads[index - 1]
        curr = payloads[index]
        for byte_index in range(8):
            if prev[byte_index] != curr[byte_index]:
                byte_changed_count[byte_index] += 1
        for bit_index in range(64):
            prev_bit = (prev[bit_index // 8] >> (bit_index % 8)) & 1
            curr_bit = (curr[bit_index // 8] >> (bit_index % 8)) & 1
            if prev_bit != curr_bit:
                bit_toggle_count[bit_index] += 1

    transitions = max(len(payloads) - 1, 1)
    byte_change_rate = [count / transitions for count in byte_changed_count]

    return {
        "byte_changed_count": byte_changed_count,
        "byte_unique_values": byte_unique_values,
        "byte_change_rate": byte_change_rate,
        "bit_toggle_count": bit_toggle_count,
    }


def _changed_byte_indices(baseline: list[bytes], action: list[bytes]) -> list[int]:
    indices: set[int] = set()
    for payloads in (baseline, action):
        for index in range(1, len(payloads)):
            prev = payloads[index - 1]
            curr = payloads[index]
            for byte_index in range(8):
                if prev[byte_index] != curr[byte_index]:
                    indices.add(byte_index)
    if baseline and action:
        base_set = set(baseline)
        action_set = set(action)
        if base_set != action_set:
            for byte_index in range(8):
                base_vals = {p[byte_index] for p in base_set}
                action_vals = {p[byte_index] for p in action_set}
                if base_vals != action_vals:
                    indices.add(byte_index)
    return sorted(indices)


def _compute_change_score(
    *,
    baseline_count: int,
    action_count: int,
    baseline_payloads: list[bytes],
    action_payloads: list[bytes],
    only_in_action: bool,
) -> float:
    freq_delta = abs(action_count - baseline_count) / max(baseline_count, action_count, 1)
    unique_action = len(set(action_payloads))
    payload_change_delta = unique_action / max(action_count, 1)
    new_id_bonus = 1.0 if only_in_action else 0.0
    changed_indices = _changed_byte_indices(baseline_payloads, action_payloads)
    byte_change_rate = len(changed_indices) / 8.0
    score = (
        0.25 * freq_delta
        + 0.35 * payload_change_delta
        + 0.15 * new_id_bonus
        + 0.25 * byte_change_rate
    )
    return round(min(1.0, score), 4)


def compare_experiment_windows(
    session_id: str,
    *,
    baseline_event: str,
    action_event: str,
    window_seconds: float = DEFAULT_COMPARE_WINDOW_S,
    db_path: Path | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    """Compare two bounded time windows defined by experiment event markers."""
    if window_seconds <= 0 or window_seconds > MAX_COMPARE_WINDOW_S:
        msg = f"window_seconds must be between 0 and {MAX_COMPARE_WINDOW_S}, got {window_seconds}"
        raise LiveResearchError("limit_out_of_range", msg)

    try:
        get_session(session_id, db_path=db_path)
    except KeyError as exc:
        raise LiveResearchError("capture_session_not_found", str(exc)) from exc

    try:
        baseline_marker = get_session_event_by_label(session_id, baseline_event, db_path=db_path)
        action_marker = get_session_event_by_label(session_id, action_event, db_path=db_path)
    except KeyError as exc:
        raise LiveResearchError("event_not_found", str(exc)) from exc

    window_us = int(window_seconds * 1_000_000)
    baseline_start = baseline_marker.timestamp_us
    baseline_end = baseline_start + window_us
    action_start = action_marker.timestamp_us
    action_end = action_start + window_us

    record = get_session(session_id, db_path=db_path)
    frames_path = resolve_session_frames_path(record)
    if not frames_path.exists():
        raise LiveResearchError("insufficient_window_data", "Session has no stored frames")

    all_frames = list(iter_frames_from_path(frames_path))
    baseline_buckets = _collect_window_frames(all_frames, baseline_start, baseline_end)
    action_buckets = _collect_window_frames(all_frames, action_start, action_end)

    baseline_frames = sum(b.frame_count for b in baseline_buckets.values())
    action_frames = sum(b.frame_count for b in action_buckets.values())
    if baseline_frames == 0 and action_frames == 0:
        raise LiveResearchError("insufficient_window_data", "No frames in either comparison window")

    sa_asset_map = build_session_sa_asset_map(session_id, db_path=db_path)
    all_ids = set(baseline_buckets) | set(action_buckets)
    baseline_only = sorted(set(baseline_buckets) - set(action_buckets))
    action_only = sorted(set(action_buckets) - set(baseline_buckets))

    candidates: list[dict[str, Any]] = []
    for cid in all_ids:
        base = baseline_buckets.get(cid)
        act = action_buckets.get(cid)
        baseline_count = base.frame_count if base else 0
        action_count = act.frame_count if act else 0
        baseline_payloads = base.payloads if base else []
        action_payloads = act.payloads if act else []
        ref = act or base
        assert ref is not None
        changed_byte_indices = _changed_byte_indices(baseline_payloads, action_payloads)
        score = _compute_change_score(
            baseline_count=baseline_count,
            action_count=action_count,
            baseline_payloads=baseline_payloads,
            action_payloads=action_payloads,
            only_in_action=cid in action_only,
        )
        sa = ref.source_address
        candidates.append(
            {
                "can_id": _format_can_id(cid),
                "pgn": ref.pgn,
                "source_address": sa,
                "destination_address": ref.destination_address,
                "asset_key": sa_asset_map.get(sa) if sa is not None else None,
                "baseline_count": baseline_count,
                "action_count": action_count,
                "changed_byte_indices": changed_byte_indices,
                "change_score": score,
                "baseline_stats": _byte_change_stats(baseline_payloads),
                "action_stats": _byte_change_stats(action_payloads),
            }
        )

    candidates.sort(key=lambda item: (-item["change_score"], item["can_id"]))
    top_changes = candidates[:top_n]

    return {
        "session_id": session_id,
        "baseline": {
            "event": baseline_event,
            "start": _timestamp_iso(baseline_start),
            "end": _timestamp_iso(baseline_end),
            "frames": baseline_frames,
        },
        "action": {
            "event": action_event,
            "start": _timestamp_iso(action_start),
            "end": _timestamp_iso(action_end),
            "frames": action_frames,
        },
        "baseline_only_can_ids": [_format_can_id(cid) for cid in baseline_only],
        "action_only_can_ids": [_format_can_id(cid) for cid in action_only],
        "top_changes": top_changes,
    }
