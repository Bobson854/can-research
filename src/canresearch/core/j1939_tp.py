"""J1939 Transport Protocol (TP.CM / TP.DT) offline reassembly."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from canresearch.core.j1939 import J1939Identifier, parse_j1939_id
from canresearch.core.j1939_logical_messages import (
    LogicalJ1939Message,
    TransportMode,
    categorize_j1939_frame,
)
from canresearch.core.jsonl_capture_store import iter_frames_from_path
from canresearch.core.sessions import CanFrame, get_session, resolve_session_frames_path
from canresearch.storage.database import default_db_path

PGN_TP_CM = 60416
PGN_TP_DT = 60160
TRANSPORT_PGNS: frozenset[int] = frozenset({59392, PGN_TP_DT, 60415, PGN_TP_CM})
GLOBAL_DESTINATION = 0xFF

CM_BAM = 32
CM_RTS = 16
CM_CTS = 17
CM_EOM = 19
CM_ABORT = 255

BYTES_PER_DT_PACKET = 7
MAX_TP_PACKET_COUNT = 255
MAX_TP_PAYLOAD_BYTES = MAX_TP_PACKET_COUNT * BYTES_PER_DT_PACKET
DEFAULT_TRANSPORT_TIMEOUT_US = 1_250_000


class TransferState(StrEnum):
    ANNOUNCED = "announced"
    AWAITING_CTS = "awaiting_cts"
    RECEIVING = "receiving"
    AWAITING_EOM = "awaiting_eom"
    COMPLETED = "completed"
    ABORTED = "aborted"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class TransportKey:
    mode: TransportMode
    source_address: int
    destination_address: int
    transported_pgn: int


@dataclass(frozen=True, slots=True)
class TransportWarning:
    category: str
    message: str
    source_address: int | None = None
    destination_address: int | None = None
    transported_pgn: int | None = None
    timestamp_us: int | None = None
    packets_received: int | None = None
    packets_expected: int | None = None


@dataclass
class TransportStats:
    tp_cm_frames: int = 0
    tp_dt_frames: int = 0
    transfers_started: int = 0
    transfers_completed: int = 0
    transfers_incomplete: int = 0
    transfers_aborted: int = 0


@dataclass(frozen=True, slots=True)
class TransportResult:
    completed_messages: tuple[LogicalJ1939Message, ...]
    warnings: tuple[TransportWarning, ...]
    stats: TransportStats


@dataclass
class _ActiveTransfer:
    key: TransportKey
    mode: TransportMode
    source_address: int
    destination_address: int
    transported_pgn: int
    priority: int
    total_size: int
    packet_count: int
    packets: dict[int, bytes]
    expected_seq: int
    started_at_us: int
    last_seen_at_us: int
    cm_can_id: int | None
    dt_frame_count: int
    state: TransferState
    cts_window_remaining: int | None = None
    eom_seen: bool = False
    missing_eom: bool = False


def encode_j1939_can_id(
    *,
    pgn: int,
    source_address: int,
    destination_address: int | None = None,
    priority: int = 6,
) -> int:
    """Build a 29-bit J1939 CAN identifier (inverse of parse_j1939_id)."""
    data_page = (pgn >> 16) & 0x1
    pdu_format = (pgn >> 8) & 0xFF
    if pdu_format < 240:
        if destination_address is None:
            msg = "destination_address required for PDU1 PGN"
            raise ValueError(msg)
        pdu_specific = destination_address & 0xFF
    else:
        pdu_specific = pgn & 0xFF
    return (
        ((priority & 0x7) << 26)
        | (data_page << 24)
        | (pdu_format << 16)
        | (pdu_specific << 8)
        | (source_address & 0xFF)
    )


def build_tp_cm_bam(
    *,
    total_size: int,
    packet_count: int,
    transported_pgn: int,
    source_address: int,
    priority: int = 6,
) -> tuple[int, bytes]:
    can_id = encode_j1939_can_id(
        pgn=PGN_TP_CM,
        source_address=source_address,
        destination_address=GLOBAL_DESTINATION,
        priority=priority,
    )
    data = bytes(
        [
            CM_BAM,
            total_size & 0xFF,
            (total_size >> 8) & 0xFF,
            packet_count & 0xFF,
            0xFF,
            transported_pgn & 0xFF,
            (transported_pgn >> 8) & 0xFF,
            (transported_pgn >> 16) & 0xFF,
        ]
    )
    return can_id, data


def build_tp_cm_rts(
    *,
    total_size: int,
    packet_count: int,
    transported_pgn: int,
    source_address: int,
    destination_address: int,
    max_packets_per_cts: int = 0xFF,
    priority: int = 6,
) -> tuple[int, bytes]:
    can_id = encode_j1939_can_id(
        pgn=PGN_TP_CM,
        source_address=source_address,
        destination_address=destination_address,
        priority=priority,
    )
    data = bytes(
        [
            CM_RTS,
            total_size & 0xFF,
            (total_size >> 8) & 0xFF,
            packet_count & 0xFF,
            max_packets_per_cts & 0xFF,
            transported_pgn & 0xFF,
            (transported_pgn >> 8) & 0xFF,
            (transported_pgn >> 16) & 0xFF,
        ]
    )
    return can_id, data


def build_tp_cm_cts(
    *,
    packets_to_send: int,
    next_sequence: int,
    transported_pgn: int,
    source_address: int,
    destination_address: int,
    priority: int = 6,
) -> tuple[int, bytes]:
    can_id = encode_j1939_can_id(
        pgn=PGN_TP_CM,
        source_address=source_address,
        destination_address=destination_address,
        priority=priority,
    )
    data = bytes(
        [
            CM_CTS,
            packets_to_send & 0xFF,
            next_sequence & 0xFF,
            0xFF,
            0xFF,
            transported_pgn & 0xFF,
            (transported_pgn >> 8) & 0xFF,
            (transported_pgn >> 16) & 0xFF,
        ]
    )
    return can_id, data


def build_tp_cm_eom(
    *,
    total_size: int,
    packet_count: int,
    transported_pgn: int,
    source_address: int,
    destination_address: int,
    priority: int = 6,
) -> tuple[int, bytes]:
    can_id = encode_j1939_can_id(
        pgn=PGN_TP_CM,
        source_address=source_address,
        destination_address=destination_address,
        priority=priority,
    )
    data = bytes(
        [
            CM_EOM,
            total_size & 0xFF,
            (total_size >> 8) & 0xFF,
            packet_count & 0xFF,
            0xFF,
            transported_pgn & 0xFF,
            (transported_pgn >> 8) & 0xFF,
            (transported_pgn >> 16) & 0xFF,
        ]
    )
    return can_id, data


def build_tp_cm_abort(
    *,
    reason: int,
    transported_pgn: int,
    source_address: int,
    destination_address: int,
    priority: int = 6,
) -> tuple[int, bytes]:
    can_id = encode_j1939_can_id(
        pgn=PGN_TP_CM,
        source_address=source_address,
        destination_address=destination_address,
        priority=priority,
    )
    data = bytes(
        [
            CM_ABORT,
            reason & 0xFF,
            0xFF,
            0xFF,
            0xFF,
            transported_pgn & 0xFF,
            (transported_pgn >> 8) & 0xFF,
            (transported_pgn >> 16) & 0xFF,
        ]
    )
    return can_id, data


def build_tp_dt(
    *,
    sequence: int,
    payload_chunk: bytes,
    source_address: int,
    destination_address: int,
    priority: int = 6,
) -> tuple[int, bytes]:
    chunk = payload_chunk[:BYTES_PER_DT_PACKET]
    data = bytes([sequence & 0xFF]) + chunk.ljust(BYTES_PER_DT_PACKET, b"\x00")
    can_id = encode_j1939_can_id(
        pgn=PGN_TP_DT,
        source_address=source_address,
        destination_address=destination_address,
        priority=priority,
    )
    return can_id, data


def expected_packet_count(total_size: int) -> int:
    if total_size <= 0:
        return 0
    return (total_size + BYTES_PER_DT_PACKET - 1) // BYTES_PER_DT_PACKET


def parse_transported_pgn(data: bytes) -> int:
    return data[5] | (data[6] << 8) | (data[7] << 16)


def parse_message_size(data: bytes) -> int:
    return data[1] | (data[2] << 8)


def reassemble_j1939_transport(
    frames: Iterable[CanFrame],
    *,
    timeout_us: int = DEFAULT_TRANSPORT_TIMEOUT_US,
) -> TransportResult:
    """Reassemble J1939 transport-protocol traffic from capture frames."""
    reassembler = _TransportReassembler(timeout_us=timeout_us)
    for frame in frames:
        reassembler.process_frame(frame)
    return reassembler.finalize()


def reassemble_session_transport(
    session_id: str,
    *,
    db_path: Path | None = None,
    timeout_us: int = DEFAULT_TRANSPORT_TIMEOUT_US,
) -> TransportResult:
    """Reassemble transport traffic from a saved capture session."""
    path = db_path or default_db_path()
    record = get_session(session_id, db_path=path)
    frames_path = resolve_session_frames_path(record)
    if not frames_path.exists():
        msg = f"Frame store not found: {frames_path}"
        raise FileNotFoundError(msg)
    return reassemble_j1939_transport(
        iter_frames_from_path(frames_path),
        timeout_us=timeout_us,
    )


class _TransportReassembler:
    def __init__(self, *, timeout_us: int) -> None:
        self.timeout_us = timeout_us
        self.active: dict[TransportKey, _ActiveTransfer] = {}
        self.completed: list[LogicalJ1939Message] = []
        self.warnings: list[TransportWarning] = []
        self.stats = TransportStats()
        self._started_keys: set[TransportKey] = set()

    def finalize(self) -> TransportResult:
        for transfer in list(self.active.values()):
            if transfer.state not in {TransferState.COMPLETED, TransferState.ABORTED}:
                self._close_incomplete(transfer, timestamp_us=transfer.last_seen_at_us)
        return TransportResult(
            completed_messages=tuple(self.completed),
            warnings=tuple(self.warnings),
            stats=self.stats,
        )

    def process_frame(self, frame: CanFrame) -> None:
        if categorize_j1939_frame(frame) != "j1939" or frame.can_id is None:
            return

        self._expire_stale(frame.timestamp_us)

        try:
            parsed = parse_j1939_id(frame.can_id)
        except ValueError:
            return

        payload = frame.data
        if frame.dlc is not None and len(payload) > frame.dlc:
            payload = payload[: frame.dlc]
        if len(payload) < 1:
            return

        if parsed.pgn == PGN_TP_CM:
            self.stats.tp_cm_frames += 1
            self._handle_tp_cm(frame, parsed, payload)
        elif parsed.pgn == PGN_TP_DT:
            self.stats.tp_dt_frames += 1
            self._handle_tp_dt(frame, parsed, payload)

    def _expire_stale(self, timestamp_us: int) -> None:
        for _key, transfer in list(self.active.items()):
            if timestamp_us - transfer.last_seen_at_us > self.timeout_us:
                self._add_warning(
                    "transport_timeout",
                    (
                        f"Transport timed out for PGN {transfer.transported_pgn} "
                        f"SA {transfer.source_address:02X} -> DA "
                        f"{transfer.destination_address:02X}"
                    ),
                    transfer,
                    timestamp_us=timestamp_us,
                )
                self._close_incomplete(transfer, timestamp_us=timestamp_us)

    def _handle_tp_cm(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
    ) -> None:
        if len(payload) < 8:
            self._add_warning(
                "invalid_tp_cm",
                "TP.CM frame shorter than 8 bytes",
                timestamp_us=frame.timestamp_us,
                source_address=parsed.source_address,
                destination_address=parsed.destination_address,
            )
            return

        control = payload[0]
        transported_pgn = parse_transported_pgn(payload)

        if control == CM_BAM:
            self._start_bam(frame, parsed, payload, transported_pgn)
        elif control == CM_RTS:
            self._start_rts(frame, parsed, payload, transported_pgn)
        elif control == CM_CTS:
            self._handle_cts(frame, parsed, payload, transported_pgn)
        elif control == CM_EOM:
            self._handle_eom(frame, parsed, payload, transported_pgn)
        elif control == CM_ABORT:
            self._handle_abort(frame, parsed, payload, transported_pgn)
        else:
            self._add_warning(
                "invalid_tp_cm",
                f"Unsupported TP.CM control byte {control}",
                timestamp_us=frame.timestamp_us,
                source_address=parsed.source_address,
                destination_address=parsed.destination_address,
                transported_pgn=transported_pgn,
            )

    def _start_bam(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
        transported_pgn: int,
    ) -> None:
        if parsed.destination_address != GLOBAL_DESTINATION:
            self._add_warning(
                "invalid_tp_cm",
                "BAM must use global destination 0xFF",
                timestamp_us=frame.timestamp_us,
                source_address=parsed.source_address,
                destination_address=parsed.destination_address,
                transported_pgn=transported_pgn,
            )
            return

        total_size, packet_count, ok = self._validate_announcement(
            payload,
            timestamp_us=frame.timestamp_us,
            source_address=parsed.source_address,
            destination_address=GLOBAL_DESTINATION,
            transported_pgn=transported_pgn,
        )
        if not ok:
            return

        key = TransportKey(
            mode=TransportMode.BAM,
            source_address=parsed.source_address,
            destination_address=GLOBAL_DESTINATION,
            transported_pgn=transported_pgn,
        )
        self._replace_active(key, frame, parsed, total_size, packet_count, TransportMode.BAM)

    def _start_rts(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
        transported_pgn: int,
    ) -> None:
        if parsed.destination_address is None or parsed.destination_address == GLOBAL_DESTINATION:
            self._add_warning(
                "invalid_tp_cm",
                "RTS requires a specific destination address",
                timestamp_us=frame.timestamp_us,
                source_address=parsed.source_address,
                transported_pgn=transported_pgn,
            )
            return

        total_size, packet_count, ok = self._validate_announcement(
            payload,
            timestamp_us=frame.timestamp_us,
            source_address=parsed.source_address,
            destination_address=parsed.destination_address,
            transported_pgn=transported_pgn,
        )
        if not ok:
            return

        key = TransportKey(
            mode=TransportMode.RTS_CTS,
            source_address=parsed.source_address,
            destination_address=parsed.destination_address,
            transported_pgn=transported_pgn,
        )
        transfer = self._replace_active(
            key,
            frame,
            parsed,
            total_size,
            packet_count,
            TransportMode.RTS_CTS,
        )
        transfer.state = TransferState.AWAITING_CTS

    def _handle_cts(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
        transported_pgn: int,
    ) -> None:
        if parsed.destination_address is None:
            return
        sender = parsed.destination_address
        receiver = parsed.source_address
        key = TransportKey(
            mode=TransportMode.RTS_CTS,
            source_address=sender,
            destination_address=receiver,
            transported_pgn=transported_pgn,
        )
        transfer = self.active.get(key)
        if transfer is None or transfer.state in {
            TransferState.COMPLETED,
            TransferState.ABORTED,
            TransferState.INVALID,
        }:
            self._add_warning(
                "unexpected_cts",
                "CTS for unknown or inactive RTS/CTS transfer",
                timestamp_us=frame.timestamp_us,
                source_address=sender,
                destination_address=receiver,
                transported_pgn=transported_pgn,
            )
            return

        packets_to_send = payload[1]
        next_sequence = payload[2]
        if packets_to_send == 0 or next_sequence < 1:
            self._add_warning(
                "unexpected_cts",
                "Invalid CTS window",
                transfer,
                timestamp_us=frame.timestamp_us,
            )
            self._invalidate(transfer)
            return

        transfer.last_seen_at_us = frame.timestamp_us
        transfer.expected_seq = next_sequence
        transfer.cts_window_remaining = packets_to_send
        transfer.state = TransferState.RECEIVING

    def _handle_eom(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
        transported_pgn: int,
    ) -> None:
        if parsed.destination_address is None:
            return
        sender = parsed.destination_address
        receiver = parsed.source_address
        key = TransportKey(
            mode=TransportMode.RTS_CTS,
            source_address=sender,
            destination_address=receiver,
            transported_pgn=transported_pgn,
        )
        transfer = self.active.get(key)
        if transfer is None:
            self._add_warning(
                "unexpected_eom_ack",
                "EOM ACK for unknown RTS/CTS transfer",
                timestamp_us=frame.timestamp_us,
                source_address=sender,
                destination_address=receiver,
                transported_pgn=transported_pgn,
            )
            return

        transfer.last_seen_at_us = frame.timestamp_us
        transfer.eom_seen = True
        announced_size = parse_message_size(payload)
        announced_packets = payload[3]
        if announced_size != transfer.total_size or announced_packets != transfer.packet_count:
            self._add_warning(
                "unexpected_eom_ack",
                "EOM ACK size/packet count mismatch",
                transfer,
                timestamp_us=frame.timestamp_us,
            )
            self._invalidate(transfer)
            return

        if len(transfer.packets) == transfer.packet_count:
            self._complete_transfer(transfer, frame.timestamp_us)

    def _handle_abort(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
        transported_pgn: int,
    ) -> None:
        reason = payload[1]
        for key, transfer in list(self.active.items()):
            if transfer.transported_pgn != transported_pgn:
                continue
            if not self._parties_match_transfer(parsed, transfer):
                continue
            self._add_warning(
                "transport_abort",
                f"Transport aborted (reason {reason})",
                transfer,
                timestamp_us=frame.timestamp_us,
            )
            transfer.state = TransferState.ABORTED
            self.stats.transfers_aborted += 1
            del self.active[key]
            return

        self._add_warning(
            "transport_abort",
            f"Transport abort for inactive transfer (reason {reason})",
            timestamp_us=frame.timestamp_us,
            source_address=parsed.source_address,
            destination_address=parsed.destination_address,
            transported_pgn=transported_pgn,
        )

    def _handle_tp_dt(
        self,
        frame: CanFrame,
        parsed: J1939Identifier,
        payload: bytes,
    ) -> None:
        if parsed.destination_address is None:
            return

        transfer = self._find_active_transfer_for_dt(parsed)
        if transfer is None:
            return

        seq = payload[0]
        chunk = payload[1:8]

        if transfer.mode == TransportMode.RTS_CTS and transfer.state == TransferState.AWAITING_CTS:
            self._add_warning(
                "unexpected_sequence",
                "TP.DT received before CTS window opened",
                transfer,
                timestamp_us=frame.timestamp_us,
            )
            self._invalidate(transfer)
            return

        if (
            transfer.mode == TransportMode.RTS_CTS
            and transfer.state == TransferState.AWAITING_EOM
            and len(transfer.packets) >= transfer.packet_count
        ):
            return

        if seq in transfer.packets:
            if transfer.packets[seq] == chunk:
                self._add_warning(
                    "duplicate_packet",
                    f"Duplicate TP.DT sequence {seq} ignored",
                    transfer,
                    timestamp_us=frame.timestamp_us,
                )
            else:
                self._add_warning(
                    "conflicting_duplicate_packet",
                    f"Conflicting TP.DT sequence {seq}",
                    transfer,
                    timestamp_us=frame.timestamp_us,
                )
                self._invalidate(transfer)
            return

        if seq != transfer.expected_seq:
            self._add_warning(
                "unexpected_sequence",
                f"Expected TP.DT sequence {transfer.expected_seq}, got {seq}",
                transfer,
                timestamp_us=frame.timestamp_us,
            )
            self._invalidate(transfer)
            return

        transfer.packets[seq] = chunk
        transfer.expected_seq += 1
        transfer.dt_frame_count += 1
        transfer.last_seen_at_us = frame.timestamp_us

        if transfer.mode == TransportMode.RTS_CTS and transfer.cts_window_remaining is not None:
            transfer.cts_window_remaining -= 1
            if transfer.cts_window_remaining == 0 and len(transfer.packets) < transfer.packet_count:
                transfer.state = TransferState.AWAITING_CTS

        if len(transfer.packets) == transfer.packet_count:
            if transfer.mode == TransportMode.BAM or transfer.eom_seen:
                self._complete_transfer(transfer, frame.timestamp_us)
            else:
                self._complete_transfer(transfer, frame.timestamp_us, missing_eom=True)

    def _find_active_transfer_for_dt(self, parsed: J1939Identifier) -> _ActiveTransfer | None:
        inactive = {
            TransferState.COMPLETED,
            TransferState.ABORTED,
            TransferState.INVALID,
        }
        if parsed.destination_address == GLOBAL_DESTINATION:
            matches = [
                transfer
                for transfer in self.active.values()
                if transfer.mode == TransportMode.BAM
                and transfer.source_address == parsed.source_address
                and transfer.state not in inactive
            ]
            if not matches:
                return None
            if len(matches) == 1:
                return matches[0]
            return max(matches, key=lambda item: item.started_at_us)

        assert parsed.destination_address is not None
        matches = [
            transfer
            for transfer in self.active.values()
            if transfer.mode == TransportMode.RTS_CTS
            and transfer.source_address == parsed.source_address
            and transfer.destination_address == parsed.destination_address
            and transfer.state not in inactive
        ]
        if not matches:
            return None
        if len(matches) > 1:
            receiving = [
                transfer
                for transfer in matches
                if transfer.state in {TransferState.RECEIVING, TransferState.AWAITING_EOM}
            ]
            if len(receiving) == 1:
                return receiving[0]
        return matches[0]

    def _replace_active(
        self,
        key: TransportKey,
        frame: CanFrame,
        parsed: J1939Identifier,
        total_size: int,
        packet_count: int,
        mode: TransportMode,
    ) -> _ActiveTransfer:
        existing = self.active.get(key)
        if existing is not None and existing.state not in {
            TransferState.COMPLETED,
            TransferState.ABORTED,
        }:
            self._close_incomplete(existing, timestamp_us=frame.timestamp_us)

        transfer = _ActiveTransfer(
            key=key,
            mode=mode,
            source_address=key.source_address,
            destination_address=key.destination_address,
            transported_pgn=key.transported_pgn,
            priority=parsed.priority,
            total_size=total_size,
            packet_count=packet_count,
            packets={},
            expected_seq=1,
            started_at_us=frame.timestamp_us,
            last_seen_at_us=frame.timestamp_us,
            cm_can_id=frame.can_id,
            dt_frame_count=0,
            state=TransferState.ANNOUNCED,
        )
        self.active[key] = transfer
        if key not in self._started_keys:
            self._started_keys.add(key)
            self.stats.transfers_started += 1
        return transfer

    def _validate_announcement(
        self,
        payload: bytes,
        *,
        timestamp_us: int,
        source_address: int,
        destination_address: int,
        transported_pgn: int,
    ) -> tuple[int, int, bool]:
        total_size = parse_message_size(payload)
        packet_count = payload[3]

        if total_size < 1 or total_size > MAX_TP_PAYLOAD_BYTES:
            self._add_warning(
                "invalid_message_size",
                f"Invalid TP message size {total_size}",
                timestamp_us=timestamp_us,
                source_address=source_address,
                destination_address=destination_address,
                transported_pgn=transported_pgn,
            )
            return 0, 0, False

        expected = expected_packet_count(total_size)
        if packet_count < 1 or packet_count > MAX_TP_PACKET_COUNT or packet_count != expected:
            self._add_warning(
                "invalid_packet_count",
                (
                    f"Invalid TP packet count {packet_count} for size {total_size} "
                    f"(expected {expected})"
                ),
                timestamp_us=timestamp_us,
                source_address=source_address,
                destination_address=destination_address,
                transported_pgn=transported_pgn,
            )
            return 0, 0, False

        return total_size, packet_count, True

    def _complete_transfer(
        self,
        transfer: _ActiveTransfer,
        timestamp_us: int,
        *,
        missing_eom: bool = False,
    ) -> None:
        payload = self._build_payload(transfer)
        message = LogicalJ1939Message(
            pgn=PGN_TP_CM,
            source_address=transfer.source_address,
            destination_address=transfer.destination_address,
            priority=transfer.priority,
            timestamp_us=timestamp_us,
            payload=payload,
            is_transport=True,
            transport_mode=transfer.mode,
            transported_pgn=transfer.transported_pgn,
            packet_count=transfer.packet_count,
            payload_length=len(payload),
            started_at_us=transfer.started_at_us,
            completed_at_us=timestamp_us,
            source_frame_count=1 + transfer.dt_frame_count,
            cm_can_id=transfer.cm_can_id,
        )
        self.completed.append(message)
        transfer.state = TransferState.COMPLETED
        self.stats.transfers_completed += 1
        if missing_eom:
            self._add_warning(
                "missing_eom_ack",
                "All TP.DT packets received but EOM ACK was missing",
                transfer,
                timestamp_us=timestamp_us,
            )
        del self.active[transfer.key]

    def _build_payload(self, transfer: _ActiveTransfer) -> bytes:
        buffer = bytearray()
        for seq in range(1, transfer.packet_count + 1):
            buffer.extend(transfer.packets[seq])
        return bytes(buffer[: transfer.total_size])

    def _close_incomplete(self, transfer: _ActiveTransfer, *, timestamp_us: int) -> None:
        if transfer.state in {TransferState.COMPLETED, TransferState.ABORTED}:
            return
        self._add_warning(
            "incomplete_transport",
            (
                f"Incomplete transport for PGN {transfer.transported_pgn}: "
                f"{len(transfer.packets)}/{transfer.packet_count} packets"
            ),
            transfer,
            timestamp_us=timestamp_us,
            packets_received=len(transfer.packets),
            packets_expected=transfer.packet_count,
        )
        self.stats.transfers_incomplete += 1
        transfer.state = TransferState.INVALID
        self.active.pop(transfer.key, None)

    def _invalidate(self, transfer: _ActiveTransfer) -> None:
        transfer.state = TransferState.INVALID
        self.active.pop(transfer.key, None)

    @staticmethod
    def _parties_match_transfer(parsed: J1939Identifier, transfer: _ActiveTransfer) -> bool:
        parties = {parsed.source_address, parsed.destination_address}
        return transfer.source_address in parties and transfer.destination_address in parties

    def _add_warning(
        self,
        category: str,
        message: str,
        transfer: _ActiveTransfer | None = None,
        *,
        timestamp_us: int | None = None,
        source_address: int | None = None,
        destination_address: int | None = None,
        transported_pgn: int | None = None,
        packets_received: int | None = None,
        packets_expected: int | None = None,
    ) -> None:
        self.warnings.append(
            TransportWarning(
                category=category,
                message=message,
                source_address=transfer.source_address if transfer else source_address,
                destination_address=(
                    transfer.destination_address if transfer else destination_address
                ),
                transported_pgn=transfer.transported_pgn if transfer else transported_pgn,
                timestamp_us=timestamp_us,
                packets_received=packets_received,
                packets_expected=packets_expected,
            )
        )
