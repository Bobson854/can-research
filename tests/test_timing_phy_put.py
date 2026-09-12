"""Tests for verified CANsub PHY PUT contract (API 04.00 webCAN observation)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from canresearch.cansub.client import CansubClient
from canresearch.cansub.exceptions import CansubApiError
from canresearch.cansub.timing import (
    CANSUB_PHY_PUT_VERIFIED,
    ChannelTimingExpectation,
    TimingCompatibility,
    compare_phy_to_expectation,
    resolve_apply_phy_payload,
    validate_phy_put_payload,
)
from canresearch.cansub.ws_client import CansubRxResult
import canresearch.core.capture_prepare as capture_prepare_mod
from canresearch.core.live_errors import LiveResearchError

# Bind before conftest autouse replaces the module attribute with a noop.
_REAL_PREPARE = capture_prepare_mod.prepare_channel_for_capture
from tests.test_timing_preflight import PHY_250K_1M, PHY_500K_1M

OBSERVED_PUT_500K_1M = {
    "listen_only": False,
    "auto_reset": True,
    "error_frames": False,
    "tx_ack_frames": True,
    "timing": {"brp": 4, "seg1": 31, "seg2": 8, "sjw": 4},
    "timing_data": {"brp": 4, "seg1": 15, "seg2": 4, "sjw": 4},
}


def test_phy_put_verified_flag() -> None:
    assert CANSUB_PHY_PUT_VERIFIED is True


def test_resolve_apply_phy_payload_matches_webcan_schema() -> None:
    expectation = ChannelTimingExpectation(
        channel=1,
        nominal_bitrate=500_000,
        data_bitrate=1_000_000,
    )
    payload = resolve_apply_phy_payload(expectation)
    assert payload == OBSERVED_PUT_500K_1M


def test_validate_phy_put_payload_requires_tx_ack_frames() -> None:
    incomplete = dict(OBSERVED_PUT_500K_1M)
    del incomplete["tx_ack_frames"]
    errors = validate_phy_put_payload(incomplete)
    assert any("tx_ack_frames" in item for item in errors)
    assert validate_phy_put_payload(OBSERVED_PUT_500K_1M) == []


def test_compare_phy_to_expectation_by_bitrate() -> None:
    expectation = ChannelTimingExpectation(
        channel=1,
        nominal_bitrate=500_000,
        data_bitrate=1_000_000,
    )
    assert (
        compare_phy_to_expectation(expectation, PHY_500K_1M)
        == TimingCompatibility.MATCH
    )
    assert (
        compare_phy_to_expectation(expectation, PHY_250K_1M)
        == TimingCompatibility.MISMATCH
    )


def test_set_channel_phy_put_path_and_empty_200(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_put_json(path: str, payload: dict) -> None:
        captured["path"] = path
        captured["payload"] = payload
        return None

    client = CansubClient("example.test")
    monkeypatch.setattr(client, "put_json", fake_put_json)
    result = client.set_channel_phy(2, OBSERVED_PUT_500K_1M)
    assert captured["path"] == "/api/can/2/phy"
    assert captured["payload"] == OBSERVED_PUT_500K_1M
    assert result == OBSERVED_PUT_500K_1M


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


def test_prepare_active_match_does_not_put(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)
    put_calls: list[dict] = []

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_500K_1M, state="error_active")

        def set_channel_phy(self, channel: int, payload: dict):
            put_calls.append(payload)
            return payload

    monkeypatch.setattr(
        "canresearch.core.capture_prepare._run_passive_rx_proof",
        lambda *args, **kwargs: None,
    )
    _REAL_PREPARE("desk.local", 1, config_path=ensure_config, client=FakeClient())
    assert put_calls == []


def test_prepare_active_mismatch_does_not_put(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)
    put_calls: list[dict] = []

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="error_active")

        def set_channel_phy(self, channel: int, payload: dict):
            put_calls.append(payload)
            return payload

    with pytest.raises(LiveResearchError) as exc:
        _REAL_PREPARE("desk.local", 1, config_path=ensure_config, client=FakeClient())
    assert exc.value.code == "timing_mismatch"
    assert put_calls == []


def test_prepare_inactive_performs_put_and_readback(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)
    put_payloads: list[dict] = []
    readback = OBSERVED_PUT_500K_1M.copy()

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="stopped")

        def get_channel_phy(self, channel: int):
            _ = channel
            return readback

        def set_channel_phy(self, channel: int, payload: dict):
            put_payloads.append(payload)
            return payload

    monkeypatch.setattr(
        "canresearch.core.capture_prepare._run_passive_rx_proof",
        lambda *args, **kwargs: None,
    )
    _REAL_PREPARE("desk.local", 1, config_path=ensure_config, client=FakeClient())
    assert put_payloads == [OBSERVED_PUT_500K_1M]


def test_prepare_put_failure_is_safe(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="stopped")

        def set_channel_phy(self, channel: int, payload: dict):
            _ = channel, payload
            raise CansubApiError("bad request", status_code=400)

    with pytest.raises(LiveResearchError) as exc:
        _REAL_PREPARE("desk.local", 1, config_path=ensure_config, client=FakeClient())
    assert exc.value.code == "timing_put_failed"


def test_prepare_readback_failure_blocks_capture(
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

        def set_channel_phy(self, channel: int, payload: dict):
            _ = channel, payload
            return payload

    with pytest.raises(LiveResearchError) as exc:
        _REAL_PREPARE("desk.local", 1, config_path=ensure_config, client=FakeClient())
    assert exc.value.code == "timing_verify_failed"


def test_passive_proof_without_frames_blocks(
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)

    def fake_rx(*args, **kwargs):
        _ = args, kwargs
        return CansubRxResult(
            host="desk.local",
            channel=1,
            connected=True,
            duration_s=0.75,
            frame_count=0,
            exit_reason="completed",
        )

    monkeypatch.setattr(
        "canresearch.core.capture_prepare.receive_frames_sync",
        fake_rx,
    )
    with pytest.raises(LiveResearchError) as exc:
        _REAL_PREPARE(
            "desk.local",
            1,
            config_path=ensure_config,
            client=MagicMock(
                get_channel_info=MagicMock(
                    return_value=MagicMock(phy=PHY_500K_1M, state="error_active"),
                ),
            ),
        )
    assert exc.value.code == "timing_proof_failed"


def test_live_capture_no_session_on_prepare_failure(
    tmp_path: Path,
    ensure_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.cansub.live_capture import LiveCaptureRegistry
    from canresearch.storage.database import initialize

    db_path = tmp_path / "canresearch.db"
    initialize(db_path)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: ensure_config)

    class FakeClient:
        def get_channel_info(self, channel: int):
            _ = channel
            return MagicMock(phy=PHY_250K_1M, state="stopped")

        def get_channel_phy(self, channel: int):
            _ = channel
            return PHY_250K_1M

        def set_channel_phy(self, channel: int, payload: dict):
            _ = channel, payload
            return payload

    monkeypatch.setattr(
        "canresearch.cansub.live_capture.capture_prepare.prepare_channel_for_capture",
        _REAL_PREPARE,
    )
    monkeypatch.setattr(
        "canresearch.core.capture_prepare.CansubClient",
        lambda *args, **kwargs: FakeClient(),
    )
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)

    registry = LiveCaptureRegistry()
    with pytest.raises(LiveResearchError) as exc:
        registry.start("desk.local", 1, db_path=db_path)
    assert exc.value.code == "timing_verify_failed"
    assert registry.list_active_session_ids() == []
    conn = initialize(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()
    assert count == 0
