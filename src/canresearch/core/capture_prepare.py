"""Configured CAN timing preparation before passive RX capture."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from canresearch.cansub.client import CansubClient, get_channel_info
from canresearch.cansub.exceptions import CansubApiError
from canresearch.cansub.timing import (
    CANSUB_PHY_PUT_VERIFIED,
    ConnectionPolicy,
    TimingCompatibility,
    compare_phy_to_expectation,
    resolve_apply_phy_payload,
    validate_phy_put_payload,
)
from canresearch.cansub.ws_client import ConnectFn, receive_frames_sync
from canresearch.config import load_config
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.timing_preflight import (
    TimingPreflightResult,
    check_channel_timing_preflight,
    get_channel_timing_expectation,
)

if TYPE_CHECKING:
    pass

PASSIVE_RX_PROOF_DURATION_S = 0.75


def prepare_channel_for_capture(
    host: str,
    channel: int,
    *,
    timeout: float = 5.0,
    verify_tls: bool = False,
    config_path: Path | None = None,
    client: CansubClient | None = None,
    connect: ConnectFn | None = None,
) -> TimingPreflightResult | None:
    """Prepare a channel for passive RX without creating a session row."""
    expectation = get_channel_timing_expectation(channel, config_path=config_path)
    if expectation is None:
        return None

    cansub_client = client or CansubClient(host, timeout=timeout, verify_tls=verify_tls)
    result = check_channel_timing_preflight(
        host,
        channel,
        timeout=timeout,
        verify_tls=verify_tls,
        config_path=config_path,
        client=cansub_client,
    )

    if expectation.connection_policy == ConnectionPolicy.NONE:
        if result.state == TimingCompatibility.MISMATCH:
            _raise_from_result(result)
        if result.state == TimingCompatibility.UNKNOWN:
            _raise_unknown(result)
        return result

    if result.state == TimingCompatibility.MATCH:
        _run_passive_rx_proof(
            host,
            channel,
            timeout=timeout,
            verify_tls=verify_tls,
            connect=connect,
        )
        return result

    if result.state == TimingCompatibility.INACTIVE_OR_AMBIGUOUS:
        _prepare_inactive_channel(
            host,
            channel,
            expectation=expectation,
            result=result,
            client=cansub_client,
            timeout=timeout,
            verify_tls=verify_tls,
            connect=connect,
        )
        return check_channel_timing_preflight(
            host,
            channel,
            timeout=timeout,
            verify_tls=verify_tls,
            config_path=config_path,
            client=cansub_client,
        )

    if result.state == TimingCompatibility.MISMATCH:
        _raise_from_result(result)
    if result.state == TimingCompatibility.UNKNOWN:
        _raise_unknown(result)
    return result


def _prepare_inactive_channel(
    host: str,
    channel: int,
    *,
    expectation,
    result: TimingPreflightResult,
    client: CansubClient,
    timeout: float,
    verify_tls: bool,
    connect: ConnectFn | None,
) -> None:
    if not CANSUB_PHY_PUT_VERIFIED:
        message = (
            f"Channel {channel} is inactive with uninitialised/default PHY "
            f"({result.actual_summary}). Configure the expected "
            f"{result.expected_summary} in webCAN before capture.\n"
            "Automatic PHY PUT is disabled because the REST contract is not verified.\n"
            f"{result.remediation}"
        )
        raise LiveResearchError("timing_prepare_required", message)

    payload = resolve_apply_phy_payload(expectation)
    if payload is None:
        message = (
            "Configured bitrates do not map to a known timing preset and no explicit "
            "timing/timing_data tables were provided in config."
        )
        raise LiveResearchError("timing_prepare_required", message)
    validation_errors = validate_phy_put_payload(payload)
    if validation_errors:
        joined = "; ".join(validation_errors)
        raise LiveResearchError("timing_prepare_required", joined)
    try:
        client.set_channel_phy(channel, payload)
    except CansubApiError as exc:
        message = (
            f"PUT /api/can/{channel}/phy failed before capture: {exc}\n"
            f"{result.remediation}"
        )
        raise LiveResearchError("timing_put_failed", message) from exc
    readback_phy = client.get_channel_phy(channel)
    verify_state = compare_phy_to_expectation(expectation, readback_phy)
    if verify_state != TimingCompatibility.MATCH:
        message = (
            f"Channel {channel} PHY read-back after PUT does not match configuration.\n"
            f"  Expected: {result.expected_summary}\n"
            f"  Read-back: {readback_phy}\n"
            f"  State: {verify_state.value}\n"
            f"{result.remediation}"
        )
        raise LiveResearchError("timing_verify_failed", message)
    _run_passive_rx_proof(
        host,
        channel,
        timeout=timeout,
        verify_tls=verify_tls,
        connect=connect,
    )


def _run_passive_rx_proof(
    host: str,
    channel: int,
    *,
    timeout: float,
    verify_tls: bool,
    connect: ConnectFn | None,
) -> None:
    try:
        proof = receive_frames_sync(
            host,
            channel,
            duration=PASSIVE_RX_PROOF_DURATION_S,
            timeout=timeout,
            verify_tls=verify_tls,
            connect=connect,
            release_slot=True,
        )
    except Exception as exc:
        message = (
            f"Passive RX proof failed on channel {channel} before capture: {exc}"
        )
        raise LiveResearchError("timing_proof_failed", message) from exc
    if not proof.connected:
        message = (
            f"Passive RX proof could not connect on channel {channel} before capture."
        )
        raise LiveResearchError("timing_proof_failed", message)
    if proof.frame_count <= 0:
        message = (
            f"Passive RX proof on channel {channel} connected but observed no CAN "
            f"frames in {proof.duration_s:.2f}s. Check wiring, bus activity, and PHY "
            "timing before capture."
        )
        raise LiveResearchError("timing_proof_failed", message)


def _raise_from_result(result: TimingPreflightResult) -> None:
    message = (
        f"Channel {result.channel} PHY timing does not match configured expectation.\n"
        f"  Channel state: {result.channel_state or 'unknown'}\n"
        f"  Expected: {result.expected_summary}\n"
        f"  Actual:   {result.actual_summary}\n"
        f"{result.remediation}"
    )
    raise LiveResearchError("timing_mismatch", message)


def _raise_unknown(result: TimingPreflightResult) -> None:
    message = (
        f"Channel {result.channel} PHY timing could not be verified.\n"
        f"  Expected: {result.expected_summary}\n"
        f"  Actual:   {result.actual_summary}\n"
        f"{result.remediation}"
    )
    raise LiveResearchError("timing_unknown", message)
