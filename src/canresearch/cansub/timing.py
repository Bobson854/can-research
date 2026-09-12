"""CANsub PHY timing helpers.

The CANsub REST API returns bit-timing as ``timing`` / ``timing_data`` segment
objects (``brp``, ``seg1``, ``seg2``, ``sjw``), not nominal bitrate fields.

Nominal and data bitrates are derived using the 80 MHz CAN clock documented for
CANsub in the official ``python-can-cansub`` integration package. This matches the
segment values observed on tested desk hardware and the CSS REST API examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# Documented CANsub CAN clock (python-can-cansub / CSS integration).
CANSUB_CAN_CLOCK_HZ = 80_000_000


@dataclass(frozen=True, slots=True)
class BitTimingSegments:
    brp: int
    seg1: int
    seg2: int
    sjw: int

    @classmethod
    def from_mapping(cls, value: Any) -> BitTimingSegments | None:
        if not isinstance(value, dict):
            return None
        try:
            brp = int(value["brp"])
            seg1 = int(value["seg1"])
            seg2 = int(value["seg2"])
            sjw = int(value["sjw"])
        except (KeyError, TypeError, ValueError):
            return None
        if brp <= 0 or seg1 < 0 or seg2 < 0 or sjw <= 0:
            return None
        return cls(brp=brp, seg1=seg1, seg2=seg2, sjw=sjw)

    def bit_quanta(self) -> int:
        return self.seg1 + self.seg2 + 1

    def bitrate_bps(self) -> int | None:
        quanta = self.bit_quanta()
        divisor = self.brp * quanta
        if divisor <= 0:
            return None
        if CANSUB_CAN_CLOCK_HZ % divisor != 0:
            return None
        return CANSUB_CAN_CLOCK_HZ // divisor


@dataclass(frozen=True, slots=True)
class ChannelBitrates:
    nominal_bps: int | None
    data_bps: int | None
    nominal_segments: BitTimingSegments | None = None
    data_segments: BitTimingSegments | None = None

    @classmethod
    def from_phy(cls, phy: dict[str, Any] | None) -> ChannelBitrates:
        if phy is None:
            return cls(nominal_bps=None, data_bps=None)
        nominal = BitTimingSegments.from_mapping(phy.get("timing"))
        data = BitTimingSegments.from_mapping(phy.get("timing_data"))
        return cls(
            nominal_bps=nominal.bitrate_bps() if nominal else None,
            data_bps=data.bitrate_bps() if data else None,
            nominal_segments=nominal,
            data_segments=data,
        )


def format_bitrate_bps(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value >= 1_000_000 and value % 1_000_000 == 0:
        return f"{value // 1_000_000} Mbit/s"
    if value >= 1_000 and value % 1_000 == 0:
        return f"{value // 1_000} kbit/s"
    return f"{value} bit/s"


def format_channel_bitrates(bitrates: ChannelBitrates) -> str:
    nominal = format_bitrate_bps(bitrates.nominal_bps)
    if bitrates.data_bps is None:
        return f"{nominal} nominal"
    data = format_bitrate_bps(bitrates.data_bps)
    return f"{nominal} nominal / {data} data"


class TimingCompatibility(StrEnum):
    NOT_CONFIGURED = "not_configured"
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    INACTIVE_OR_AMBIGUOUS = "inactive_or_ambiguous"


class ConnectionPolicy(StrEnum):
    """Per-channel passive RX preparation policy."""

    NONE = "none"
    ENSURE_BEFORE_RX = "ensure_before_rx"


# Verified on CANsub.2 API 04.00 (FW 02.04.00) via successful webCAN PUT observation.
CANSUB_PHY_PUT_VERIFIED = True

# webCAN PUT defaults when config does not override (API 04.00 observed schema).
DEFAULT_PHY_PUT_LISTEN_ONLY = False
DEFAULT_PHY_PUT_AUTO_RESET = True
DEFAULT_PHY_PUT_ERROR_FRAMES = False
DEFAULT_PHY_PUT_TX_ACK_FRAMES = True

INACTIVE_CHANNEL_STATES = frozenset(
    {"stopped", "inactive", "init", "uninitialized", "idle"},
)

DEFAULT_STOPPED_PHY_BITRATES = (250_000, 1_000_000)


def is_channel_state_active(channel_state: str | None) -> bool:
    if channel_state is None:
        return False
    return channel_state.lower() not in INACTIVE_CHANNEL_STATES


def is_default_stopped_phy(phy: dict[str, Any] | None) -> bool:
    bitrates = ChannelBitrates.from_phy(phy)
    return (
        bitrates.nominal_bps == DEFAULT_STOPPED_PHY_BITRATES[0]
        and bitrates.data_bps == DEFAULT_STOPPED_PHY_BITRATES[1]
    )


def evaluate_timing_compatibility(
    expectation: ChannelTimingExpectation,
    phy: dict[str, Any] | None,
    *,
    channel_state: str | None,
) -> TimingCompatibility:
    """Compare configured timing against PHY, respecting channel activity."""
    actual = ChannelBitrates.from_phy(phy)
    if not is_channel_state_active(channel_state):
        if actual.nominal_bps is None:
            return TimingCompatibility.UNKNOWN
        return TimingCompatibility.INACTIVE_OR_AMBIGUOUS
    return compare_expected_bitrates(expectation, actual)


@dataclass(frozen=True, slots=True)
class ChannelTimingExpectation:
    channel: int
    nominal_bitrate: int
    data_bitrate: int | None = None
    timing: dict[str, int] | None = None
    timing_data: dict[str, int] | None = None
    listen_only: bool | None = None
    auto_reset: bool | None = None
    error_frames: bool | None = None
    tx_ack_frames: bool | None = None
    connection_policy: ConnectionPolicy = ConnectionPolicy.NONE

    def expected_bitrates(self) -> ChannelBitrates:
        return ChannelBitrates(
            nominal_bps=self.nominal_bitrate,
            data_bps=self.data_bitrate,
        )

    def expected_summary(self) -> str:
        return format_channel_bitrates(self.expected_bitrates())


def compare_expected_bitrates(
    expected: ChannelTimingExpectation,
    actual: ChannelBitrates,
) -> TimingCompatibility:
    if actual.nominal_bps is None:
        return TimingCompatibility.UNKNOWN
    if actual.nominal_bps != expected.nominal_bitrate:
        return TimingCompatibility.MISMATCH
    if expected.data_bitrate is not None:
        if actual.data_bps is None:
            return TimingCompatibility.UNKNOWN
        if actual.data_bps != expected.data_bitrate:
            return TimingCompatibility.MISMATCH
    return TimingCompatibility.MATCH


# Known-valid CANsub timing pairs used for optional apply-phy when config stores
# bitrates only (matches common CSS / desk presets at 80 MHz).
TIMING_PRESET_BY_BITRATES: dict[tuple[int, int | None], dict[str, dict[str, int]]] = {
    (250_000, 1_000_000): {
        "timing": {"brp": 4, "seg1": 63, "seg2": 16, "sjw": 4},
        "timing_data": {"brp": 4, "seg1": 15, "seg2": 4, "sjw": 4},
    },
    (500_000, 1_000_000): {
        # Observed successful webCAN PUT on API 04.00 (80 MHz, 500k / 1M).
        "timing": {"brp": 4, "seg1": 31, "seg2": 8, "sjw": 4},
        "timing_data": {"brp": 4, "seg1": 15, "seg2": 4, "sjw": 4},
    },
}


def compare_phy_to_expectation(
    expectation: ChannelTimingExpectation,
    phy: dict[str, Any] | None,
) -> TimingCompatibility:
    """Compare GET /phy to configured expectation (ignores channel activity)."""
    actual = ChannelBitrates.from_phy(phy)
    bitrate_state = compare_expected_bitrates(expectation, actual)
    if bitrate_state != TimingCompatibility.MATCH:
        return bitrate_state
    if expectation.timing is not None and expectation.timing_data is not None:
        if phy is None:
            return TimingCompatibility.UNKNOWN
        for key, expected_seg in (
            ("timing", expectation.timing),
            ("timing_data", expectation.timing_data),
        ):
            parsed = BitTimingSegments.from_mapping(phy.get(key))
            expected = BitTimingSegments.from_mapping(expected_seg)
            if parsed is None or expected is None or parsed != expected:
                return TimingCompatibility.MISMATCH
    return TimingCompatibility.MATCH


def resolve_apply_phy_payload(
    expectation: ChannelTimingExpectation,
    current_phy: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a verified PUT /api/can/{channel}/phy JSON body from config."""
    _ = current_phy
    if expectation.timing and expectation.timing_data:
        timing = dict(expectation.timing)
        timing_data = dict(expectation.timing_data)
    else:
        preset = TIMING_PRESET_BY_BITRATES.get(
            (expectation.nominal_bitrate, expectation.data_bitrate),
        )
        if preset is None:
            return None
        timing = dict(preset["timing"])
        timing_data = dict(preset["timing_data"])

    payload: dict[str, Any] = {
        "listen_only": (
            expectation.listen_only
            if expectation.listen_only is not None
            else DEFAULT_PHY_PUT_LISTEN_ONLY
        ),
        "auto_reset": (
            expectation.auto_reset
            if expectation.auto_reset is not None
            else DEFAULT_PHY_PUT_AUTO_RESET
        ),
        "error_frames": (
            expectation.error_frames
            if expectation.error_frames is not None
            else DEFAULT_PHY_PUT_ERROR_FRAMES
        ),
        "tx_ack_frames": (
            expectation.tx_ack_frames
            if expectation.tx_ack_frames is not None
            else DEFAULT_PHY_PUT_TX_ACK_FRAMES
        ),
        "timing": timing,
        "timing_data": timing_data,
    }
    return payload


def validate_phy_put_payload(payload: dict[str, Any]) -> list[str]:
    """Return structural validation errors for a planned PUT /phy body."""
    errors: list[str] = []
    for key in ("timing", "timing_data"):
        segments = payload.get(key)
        if not isinstance(segments, dict):
            errors.append(f"{key} must be an object")
            continue
        parsed = BitTimingSegments.from_mapping(segments)
        if parsed is None:
            errors.append(f"{key} must contain positive brp/seg1/seg2/sjw integers")
    for flag in ("listen_only", "auto_reset", "error_frames", "tx_ack_frames"):
        value = payload.get(flag)
        if not isinstance(value, bool):
            errors.append(f"{flag} must be a boolean")
    return errors
