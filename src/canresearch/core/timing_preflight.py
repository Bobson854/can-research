"""Shared CANsub PHY timing preflight for live research operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from canresearch.cansub.client import CansubClient, get_channel_info
from canresearch.cansub.timing import (
    ChannelBitrates,
    ChannelTimingExpectation,
    TimingCompatibility,
    compare_expected_bitrates,
    format_channel_bitrates,
)
from canresearch.config import load_config
from canresearch.core.live_errors import LiveResearchError


@dataclass(frozen=True, slots=True)
class TimingPreflightResult:
    channel: int
    host: str
    state: TimingCompatibility
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
) -> TimingPreflightResult:
    """Compare configured expected timing against device-reported PHY timing."""
    expectation = get_channel_timing_expectation(channel, config_path=config_path)
    if expectation is None:
        return TimingPreflightResult(
            channel=channel,
            host=host,
            state=TimingCompatibility.NOT_CONFIGURED,
            expected=None,
            expected_summary=None,
            actual=ChannelBitrates(nominal_bps=None, data_bps=None),
            actual_summary="not checked (no expected timing configured)",
            remediation=(
                "No expected timing configured for this channel. "
                "Add [cansub.channels.<n>] to data/config.toml to enable preflight."
            ),
        )

    if phy is not None:
        actual = ChannelBitrates.from_phy(phy)
    elif client is not None:
        actual = ChannelBitrates.from_phy(client.get_channel_phy(channel))
    else:
        status = get_channel_info(
            host,
            channel,
            timeout=timeout,
            verify_tls=verify_tls,
            include_phy=True,
        )
        actual = ChannelBitrates.from_phy(status.phy)

    state = compare_expected_bitrates(expectation, actual)
    expected_summary = expectation.expected_summary()
    actual_summary = format_channel_bitrates(actual)

    if state == TimingCompatibility.MATCH:
        remediation = "Timing matches configured expectation."
    elif state == TimingCompatibility.MISMATCH:
        remediation = (
            "Correct CANsub channel timing in webCAN or CSS vendor tools to match the "
            "configured expectation, then verify with:\n"
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
    )
    if result.state == TimingCompatibility.NOT_CONFIGURED:
        return None
    if result.state == TimingCompatibility.MATCH:
        return result
    if result.state == TimingCompatibility.MISMATCH:
        message = (
            f"Channel {channel} PHY timing does not match configured expectation.\n"
            f"  Expected: {result.expected_summary}\n"
            f"  Actual:   {result.actual_summary}\n"
            f"{result.remediation}"
        )
        raise LiveResearchError("timing_mismatch", message)
    message = (
        f"Channel {channel} PHY timing could not be verified against configured expectation.\n"
        f"  Expected: {result.expected_summary}\n"
        f"  Actual:   {result.actual_summary}\n"
        f"{result.remediation}"
    )
    raise LiveResearchError("timing_unknown", message)
