"""J1939 64-bit NAME parsing for Address Claim messages."""

from __future__ import annotations

from dataclasses import dataclass

PGN_ADDRESS_CLAIM = 60928
NULL_SOURCE_ADDRESS = 0xFE
GLOBAL_DESTINATION = 0xFF

INVALID_NODE_SOURCE_ADDRESSES = frozenset({GLOBAL_DESTINATION})


@dataclass(frozen=True, slots=True)
class J1939Name:
    """Parsed J1939 NAME fields from a 64-bit value."""

    raw_value: int
    identity_number: int
    manufacturer_code: int
    ecu_instance: int
    function_instance: int
    function: int
    reserved: int
    vehicle_system: int
    vehicle_system_instance: int
    industry_group: int
    arbitrary_address_capable: bool

    @property
    def name_hex(self) -> str:
        return f"0x{self.raw_value:016X}"

    def format_summary(self) -> list[str]:
        aac = "yes" if self.arbitrary_address_capable else "no"
        return [
            f"NAME: {self.name_hex}",
            f"Manufacturer code: {self.manufacturer_code}",
            f"Function: {self.function}",
            f"Function instance: {self.function_instance}",
            f"ECU instance: {self.ecu_instance}",
            f"Vehicle system: {self.vehicle_system}",
            f"Industry group: {self.industry_group}",
            f"Arbitrary address capable: {aac}",
            f"Identity number: {self.identity_number}",
        ]


def parse_j1939_name_payload(payload: bytes) -> J1939Name:
    """Parse an 8-byte Address Claim payload into J1939 NAME fields.

    Payload bytes are transmitted least-significant byte first on J1939.
    """
    if len(payload) < 8:
        msg = f"NAME payload must be at least 8 bytes, got {len(payload)}"
        raise ValueError(msg)
    raw = int.from_bytes(payload[:8], byteorder="little")
    return parse_j1939_name_value(raw)


def parse_j1939_name_value(raw_value: int) -> J1939Name:
    """Parse a 64-bit J1939 NAME integer."""
    if raw_value < 0 or raw_value > 0xFFFFFFFFFFFFFFFF:
        msg = f"NAME must fit in 64 bits, got {raw_value}"
        raise ValueError(msg)
    return J1939Name(
        raw_value=raw_value,
        identity_number=raw_value & 0x1FFFFF,
        manufacturer_code=(raw_value >> 21) & 0x7FF,
        ecu_instance=(raw_value >> 32) & 0x7,
        function_instance=(raw_value >> 35) & 0x1F,
        function=(raw_value >> 40) & 0xFF,
        reserved=(raw_value >> 48) & 0x1,
        vehicle_system=(raw_value >> 49) & 0x7F,
        vehicle_system_instance=(raw_value >> 56) & 0x0F,
        industry_group=(raw_value >> 60) & 0x7,
        arbitrary_address_capable=bool((raw_value >> 63) & 0x1),
    )


def parse_j1939_name_text(text: str) -> J1939Name:
    """Parse a NAME from hex text such as 0x1122334455667788."""
    cleaned = text.strip().lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if not cleaned:
        msg = "J1939 NAME hex value is required"
        raise ValueError(msg)
    if len(cleaned) > 16:
        msg = f"J1939 NAME hex value too long: {text!r}"
        raise ValueError(msg)
    cleaned = cleaned.zfill(16)
    raw = int(cleaned, 16)
    return parse_j1939_name_value(raw)


def build_j1939_name_payload(
    *,
    identity_number: int,
    manufacturer_code: int,
    ecu_instance: int = 0,
    function_instance: int = 0,
    function: int = 0,
    vehicle_system: int = 0,
    vehicle_system_instance: int = 0,
    industry_group: int = 0,
    arbitrary_address_capable: bool = True,
    reserved: int = 0,
) -> bytes:
    """Build an 8-byte Address Claim payload from NAME fields."""
    raw = identity_number & 0x1FFFFF
    raw |= (manufacturer_code & 0x7FF) << 21
    raw |= (ecu_instance & 0x7) << 32
    raw |= (function_instance & 0x1F) << 35
    raw |= (function & 0xFF) << 40
    raw |= (reserved & 0x1) << 48
    raw |= (vehicle_system & 0x7F) << 49
    raw |= (vehicle_system_instance & 0x0F) << 56
    raw |= (industry_group & 0x7) << 60
    raw |= (1 if arbitrary_address_capable else 0) << 63
    return raw.to_bytes(8, byteorder="little")
