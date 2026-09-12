"""Shared CANsub PHY timing preflight for live research operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from canresearch.cansub.client import CansubClient, get_channel_info
from canresearch.cansub.timing import (
    ChannelBitrates,
    ChannelTimingExpectation,
    ConnectionPolicy,
    TimingCompatibility,
    compare_expected_bitrates,
    evaluate_timing_compatibility,
    format_channel_bitrates,
    is_default_stopped_phy,
)
from canresearch.config import load_config
from canresearch.core.live_errors import LiveResearchError


@dataclass(frozen=True, slots=True)
class TimingPreflightResult:
    channel: int
    host: str
    state: TimingCompatibility
    channel_state: str | None
    expected: ChannelTimingExpectation | None
    expected_summary: str | None
    actual: ChannelBitrates
    actual_summary: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "host": self.host,
            "timing_state": self.state.value,
            "channel_state": self.channel_state,
            "expected": self.expected_summary,
            "actual": self.actual_summary,
            "remediation": self.remediation,
        }


def get_channel_timing_expectation(
    channel: int,
    *,
    config_path: Path | None = None,
) -> ChannelTimingExpectation | None:
    return load_config(config_path).cansub.channels.get(channel)


def check_channel_timing_preflight(
    host: str,
    channel: int,
    *,
    timeout: float = 5.0,
    verify_tls: bool = False,
    config_path: Path | None = None,
    client: CansubClient | None = None,
    phy: dict[str, Any] | None = None,
    channel_state: str | None = None,
) -> TimingPreflightResult:
    """Compare configured expected timing against device-reported PHY timing."""
    expectation = get_channel_timing_expectation(channel, config_path=config_path)
    if expectation is None:
        return TimingPreflightResult(
            channel=channel,
            host=host,
            state=TimingCompatibility.NOT_CONFIGURED,
            channel_state=channel_state,
            expected=None,
            expected_summary=None,
            actual=ChannelBitrates(nominal_bps=None, data_bps=None),
            actual_summary="not checked (no expected timing configured)",
            remediation=(
                "No expected timing configured for this channel. "
                "Add [cansub.channels.<n>] to data/config.toml to enable preflight."
            ),
        )

    resolved_state = channel_state
    resolved_phy = phy
    if resolved_phy is None or resolved_state is None:
        if client is not None:
            status = client.get_channel_info(channel)
            resolved_phy = status.phy
            resolved_state = status.state
        else:
            status = get_channel_info(
                host,
                channel,
                timeout=timeout,
                verify_tls=verify_tls,
                include_phy=True,
            )
            resolved_phy = status.phy
            resolved_state = status.state

    actual = ChannelBitrates.from_phy(resolved_phy)
    state = evaluate_timing_compatibility(
        expectation,
        resolved_phy,
        channel_state=resolved_state,
    )
    expected_summary = expectation.expected_summary()
    actual_summary = format_channel_bitrates(actual)

    if state == TimingCompatibility.MATCH:
        remediation = "Timing matches configured expectation."
    elif state == TimingCompatibility.INACTIVE_OR_AMBIGUOUS:
        state_label = resolved_state or "inactive"
        ensure_policy = ConnectionPolicy.ENSURE_BEFORE_RX.value
        bitrates_match = (
            compare_expected_bitrates(expectation, actual)
            == TimingCompatibility.MATCH
        )
        if is_default_stopped_phy(resolved_phy):
            remediation = (
                f"Channel {channel} is {state_label} with PHY {actual_summary}. "
                "This may be the CANsub stopped/default state and is not proof of a "
                "live-bus mismatch. "
                f'Use connection_policy = "{ensure_policy}" to prepare the configured '
                f"{expected_summary} profile, verify read-back, and require passive "
                "frame evidence before capture."
            )
        elif bitrates_match:
            remediation = (
                f"Channel {channel} is {state_label} with PHY {actual_summary}. "
                "This is not proof of active bus traffic. "
                f'With connection_policy = "{ensure_policy}", CAN Research will '
                "verify/configure the expected timing and require passive frame "
                "evidence before capture."
            )
        else:
            remediation = (
                f"Channel {channel} is {state_label} with PHY {actual_summary}. "
                "Stopped/inactive PHY is not proof of a live-bus mismatch. "
                f'Use connection_policy = "{ensure_policy}" to apply the configured '
                f"{expected_summary} profile, verify read-back, and require passive "
                "frame evidence before capture."
            )
    elif state == TimingCompatibility.MISMATCH:
        remediation = (
            "Channel is active but PHY timing does not match configured expectation. "
            "Correct timing in webCAN or CSS vendor tools, then verify with:\n"
            f"  canresearch device timing-check {channel}"
        )
    else:
        remediation = (
            "Device PHY timing could not be verified. Confirm the channel is reachable "
            "and GET /api/can/{channel}/phy returns timing segments, or correct timing "
            "in webCAN before capture."
        )

    return TimingPreflightResult(
        channel=channel,
        host=host,
        state=state,
        channel_state=resolved_state,
        expected=expectation,
        expected_summary=expected_summary,
        actual=actual,
        actual_summary=actual_summary,
        remediation=remediation,
    )


def enforce_channel_timing_preflight(
    host: str,
    channel: int,
    *,
    timeout: float = 5.0,
    verify_tls: bool = False,
    config_path: Path | None = None,
    client: CansubClient | None = None,
    phy: dict[str, Any] | None = None,
    channel_state: str | None = None,
) -> TimingPreflightResult | None:
    """Raise LiveResearchError when configured timing does not permit capture."""
    result = check_channel_timing_preflight(
        host,
        channel,
        timeout=timeout,
        verify_tls=verify_tls,
        config_path=config_path,
        client=client,
        phy=phy,
        channel_state=channel_state,
    )
    if result.state in {
        TimingCompatibility.NOT_CONFIGURED,
        TimingCompatibility.MATCH,
        TimingCompatibility.INACTIVE_OR_AMBIGUOUS,
    }:
        return result
    if result.state == TimingCompatibility.MISMATCH:
        message = (
            f"Channel {channel} PHY timing does not match configured expectation.\n"
            f"  Channel state: {result.channel_state or 'unknown'}\n"
            f"  Expected: {result.expected_summary}\n"
            f"  Actual:   {result.actual_summary}\n"
            f"{result.remediation}"
        )
        raise LiveResearchError("timing_mismatch", message)
    message = (
        f"Channel {channel} PHY timing could not be verified against configured expectation.\n"
        f"  Channel state: {result.channel_state or 'unknown'}\n"
        f"  Expected: {result.expected_summary}\n"
        f"  Actual:   {result.actual_summary}\n"
        f"{result.remediation}"
    )
    raise LiveResearchError("timing_unknown", message)
