"""Tests for CANsub PHY timing preflight."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from canresearch.cansub.client import CansubClient
from canresearch.cansub.live_capture import LiveCaptureRegistry
from canresearch.cansub.timing import (
    BitTimingSegments,
    ChannelBitrates,
    TimingCompatibility,
    compare_expected_bitrates,
)
from canresearch.config import load_config
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.live_research import observe_live_traffic
from canresearch.core.timing_preflight import (
    check_channel_timing_preflight,
    enforce_channel_timing_preflight,
)
from canresearch.cansub.timing import ChannelTimingExpectation
from canresearch.storage.database import initialize


PHY_250K_1M = {
    "listen_only": False,
    "auto_reset": True,
    "error_frames": False,
    "timing": {"brp": 4, "seg1": 63, "seg2": 16, "sjw": 4},
    "timing_data": {"brp": 4, "seg1": 15, "seg2": 4, "sjw": 4},
}

PHY_500K_1M = {
    "listen_only": False,
    "auto_reset": True,
    "error_frames": False,
    "timing": {"brp": 2, "seg1": 63, "seg2": 16, "sjw": 4},
    "timing_data": {"brp": 4, "seg1": 15, "seg2": 4, "sjw": 4},
}


@pytest.fixture
def timing_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[cansub]
host = "desk.local"

[cansub.channels.1]
nominal_bitrate = 500000
data_bitrate = 1000000
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_bitrate_from_timing_segments() -> None:
    nominal = BitTimingSegments.from_mapping(PHY_250K_1M["timing"])
    assert nominal is not None
    assert nominal.bitrate_bps() == 250_000
    data = BitTimingSegments.from_mapping(PHY_250K_1M["timing_data"])
    assert data is not None
    assert data.bitrate_bps() == 1_000_000


def test_load_channel_timing_expectation(timing_config: Path) -> None:
    config = load_config(timing_config)
    expectation = config.cansub.channels[1]
    assert expectation.nominal_bitrate == 500_000
    assert expectation.data_bitrate == 1_000_000


def test_not_configured_is_backward_compatible(tmp_path: Path) -> None:
    empty_config = tmp_path / "config.toml"
    empty_config.write_text("[cansub]\nhost = \"desk.local\"\n", encoding="utf-8")
    result = check_channel_timing_preflight(
        "desk.local",
        1,
        config_path=empty_config,
        phy=PHY_500K_1M,
    )
    assert result.state == TimingCompatibility.NOT_CONFIGURED
    enforce_channel_timing_preflight(
        "desk.local",
        1,
        config_path=empty_config,
        phy=PHY_250K_1M,
    )


def test_matching_timing_permits_preflight(timing_config: Path) -> None:
    result = check_channel_timing_preflight(
        "desk.local",
        1,
        config_path=timing_config,
        phy=PHY_500K_1M,
        channel_state="error_active",
    )
    assert result.state == TimingCompatibility.MATCH


def test_stopped_default_phy_is_inactive_not_mismatch(timing_config: Path) -> None:
    result = check_channel_timing_preflight(
        "desk.local",
        1,
        config_path=timing_config,
        phy=PHY_250K_1M,
        channel_state="stopped",
    )
    assert result.state == TimingCompatibility.INACTIVE_OR_AMBIGUOUS


def test_mismatch_blocks_enforce_on_active_channel(timing_config: Path) -> None:
    with pytest.raises(LiveResearchError) as exc:
        enforce_channel_timing_preflight(
            "desk.local",
            1,
            config_path=timing_config,
            phy=PHY_250K_1M,
            channel_state="error_active",
        )
    assert exc.value.code == "timing_mismatch"
    assert "500 kbit/s" in exc.value.message
    assert "250 kbit/s" in exc.value.message


def test_stopped_default_phy_does_not_block_enforce(timing_config: Path) -> None:
    enforce_channel_timing_preflight(
        "desk.local",
        1,
        config_path=timing_config,
        phy=PHY_250K_1M,
        channel_state="stopped",
    )


def test_unknown_actual_blocks_enforce(timing_config: Path) -> None:
    with pytest.raises(LiveResearchError) as exc:
        enforce_channel_timing_preflight(
            "desk.local",
            1,
            config_path=timing_config,
            phy={"listen_only": False},
            channel_state="error_active",
        )
    assert exc.value.code == "timing_unknown"


def test_live_capture_blocked_before_session(
    tmp_path: Path,
    timing_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.core.live_errors import LiveResearchError

    db_path = tmp_path / "canresearch.db"
    initialize(db_path)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: timing_config)

    def block_prepare(*args, **kwargs):
        _ = args, kwargs
        raise LiveResearchError(
            "timing_mismatch",
            "Channel 1 PHY timing does not match configured expectation.",
        )

    monkeypatch.setattr(
        "canresearch.core.capture_prepare.prepare_channel_for_capture",
        block_prepare,
    )
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)

    registry = LiveCaptureRegistry()
    with pytest.raises(LiveResearchError) as exc:
        registry.start("desk.local", 1, db_path=db_path)
    assert exc.value.code == "timing_mismatch"
    assert registry.list_active_session_ids() == []
    conn = initialize(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()
    assert count == 0
    assert not any(tmp_path.rglob("frames.jsonl"))


def test_observe_live_traffic_blocked_on_mismatch(
    timing_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.core.live_errors import LiveResearchError

    monkeypatch.setattr("canresearch.config.default_config_path", lambda: timing_config)

    def block_prepare(*args, **kwargs):
        _ = args, kwargs
        raise LiveResearchError("timing_mismatch", "active mismatch")

    monkeypatch.setattr(
        "canresearch.core.capture_prepare.prepare_channel_for_capture",
        block_prepare,
    )

    with pytest.raises(LiveResearchError) as exc:
        observe_live_traffic("desk.local", 1, duration_seconds=1.0)
    assert exc.value.code == "timing_mismatch"


def test_mcp_and_cli_share_preflight_message(timing_config: Path) -> None:
    cli_result = check_channel_timing_preflight(
        "desk.local",
        1,
        config_path=timing_config,
        phy=PHY_250K_1M,
        channel_state="error_active",
    )
    with pytest.raises(LiveResearchError) as exc:
        enforce_channel_timing_preflight(
            "desk.local",
            1,
            config_path=timing_config,
            phy=PHY_250K_1M,
            channel_state="error_active",
        )
    assert cli_result.state == TimingCompatibility.MISMATCH


def test_compare_expected_bitrates_match() -> None:
    expected = ChannelTimingExpectation(
        channel=1,
        nominal_bitrate=500_000,
        data_bitrate=1_000_000,
    )
    actual = ChannelBitrates.from_phy(PHY_500K_1M)
    assert compare_expected_bitrates(expected, actual) == TimingCompatibility.MATCH


def test_set_channel_phy_uses_put(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_put_json(path: str, payload: dict) -> dict:
        captured["path"] = path
        captured["payload"] = payload
        return payload

    client = CansubClient("example.test")
    monkeypatch.setattr(client, "put_json", fake_put_json)
    result = client.set_channel_phy(1, PHY_500K_1M)
    assert captured["path"] == "/api/can/1/phy"
    assert captured["payload"] == PHY_500K_1M
    assert result == PHY_500K_1M
