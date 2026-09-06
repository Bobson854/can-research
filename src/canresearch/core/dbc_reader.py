"""Read Vector-style DBC files into internal DBC models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from canresearch.core.dbc_identifiers import sanitize_dbc_identifier
from canresearch.core.dbc_knowledge import DbcLoadError, DbcLoadWarning
from canresearch.core.dbc_model import DbcDatabase, DbcMessage, DbcSignal
from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.research_frames import parse_can_id_fields

_BO_RE = re.compile(r"^BO_\s+(\d+)\s+(\S+)\s*:\s*(\d+)\s+(\S+)\s*$")
_SG_RE = re.compile(
    r'^\s+SG_\s+(\S+)\s+:\s+(\d+)\|(\d+)@(\d)([+-])\s+\(([^,]+),([^)]+)\)\s+'
    r'\[([^|]+)\|([^\]]+)\]\s+"([^"]*)"\s+(\S+)\s*$'
)


@dataclass(slots=True)
class _MessageBuilder:
    dbc_frame_id: int
    name: str
    dlc: int
    transmitter: str
    signals: list[DbcSignal] = field(default_factory=list)


def decode_dbc_frame_id(dbc_frame_id: int) -> tuple[int, bool]:
    """Return (can_id, is_extended) from a Vector BO_ frame id."""
    if dbc_frame_id < 0:
        msg = f"Invalid DBC frame id: {dbc_frame_id}"
        raise DbcLoadError(msg)
    if dbc_frame_id > 0x1FFFFFFF:
        is_extended = dbc_frame_id >= 0x80000000
        can_id = dbc_frame_id & 0x1FFFFFFF if is_extended else dbc_frame_id
        return can_id, is_extended
    if dbc_frame_id > 0x7FF:
        return dbc_frame_id & 0x1FFFFFFF, True
    return dbc_frame_id, False


def _parse_float(text: str) -> float:
    cleaned = text.strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def _message_from_builder(builder: _MessageBuilder) -> DbcMessage:
    can_id, is_extended = decode_dbc_frame_id(builder.dbc_frame_id)
    j1939 = parse_can_id_fields(can_id, is_extended=is_extended)
    pgn = j1939.get("pgn") or 0
    source_address = j1939.get("source_address") or 0
    destination_address = j1939.get("destination_address")
    if is_extended:
        try:
            parsed = parse_j1939_id(can_id)
            pgn = parsed.pgn
            source_address = parsed.source_address
            destination_address = parsed.destination_address
        except ValueError:
            pass
    return DbcMessage(
        name=builder.name,
        can_id=can_id,
        dbc_frame_id=builder.dbc_frame_id,
        dlc=builder.dlc,
        transmitter=builder.transmitter,
        pgn=pgn,
        source_address=source_address,
        destination_address=destination_address,
        origin="dbc_import",
        signals=tuple(builder.signals),
    )


def read_dbc_file(path: Path) -> tuple[DbcDatabase, tuple[DbcLoadWarning, ...]]:
    """Parse a DBC file without mutating it on disk."""
    if not path.is_file():
        msg = f"DBC file not found: {path}"
        raise DbcLoadError(msg)

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    warnings: list[DbcLoadWarning] = []
    nodes: list[str] = []
    comments: list[str] = []
    version = ""
    builders: list[_MessageBuilder] = []
    current: _MessageBuilder | None = None
    seen_frame_ids: dict[int, str] = {}
    in_ns_block = False

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "NS_:" or line.startswith("NS_ "):
            in_ns_block = True
            continue
        if in_ns_block:
            if line.startswith("BS_"):
                in_ns_block = False
            else:
                continue
        if line.startswith("BS_"):
            continue
        if line.startswith("VERSION "):
            match = re.match(r'^VERSION\s+"([^"]*)"', line)
            if match:
                version = match.group(1)
            continue
        if line.startswith("BU_:"):
            tail = line[4:].strip()
            if tail:
                nodes.extend(tail.split())
            continue
        if line.startswith('CM_ "'):
            comments.append(line[4:].strip().strip('"'))
            continue
        if line.startswith(("BA_", "VAL_", "SIG_", "BO_TX_", "CAT_", "EV_", "ENVVAR")):
            continue

        bo_match = _BO_RE.match(raw_line.rstrip())
        if bo_match:
            dbc_frame_id = int(bo_match.group(1))
            name = bo_match.group(2)
            dlc = int(bo_match.group(3))
            transmitter = bo_match.group(4)
            if dbc_frame_id in seen_frame_ids:
                warnings.append(
                    DbcLoadWarning(
                        category="duplicate_frame_id",
                        message=(
                            f"Duplicate BO_ id {dbc_frame_id} "
                            f"({seen_frame_ids[dbc_frame_id]} vs {name})"
                        ),
                        line_number=line_number,
                    )
                )
            else:
                seen_frame_ids[dbc_frame_id] = name
            if name != sanitize_dbc_identifier(name, prefix_if_digit="Msg"):
                warnings.append(
                    DbcLoadWarning(
                        category="identifier_strict_compat",
                        message=f"Message name may fail strict parsers: {name}",
                        line_number=line_number,
                    )
                )
            current = _MessageBuilder(
                dbc_frame_id=dbc_frame_id,
                name=name,
                dlc=dlc,
                transmitter=transmitter,
            )
            builders.append(current)
            continue

        sg_match = _SG_RE.match(raw_line.rstrip())
        if sg_match:
            if current is None:
                msg = f"Signal definition before message (line {line_number})"
                raise DbcLoadError(msg)
            sig_name = sg_match.group(1)
            start_bit = int(sg_match.group(2))
            bit_length = int(sg_match.group(3))
            byte_order = int(sg_match.group(4))
            signed = sg_match.group(5) == "-"
            factor = _parse_float(sg_match.group(6))
            offset = _parse_float(sg_match.group(7))
            minimum = _parse_float(sg_match.group(8))
            maximum = _parse_float(sg_match.group(9))
            unit = sg_match.group(10)
            if sig_name != sanitize_dbc_identifier(sig_name, prefix_if_digit="Sig"):
                warnings.append(
                    DbcLoadWarning(
                        category="identifier_strict_compat",
                        message=f"Signal name may fail strict parsers: {sig_name}",
                        line_number=line_number,
                    )
                )
            signal_names = {signal.name for signal in current.signals}
            if sig_name in signal_names:
                warnings.append(
                    DbcLoadWarning(
                        category="duplicate_signal_name",
                        message=f"Duplicate signal {sig_name} in message {current.name}",
                        line_number=line_number,
                    )
                )
            current.signals.append(
                DbcSignal(
                    name=sig_name,
                    start_bit=start_bit,
                    bit_length=bit_length,
                    byte_order=byte_order,
                    signed=signed,
                    factor=factor,
                    offset=offset,
                    minimum=minimum,
                    maximum=maximum,
                    unit=unit,
                    pgn=0,
                    spn=0,
                    origin="dbc_import",
                    reference_backed=False,
                )
            )
            continue

        if line.startswith("BO_ "):
            msg = f"Unparseable DBC message line {line_number}: {raw_line.strip()}"
            raise DbcLoadError(msg)
        if raw_line.lstrip().startswith("SG_ ") and ":" in line:
            msg = f"Unparseable DBC signal line {line_number}: {raw_line.strip()}"
            raise DbcLoadError(msg)

    if not builders:
        msg = f"No messages found in DBC file: {path}"
        raise DbcLoadError(msg)

    messages = tuple(_message_from_builder(builder) for builder in builders)
    database = DbcDatabase(
        version=version,
        nodes=tuple(nodes),
        messages=messages,
        provenance=None,
        comments=tuple(comments),
    )
    return database, tuple(warnings)
