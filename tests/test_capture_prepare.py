"""Tests for configured timing preparation workflow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from canresearch.cansub.timing import (
    CANSUB_PHY_PUT_VERIFIED,
    ConnectionPolicy,
    TimingCompatibility,
)
from canresearch.core.capture_prepare import prepare_channel_for_capture
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.timing_preflight import check_channel_timing_preflight
from tests.test_timing_preflight import PHY_250K_1M, PHY_500K_1M


@pytest.fixture
def ensure_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[cansub]
host = "desk.local"

[cansub.channels.1]
nominal_bitrate = 500000
data_bitrate = 1000000
connection_policy = "ensure_before_rx"
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_prepare_inactive_channel_requires_manual_timing_without_verified_put(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="stopped")

        def get_channel_phy(self, channel: int):
            _ = channel
            return PHY_250K_1M

    put_called = {"value": False}

    def fake_put(*args, **kwargs):
        _ = args, kwargs
        put_called["value"] = True

    monkeypatch.setattr(
        "canresearch.core.capture_prepare.CansubClient",
        lambda *args, **kwargs: FakeClient(),
    )
    monkeypatch.setattr(
        "canresearch.core.capture_prepare._run_passive_rx_proof",
        lambda *args, **kwargs: None,
    )
    assert CANSUB_PHY_PUT_VERIFIED is False

    with pytest.raises(LiveResearchError) as exc:
        prepare_channel_for_capture("desk.local", 1, client=FakeClient())
    assert exc.value.code == "timing_prepare_required"
    assert not put_called["value"]


def test_prepare_active_mismatch_blocks_before_session(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)
    result = check_channel_timing_preflight(
        "desk.local",
        1,
        config_path=ensure_config,
        phy=PHY_250K_1M,
        channel_state="error_active",
    )
    assert result.state == TimingCompatibility.MISMATCH

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="error_active")

    with pytest.raises(LiveResearchError) as exc:
        prepare_channel_for_capture("desk.local", 1, config_path=ensure_config, client=FakeClient())
    assert exc.value.code == "timing_mismatch"


def test_connection_policy_none_is_backward_compatible(tmp_path: Path) -> None:
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
    result = check_channel_timing_preflight(
        "desk.local",
        1,
        config_path=config_path,
        phy=PHY_250K_1M,
        channel_state="stopped",
    )
    assert result.state == TimingCompatibility.INACTIVE_OR_AMBIGUOUS

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="stopped")

    prepare_channel_for_capture(
        "desk.local",
        1,
        config_path=config_path,
        client=FakeClient(),
    )
