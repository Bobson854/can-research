"""Synthetic proprietary CAN fixture for signal research regression tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from canresearch.core.session_events import add_session_event
from canresearch.core.sessions import create_session

SYNTHETIC_CAN_ID = 0x18FF748A
PRESSURE_SCALE = 0.1
ACTION_BIT = 32


@dataclass(frozen=True, slots=True)
class SyntheticFrame:
    timestamp_us: int
    counter: int
    pressure_raw: int
    action_on: bool
    noise_byte: int = 0xA5


def build_payload(*, counter: int, pressure_raw: int, action_on: bool, noise: int = 0xA5) -> bytes:
    payload = bytearray(8)
    payload[0] = counter & 0xFF
    payload[2] = pressure_raw & 0xFF
    payload[3] = (pressure_raw >> 8) & 0xFF
    payload[4] = 0x01 if action_on else 0x00
    payload[5] = noise
    payload[6] = 0x11
    payload[7] = 0x22
    body_for_xor = bytes(
        [payload[0], payload[2], payload[3], payload[4], payload[5], payload[6], payload[7]]
    )
    payload[1] = 0
    for byte in body_for_xor:
        payload[1] ^= byte
    return bytes(payload)


def pressure_engineering(pressure_raw: int) -> float:
    return pressure_raw * PRESSURE_SCALE


def generate_synthetic_frames(
    *,
    baseline_ranges: list[tuple[int, int, int]],
    action_ranges: list[tuple[int, int, int]],
    pressure_baseline: int = 1000,
    pressure_action: int = 1500,
) -> list[SyntheticFrame]:
    """Generate frames for baseline/action/repeated windows.

    Each range is (start_us, end_us, step_us).
    """
    frames: list[SyntheticFrame] = []
    counter = 0

    def emit_ranges(ranges: list[tuple[int, int, int]], *, action_on: bool, pressure: int) -> None:
        nonlocal counter
        for start_us, end_us, step_us in ranges:
            ts = start_us
            while ts < end_us:
                frames.append(
                    SyntheticFrame(
                        timestamp_us=ts,
                        counter=counter,
                        pressure_raw=pressure,
                        action_on=action_on,
                    )
                )
                counter = (counter + 1) % 256
                ts += step_us

    emit_ranges(baseline_ranges, action_on=False, pressure=pressure_baseline)
    emit_ranges(action_ranges, action_on=True, pressure=pressure_action)
    frames.sort(key=lambda f: f.timestamp_us)
    return frames


def write_synthetic_session(
    *,
    session_id: str,
    db_path: Path,
    frames_path: Path,
    repetitions: int = 3,
) -> dict[str, object]:
    """Create a session with repeated baseline/action markers and synthetic traffic."""
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    create_session(
        session_id=session_id,
        name="synthetic-proprietary",
        host="test.local",
        channel=1,
        device_id="synthetic",
        frame_store_path=str(frames_path),
        db_path=db_path,
    )

    all_frames: list[SyntheticFrame] = []
    baseline_labels: list[str] = []
    action_labels: list[str] = []

    for rep in range(repetitions):
        base_start = rep * 10_000_000 + 1_000_000
        act_start = rep * 10_000_000 + 5_000_000
        baseline_labels.append(f"baseline_{rep + 1}")
        action_labels.append(f"scv2_extend_{rep + 1}")
        chunk = generate_synthetic_frames(
            baseline_ranges=[(base_start, base_start + 2_000_000, 100_000)],
            action_ranges=[(act_start, act_start + 2_000_000, 100_000)],
        )
        all_frames.extend(chunk)
        add_session_event(session_id, baseline_labels[-1], timestamp_us=base_start, db_path=db_path)
        add_session_event(session_id, action_labels[-1], timestamp_us=act_start, db_path=db_path)

    with frames_path.open("w", encoding="utf-8") as handle:
        for frame in sorted(all_frames, key=lambda f: f.timestamp_us):
            payload = build_payload(
                counter=frame.counter,
                pressure_raw=frame.pressure_raw,
                action_on=frame.action_on,
                noise=frame.noise_byte,
            )
            line = {
                "timestamp_us": frame.timestamp_us,
                "channel": 1,
                "can_id": SYNTHETIC_CAN_ID,
                "extended": True,
                "fd": False,
                "rtr": False,
                "brs": False,
                "esi": False,
                "tx_ack": False,
                "dlc": 8,
                "data": payload.hex().upper(),
                "is_error_frame": False,
                "error_type": None,
            }
            handle.write(json.dumps(line, separators=(",", ":")))
            handle.write("\n")

    reference = [
        {
            "timestamp_us": frame.timestamp_us,
            "value": pressure_engineering(frame.pressure_raw),
        }
        for frame in all_frames
    ]

    return {
        "session_id": session_id,
        "can_id": SYNTHETIC_CAN_ID,
        "baseline_events": baseline_labels,
        "action_events": action_labels,
        "reference_series": reference,
        "frame_count": len(all_frames),
    }
