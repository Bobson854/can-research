"""Command-line interface for can-research."""

from __future__ import annotations

import click

from canresearch import __version__


@click.group()
@click.version_option(__version__, prog_name="canresearch")
def main() -> None:
    """CAN research tool for CANsub.2, J1939/ISOBUS, and MCP-assisted analysis."""


@main.group("device")
def device_group() -> None:
    """Discover and inspect CANsub.2 devices."""


@device_group.command("list")
@click.option("--host", default=None, help="Direct CANsub.2 host/IP (overrides config).")
@click.option("--timeout", default=None, type=float, help="HTTP timeout in seconds.")
def device_list(host: str | None, timeout: float | None) -> None:
    """List connected CANsub.2 devices (USB or Ethernet)."""
    try:
        resolved_host, resolved_timeout, verify_tls = _resolve_cansub_settings(host, timeout)
    except click.ClickException as exc:
        click.echo("CANsub.2 device discovery is not yet implemented.")
        click.echo("Planned: scan USB and Ethernet for CSS Electronics CANsub.2 adapters.")
        click.echo(exc.message)
        return

    _print_device_info(resolved_host, resolved_timeout, verify_tls)


@device_group.command("info")
@click.option("--host", default=None, help="CANsub.2 host/IP (overrides config).")
@click.option("--timeout", default=None, type=float, help="HTTP timeout in seconds.")
def device_info(host: str | None, timeout: float | None) -> None:
    """Show read-only information for a CANsub.2."""
    resolved_host, resolved_timeout, verify_tls = _resolve_cansub_settings(host, timeout)
    _print_device_info(resolved_host, resolved_timeout, verify_tls)


@device_group.command("channel-info")
@click.argument("channel", type=int)
@click.option("--host", default=None, help="CANsub.2 host/IP (overrides config).")
@click.option("--timeout", default=None, type=float, help="HTTP timeout in seconds.")
def device_channel_info(channel: int, host: str | None, timeout: float | None) -> None:
    """Show read-only status for a CAN channel."""
    resolved_host, resolved_timeout, verify_tls = _resolve_cansub_settings(host, timeout)
    _print_channel_info(resolved_host, channel, resolved_timeout, verify_tls)


def _resolve_cansub_settings(
    host: str | None,
    timeout: float | None,
) -> tuple[str, float, bool]:
    from canresearch.config import ConfigError, resolve_cansub_settings

    try:
        return resolve_cansub_settings(host, timeout, None)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


def _print_device_info(host: str, timeout: float, verify_tls: bool) -> None:
    from canresearch.cansub.client import probe_host
    from canresearch.cansub.exceptions import CansubError

    try:
        info = probe_host(host, timeout=timeout, verify_tls=verify_tls)
    except CansubError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo("CANsub.2")
    click.echo(f"Host:       {info.host}")
    click.echo(f"Status:     {info.status}")
    if info.device_id:
        click.echo(f"Device ID:  {info.device_id}")
    if info.api_version:
        click.echo(f"API:        {info.api_version}")
    if info.hardware_version:
        click.echo(f"Hardware:   {info.hardware_version}")
    if info.firmware_version:
        click.echo(f"Firmware:   {info.firmware_version}")
    if info.mac_address:
        click.echo(f"MAC:        {info.mac_address}")
    if info.usb_id:
        click.echo(f"USB ID:     {info.usb_id}")
    if info.channels:
        channel_text = ", ".join(str(ch) for ch in info.channels)
        click.echo(f"Channels:   {channel_text}")


def _print_channel_info(host: str, channel: int, timeout: float, verify_tls: bool) -> None:
    from canresearch.cansub.client import get_channel_info
    from canresearch.cansub.exceptions import CansubApiError, CansubError

    try:
        info = get_channel_info(host, channel, timeout=timeout, verify_tls=verify_tls)
    except CansubApiError as exc:
        if exc.status_code == 404:
            raise SystemExit(f"CAN channel {channel} not found on {host}") from exc
        raise SystemExit(str(exc)) from exc
    except CansubError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"CANsub.2 Channel {info.channel}")
    click.echo(f"Host:       {info.host}")
    click.echo(f"Channel:    {info.channel}")
    if info.state is not None:
        click.echo(f"State:      {info.state}")
    if info.frame_count is not None:
        click.echo(f"Frames:     {info.frame_count}")
    if info.frame_rate is not None:
        click.echo(f"Frame rate: {info.frame_rate} fps")
    if info.bus_load is not None:
        click.echo(f"Bus load:   {info.bus_load}%")
    if info.rx_error_count is not None:
        click.echo(f"RX errors:  {info.rx_error_count}")
    if info.tx_error_count is not None:
        click.echo(f"TX errors:  {info.tx_error_count}")
    if info.bus_error_count is not None:
        click.echo(f"Bus errors: {info.bus_error_count}")
    if info.phy:
        if "listen_only" in info.phy:
            click.echo(f"Listen only: {info.phy['listen_only']}")
        if "auto_reset" in info.phy:
            click.echo(f"Auto reset:  {info.phy['auto_reset']}")
        if "error_frames" in info.phy:
            click.echo(f"Error frames: {info.phy['error_frames']}")
        if "timing" in info.phy:
            click.echo(f"Timing:      {info.phy['timing']}")
        if "timing_data" in info.phy:
            click.echo(f"Timing data: {info.phy['timing_data']}")


@device_group.command("rx")
@click.argument("channel", type=int)
@click.option("--host", default=None, help="CANsub.2 host/IP (overrides config).")
@click.option("--timeout", default=None, type=float, help="HTTP timeout for channel validation.")
@click.option(
    "--duration",
    default=5.0,
    type=float,
    show_default=True,
    help="Seconds to wait for frames before exiting.",
)
@click.option("--max-frames", default=None, type=int, help="Stop after receiving this many frames.")
def device_rx(
    channel: int,
    host: str | None,
    timeout: float | None,
    duration: float,
    max_frames: int | None,
) -> None:
    """Receive CAN frames from a channel via WebSocket (read-only)."""
    resolved_host, resolved_timeout, verify_tls = _resolve_cansub_settings(host, timeout)
    _run_device_rx(
        resolved_host,
        channel,
        duration=duration,
        max_frames=max_frames,
        timeout=resolved_timeout,
        verify_tls=verify_tls,
    )


def _run_device_rx(
    host: str,
    channel: int,
    *,
    duration: float,
    max_frames: int | None,
    timeout: float,
    verify_tls: bool,
) -> None:
    from canresearch.cansub.exceptions import CansubWebSocketError
    from canresearch.cansub.ws_client import receive_frames_sync

    click.echo("CANsub.2 RX")
    click.echo(f"Host:       {host}")
    click.echo(f"Channel:    {channel}")
    click.echo(f"Duration:   {duration:g} s")

    def on_frame(frame) -> None:
        if frame.is_error_frame:
            click.echo(f"ERR  {frame.error_type}  ts={frame.timestamp_us}")
            return
        id_text = f"0x{frame.can_id:X}" if frame.can_id is not None else "?"
        data_text = frame.data.hex(" ") if frame.data else ""
        flags = []
        if frame.extended:
            flags.append("ext")
        if frame.fd:
            flags.append("fd")
        if frame.rtr:
            flags.append("rtr")
        if frame.tx_ack:
            flags.append("tx-ack")
        flag_text = f" ({', '.join(flags)})" if flags else ""
        click.echo(f"RX   {id_text}{flag_text}  dlc={frame.dlc}  {data_text}")

    try:
        result = receive_frames_sync(
            host,
            channel,
            duration=duration,
            max_frames=max_frames,
            timeout=timeout,
            verify_tls=verify_tls,
            on_frame=on_frame,
        )
    except KeyboardInterrupt:
        click.echo("Interrupted")
        raise SystemExit(0) from None
    except CansubWebSocketError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo("Status:     connected")
    click.echo(f"Frames:     {result.frame_count}")
    click.echo(f"Result:     {result.exit_reason}")


@main.group("config")
def config_group() -> None:
    """Manage local can-research configuration."""


@config_group.command("show")
def config_show() -> None:
    """Show current configuration."""
    from canresearch.config import default_config_path, load_config

    path = default_config_path()
    config = load_config(path)
    click.echo(f"Config file: {path}")
    if not path.exists():
        click.echo("Status:      not created (using defaults)")
    click.echo("[cansub]")
    click.echo(f"host = {config.cansub.host or '(not set)'}")
    click.echo(f"timeout = {config.cansub.timeout:g}")
    click.echo(f"verify_tls = {'true' if config.cansub.verify_tls else 'false'}")


@config_group.command("set-host")
@click.argument("host")
def config_set_host(host: str) -> None:
    """Save the default CANsub.2 host (hostname or IP)."""
    from canresearch.config import ConfigError, default_config_path, update_cansub_config

    try:
        update_cansub_config(host=host)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    click.echo(f"Saved CANsub host: {host.strip()}")
    click.echo(f"Config file: {default_config_path()}")


@config_group.command("set-timeout")
@click.argument("seconds", type=float)
def config_set_timeout(seconds: float) -> None:
    """Save the default CANsub.2 HTTP timeout."""
    from canresearch.config import ConfigError, default_config_path, update_cansub_config

    try:
        update_cansub_config(timeout=seconds)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    click.echo(f"Saved CANsub timeout: {seconds:g}s")
    click.echo(f"Config file: {default_config_path()}")


@config_group.command("set-verify-tls")
@click.argument("enabled", type=click.Choice(["true", "false"]))
def config_set_verify_tls(enabled: str) -> None:
    """Save whether TLS certificates are verified for CANsub.2."""
    from canresearch.config import default_config_path, update_cansub_config

    verify_tls = enabled == "true"
    update_cansub_config(verify_tls=verify_tls)
    click.echo(f"Saved CANsub verify_tls: {enabled}")
    click.echo(f"Config file: {default_config_path()}")


@main.group("capture")
def capture_group() -> None:
    """Start and stop live CAN capture sessions."""


@capture_group.command("start")
@click.option("--channel", required=True, type=int, help="CAN channel number.")
@click.option("--host", default=None, help="CANsub.2 host/IP (overrides config).")
@click.option("--name", default=None, help="Optional session label.")
@click.option(
    "--duration",
    default=5.0,
    type=float,
    show_default=True,
    help="Seconds to capture before stopping.",
)
@click.option("--max-frames", default=None, type=int, help="Stop after this many frames.")
@click.option("--timeout", default=None, type=float, help="HTTP timeout for device validation.")
def capture_start(
    channel: int,
    host: str | None,
    name: str | None,
    duration: float,
    max_frames: int | None,
    timeout: float | None,
) -> None:
    """Start a capture session and receive frames until duration or limit."""
    resolved_host, resolved_timeout, verify_tls = _resolve_cansub_settings(host, timeout)
    _run_capture_start(
        resolved_host,
        channel,
        name=name,
        duration=duration,
        max_frames=max_frames,
        timeout=resolved_timeout,
        verify_tls=verify_tls,
    )


def _run_capture_start(
    host: str,
    channel: int,
    *,
    name: str | None,
    duration: float,
    max_frames: int | None,
    timeout: float,
    verify_tls: bool,
) -> None:
    from canresearch.cansub.capture import run_capture
    from canresearch.cansub.exceptions import CansubWebSocketError

    try:
        result = run_capture(
            host,
            channel,
            duration=duration,
            max_frames=max_frames,
            name=name,
            timeout=timeout,
            verify_tls=verify_tls,
        )
    except KeyboardInterrupt:
        click.echo("Interrupted")
        raise SystemExit(0) from None
    except CansubWebSocketError as exc:
        raise SystemExit(str(exc)) from exc

    session = result.session
    click.echo("Capture complete")
    click.echo(f"Session:     {session.id}")
    if session.name:
        click.echo(f"Name:        {session.name}")
    if session.host:
        click.echo(f"Host:        {session.host}")
    if session.channel is not None:
        click.echo(f"Channel:     {session.channel}")
    click.echo(f"Duration:    {result.duration_s:g} s")
    click.echo(f"Frames:      {session.frame_count or 0}")
    if session.frame_store_path:
        click.echo(f"Store:       {session.frame_store_path}")
    click.echo(f"Status:      {session.status.value}")


@capture_group.command("stop")
@click.argument("session_id", required=False)
def capture_stop(session_id: str | None) -> None:
    """Stop an active background live capture."""
    from canresearch.cansub.live_capture import get_live_capture_registry, stop_live_capture
    from canresearch.core.live_errors import LiveResearchError

    target = session_id
    if target is None:
        active = get_live_capture_registry().list_active_session_ids()
        if not active:
            raise SystemExit("No active capture session.")
        if len(active) > 1:
            raise SystemExit(
                "Multiple active captures; specify session_id: "
                + ", ".join(active)
            )
        target = active[0]

    try:
        result = stop_live_capture(target)
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc

    click.echo(f"Session:     {result['session_id']}")
    click.echo(f"Stopped at:  {result.get('stopped_at') or '-'}")
    click.echo(f"Frames:      {result.get('frame_count', 0)}")
    duration = result.get("duration_s")
    if duration is not None:
        click.echo(f"Duration:    {duration:.1f}s")
    click.echo(f"Status:      {result.get('capture_state', '-')}")


@main.group("session")
def session_group() -> None:
    """Inspect recorded capture sessions."""


@session_group.command("list")
@click.option("--limit", default=20, show_default=True, help="Maximum sessions to show.")
def session_list(limit: int) -> None:
    """List stored capture sessions."""
    from canresearch.core.sessions import list_sessions

    sessions = list_sessions(limit=limit)
    if not sessions:
        click.echo("No capture sessions found.")
        return

    click.echo("Capture sessions")
    for session in sessions:
        name = session.name or "-"
        started = session.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        frames = session.frame_count if session.frame_count is not None else 0
        channel = session.channel if session.channel is not None else "-"
        click.echo(
            f"{session.id}  {session.status.value:<11}  ch={channel}  "
            f"frames={frames}  {started}  {name}"
        )


@session_group.command("analyze")
@click.argument("session_id")
@click.option(
    "--no-persist",
    is_flag=True,
    help="Compute analysis only; do not update observed_pgns or session status.",
)
def session_analyze(session_id: str, no_persist: bool) -> None:
    """Analyze a capture session for J1939 traffic and reference matches."""
    from canresearch.core.analysis import analyze_session

    try:
        summary = analyze_session(session_id, persist=not no_persist)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    _print_session_analysis(summary)


def _print_session_analysis(summary) -> None:
    click.echo(f"Session:              {summary.session_id}")
    if summary.session_name:
        click.echo(f"Name:                 {summary.session_name}")
    click.echo(f"Frames:               {summary.total_frames}")
    click.echo(f"J1939 frames:         {summary.j1939_frames}")
    click.echo(f"Non-J1939 frames:     {summary.non_j1939_frames}")
    if summary.error_frames:
        click.echo(f"Error frames:         {summary.error_frames}")
    if summary.malformed_frames:
        click.echo(f"Malformed frames:     {summary.malformed_frames}")
    click.echo(f"Unique PGNs:          {summary.unique_pgns}")
    click.echo(f"Unique source addrs:  {summary.unique_source_addresses}")
    click.echo(f"Known PGNs:           {summary.known_pgn_count}")
    click.echo(f"Unknown PGNs:         {summary.unknown_pgn_count}")

    if summary.transport_tp_cm_frames or summary.transport_tp_dt_frames:
        click.echo("")
        click.echo("Transport protocol")
        click.echo(f"TP.CM frames:         {summary.transport_tp_cm_frames}")
        click.echo(f"TP.DT frames:         {summary.transport_tp_dt_frames}")
        click.echo(f"Transfers started:    {summary.transport_transfers_started}")
        click.echo(f"Transfers completed:  {summary.transport_transfers_completed}")
        if summary.transport_transfers_incomplete:
            click.echo(f"Transfers incomplete: {summary.transport_transfers_incomplete}")
        if summary.transport_transfers_aborted:
            click.echo(f"Transfers aborted:    {summary.transport_transfers_aborted}")
        if summary.transport_warning_count:
            click.echo(f"Transport warnings:   {summary.transport_warning_count}")

    if (
        summary.identity_address_claim_frames
        or summary.identity_unique_nodes
        or summary.identity_address_conflicts
    ):
        click.echo("")
        click.echo("J1939 identity")
        click.echo(f"Address claims:        {summary.identity_address_claim_frames}")
        click.echo(f"Unique nodes:          {summary.identity_unique_nodes}")
        if summary.identity_claimed_addresses:
            sa_text = ", ".join(f"{sa:02X}" for sa in summary.identity_claimed_addresses)
            click.echo(f"Claimed addresses:     {sa_text}")
        if summary.identity_address_conflicts:
            click.echo(f"Address conflicts:     {summary.identity_address_conflicts}")

    if not summary.observed:
        click.echo("Observed traffic:     (none)")
        return

    click.echo("")
    click.echo("Observed traffic")
    header = (
        f"{'PGN':>6}  {'SA':>4}  {'DA':>4}  {'Count':>6}  "
        f"{'Rate':>8}  {'Classification':<18}  Name"
    )
    click.echo(header)
    for item in summary.observed:
        sa_text = f"0x{item.source_address:02X}"
        if item.destination_address is not None:
            da_text = f"0x{item.destination_address:02X}"
        else:
            da_text = "-"
        if summary.duration_s and summary.duration_s > 0:
            rate = item.frame_count / summary.duration_s
            rate_text = f"{rate:.2f}/s"
        else:
            rate_text = "-"
        name = item.display_name or "-"
        click.echo(
            f"{item.pgn:>6}  {sa_text:>4}  {da_text:>4}  {item.frame_count:>6}  "
            f"{rate_text:>8}  {item.classification:<18}  {name}"
        )
        if len(item.reference_matches) > 1:
            extra = ", ".join(
                match.origin
                for match in item.reference_matches
                if match.origin != item.classification
            )
            if extra:
                click.echo(f"{'':>6}  {'':>4}  {'':>4}  {'':>6}  {'':>8}  {'also:':<18}  {extra}")


@session_group.command("decode")
@click.argument("session_id")
@click.option("--pgn", type=int, default=None, help="Decode only this PGN.")
@click.option("--spn", type=int, default=None, help="Decode only this SPN.")
@click.option("--limit", type=int, default=None, help="Stop after this many decoded signals.")
def session_decode(
    session_id: str,
    pgn: int | None,
    spn: int | None,
    limit: int | None,
) -> None:
    """Decode SPN values for known standard J1939 PGNs in a saved session."""
    from canresearch.core.session_decode import decode_session

    try:
        summary = decode_session(
            session_id,
            pgn_filter=pgn,
            spn_filter=spn,
            limit=limit,
        )
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    _print_session_decode(summary)


def _print_session_decode(summary) -> None:
    click.echo(f"Session:              {summary.session_id}")
    if summary.session_name:
        click.echo(f"Name:                 {summary.session_name}")
    click.echo(f"Frames:               {summary.total_frames}")
    click.echo(f"J1939 frames:         {summary.j1939_frames}")
    click.echo(f"Known PGN frames:     {summary.known_pgn_frames}")
    click.echo(f"Unknown PGN frames:   {summary.unknown_pgn_frames}")
    click.echo(f"Decoded signals:      {summary.decoded_signal_count}")
    click.echo(f"Warnings:             {summary.warning_count}")

    if summary.warnings:
        click.echo("")
        click.echo("Warnings")
        for warning in summary.warnings[:20]:
            target = ""
            if warning.pgn is not None:
                target = f" PGN {warning.pgn}"
            if warning.spn is not None:
                target += f" SPN {warning.spn}"
            click.echo(f"  [{warning.category}]{target}: {warning.message}")
        if len(summary.warnings) > 20:
            click.echo(f"  ... and {len(summary.warnings) - 20} more warnings")

    if not summary.decoded_signals:
        click.echo("Decoded values:       (none)")
        return

    click.echo("")
    click.echo("Decoded signals")
    header = (
        f"{'Timestamp':>16}  {'PGN':>6}  {'SA':>4}  {'SPN':>5}  "
        f"{'Name':<20}  {'Raw':>8}  {'Value':>12}  Unit"
    )
    click.echo(header)
    for item in summary.decoded_signals:
        sa_text = f"0x{item.source_address:02X}"
        name = (item.spn_name or "-")[:20]
        value_text = f"{item.engineering_value:g}" if item.engineering_value is not None else "-"
        unit = item.unit or "-"
        click.echo(
            f"{item.timestamp_us:>16}  {item.pgn:>6}  {sa_text:>4}  {item.spn:>5}  "
            f"{name:<20}  {item.raw_value:>8}  {value_text:>12}  {unit}"
        )


@session_group.command("dbc")
@click.argument("session_id")
@click.option(
    "--asset",
    "asset_key",
    required=True,
    help="Target asset key (must be linked to the session).",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(),
    help="Output DBC path (default: <asset_key>_standard.dbc).",
)
@click.option("--pgn", type=int, default=None, help="Include only this PGN.")
@click.option(
    "--source-address",
    "source_addresses",
    multiple=True,
    type=lambda value: int(value, 0),
    help="Include only traffic from this J1939 source address (repeatable).",
)
def session_dbc(
    session_id: str,
    asset_key: str,
    output: str | None,
    pgn: int | None,
    source_addresses: tuple[int, ...],
) -> None:
    """Generate a reference-backed asset DBC from a capture session."""
    from pathlib import Path

    from canresearch.core.assets import default_dbc_filename
    from canresearch.core.dbc import build_session_dbc

    output_path = Path(output) if output else Path(default_dbc_filename(asset_key))
    sa_filter = source_addresses if source_addresses else None
    try:
        summary = build_session_dbc(
            session_id,
            output_path,
            asset_key=asset_key,
            pgn_filter=pgn,
            source_addresses=sa_filter,
        )
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    _print_session_dbc(summary, output_path)


@session_group.command("tp")
@click.argument("session_id")
@click.option("--pgn", type=int, default=None, help="Filter completed transported PGN.")
@click.option(
    "--source-address",
    "source_address",
    type=lambda value: int(value, 0),
    default=None,
    help="Filter by source address.",
)
@click.option(
    "--show-payload",
    is_flag=True,
    help="Print hex payload for completed transported messages.",
)
def session_tp(
    session_id: str,
    pgn: int | None,
    source_address: int | None,
    show_payload: bool,
) -> None:
    """Reassemble J1939 transport-protocol traffic from a capture session."""
    from canresearch.core.j1939_tp import reassemble_session_transport

    try:
        result = reassemble_session_transport(session_id)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Session:              {session_id}")
    click.echo(f"TP.CM frames:         {result.stats.tp_cm_frames}")
    click.echo(f"TP.DT frames:         {result.stats.tp_dt_frames}")
    click.echo(f"Transfers started:    {result.stats.transfers_started}")
    click.echo(f"Transfers completed:  {result.stats.transfers_completed}")
    click.echo(f"Transfers incomplete: {result.stats.transfers_incomplete}")
    click.echo(f"Transfers aborted:    {result.stats.transfers_aborted}")

    completed = result.completed_messages
    if pgn is not None:
        completed = [msg for msg in completed if msg.transported_pgn == pgn]
    if source_address is not None:
        completed = [msg for msg in completed if msg.source_address == source_address]

    if completed:
        click.echo("")
        click.echo("Completed transported PGNs:")
        for message in completed:
            da = message.destination_address
            da_text = f"{da:02X}" if da is not None else "FF"
            mode = message.transport_mode.value if message.transport_mode else "-"
            click.echo(
                f"  PGN {message.transported_pgn:<6}  SA {message.source_address:02X} "
                f"-> DA {da_text}  bytes {message.payload_length}  {mode}"
            )
            if show_payload:
                click.echo(f"    payload: {message.payload.hex()}")

    if result.warnings:
        warning_counts: dict[str, int] = {}
        for warning in result.warnings:
            warning_counts[warning.category] = warning_counts.get(warning.category, 0) + 1
        click.echo("")
        click.echo("Warnings:")
        for category, count in sorted(warning_counts.items()):
            click.echo(f"  {category}: {count}")


def _print_session_dbc(summary, output_path) -> None:
    click.echo(f"Session:                 {summary.session_id}")
    if summary.session_name:
        click.echo(f"Name:                    {summary.session_name}")
    click.echo(f"Asset:                   {summary.asset_key}")
    click.echo(f"DBC type:                {summary.dbc_type}")
    if summary.source_addresses:
        sa_text = ", ".join(f"0x{sa:02X}" for sa in summary.source_addresses)
        click.echo(f"Source addresses:        {sa_text}")
    if summary.provenance and summary.provenance.source_address_origin:
        click.echo(f"Source address origin:   {summary.provenance.source_address_origin}")
    if summary.provenance and summary.provenance.j1939_names:
        click.echo(f"J1939 NAMEs:             {', '.join(summary.provenance.j1939_names)}")
    click.echo(f"Frames examined:         {summary.frames_examined}")
    click.echo(f"Observed J1939 PGNs:     {summary.observed_j1939_pgns}")
    click.echo(f"Reference-backed PGNs:   {summary.reference_backed_pgns}")
    click.echo(f"DBC messages generated:  {summary.messages_generated}")
    click.echo(f"DBC signals generated:   {summary.signals_generated}")
    click.echo(f"Signals skipped:         {summary.signals_skipped}")

    if summary.warning_counts:
        click.echo("Warnings:")
        for category, count in sorted(summary.warning_counts.items()):
            click.echo(f"  {category}: {count}")

    if summary.messages_generated == 0:
        click.echo("No reference-backed messages were generated for this session.")
    click.echo(f"Written:                 {output_path}")


@session_group.command("summary")
@click.argument("session_id")
def session_summary(session_id: str) -> None:
    """Summarize a capture session."""
    from canresearch.core.sessions import summarize_session

    try:
        summary = summarize_session(session_id)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Session:     {summary['id']}")
    if summary.get("name"):
        click.echo(f"Name:        {summary['name']}")
    if summary.get("host"):
        click.echo(f"Host:        {summary['host']}")
    if summary.get("channel") is not None:
        click.echo(f"Channel:     {summary['channel']}")
    if summary.get("device_id"):
        click.echo(f"Device ID:   {summary['device_id']}")
    click.echo(f"Status:      {summary['status']}")
    click.echo(f"Started:     {summary['started_at']}")
    if summary.get("stopped_at"):
        click.echo(f"Stopped:     {summary['stopped_at']}")
    if summary.get("duration_s") is not None:
        click.echo(f"Duration:    {summary['duration_s']:.1f} s")
    click.echo(f"Frames:      {summary.get('frame_count', 0)}")
    if summary.get("frame_store_path"):
        click.echo(f"Store:       {summary['frame_store_path']}")
    if summary.get("notes"):
        click.echo(f"Notes:       {summary['notes']}")


@session_group.group("event")
def session_event_group() -> None:
    """Experiment event markers for capture sessions."""


@session_event_group.command("add")
@click.argument("session_id")
@click.option("--label", required=True, help="Event label (e.g. baseline_start, scv2_extend).")
@click.option("--notes", default=None, help="Optional annotation.")
def session_event_add(session_id: str, label: str, notes: str | None) -> None:
    """Add an experiment event marker to a session."""
    from canresearch.core.live_errors import LiveResearchError
    from canresearch.core.live_research import mark_experiment_event

    try:
        event = mark_experiment_event(session_id, label, notes=notes)
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Event:       {event['label']}")
    click.echo(f"Session:     {event['session_id']}")
    click.echo(f"Timestamp:   {event['timestamp']}")
    if event.get("notes"):
        click.echo(f"Notes:       {event['notes']}")


@session_event_group.command("list")
@click.argument("session_id")
def session_event_list(session_id: str) -> None:
    """List experiment event markers for a session."""
    from canresearch.core.live_errors import LiveResearchError
    from canresearch.core.live_research import list_experiment_events

    try:
        events = list_experiment_events(session_id)
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc

    if not events:
        click.echo("No experiment events.")
        return
    click.echo(f"Experiment events for session {session_id}")
    for event in events:
        notes = f"  ({event['notes']})" if event.get("notes") else ""
        click.echo(f"  {event['timestamp']}  {event['label']}{notes}")


@session_group.command("compare")
@click.argument("session_id")
@click.option("--baseline-event", required=True, help="Baseline event label.")
@click.option("--action-event", required=True, help="Action event label.")
@click.option(
    "--window-seconds",
    default=3.0,
    show_default=True,
    help="Comparison window length after each marker.",
)
def session_compare(
    session_id: str,
    baseline_event: str,
    action_event: str,
    window_seconds: float,
) -> None:
    """Compare baseline and action experiment windows in a session."""
    from canresearch.core.live_errors import LiveResearchError
    from canresearch.core.live_research import compare_experiment_windows

    try:
        result = compare_experiment_windows(
            session_id,
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window_seconds,
        )
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc

    click.echo(f"Session:     {result['session_id']}")
    baseline = result["baseline"]
    action = result["action"]
    click.echo(
        f"Baseline:    {baseline['event']}  {baseline['start']} → {baseline['end']}  "
        f"({baseline['frames']} frames)"
    )
    click.echo(
        f"Action:      {action['event']}  {action['start']} → {action['end']}  "
        f"({action['frames']} frames)"
    )
    if result.get("baseline_only_can_ids"):
        click.echo("Baseline-only CAN IDs:")
        for cid in result["baseline_only_can_ids"]:
            click.echo(f"  {cid}")
    if result.get("action_only_can_ids"):
        click.echo("Action-only CAN IDs:")
        for cid in result["action_only_can_ids"]:
            click.echo(f"  {cid}")
    click.echo("Top changes:")
    for item in result.get("top_changes", []):
        changed = item.get("changed_byte_indices") or []
        changed_text = ",".join(str(i) for i in changed) if changed else "-"
        click.echo(
            f"  {item['can_id']}  score={item['change_score']:.3f}  "
            f"baseline={item['baseline_count']} action={item['action_count']}  "
            f"bytes=[{changed_text}]"
        )


@session_group.group("research")
def session_research_group() -> None:
    """Proprietary signal research (candidate evidence only)."""


def _parse_can_id(value: str) -> int:
    cleaned = value.strip().lower()
    if cleaned.startswith("0x"):
        return int(cleaned, 16)
    return int(cleaned)


@session_research_group.command("rank")
@click.argument("session_id")
@click.option("--baseline-event", required=True)
@click.option("--action-event", required=True)
@click.option("--window-seconds", default=3.0, show_default=True)
@click.option("--limit", default=20, show_default=True)
def session_research_rank(
    session_id: str,
    baseline_event: str,
    action_event: str,
    window_seconds: float,
    limit: int,
) -> None:
    """Rank CAN ID candidates between baseline and action windows."""
    from canresearch.core.live_errors import LiveResearchError
    from canresearch.core.signal_research import rank_candidate_ids

    try:
        result = rank_candidate_ids(
            session_id,
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window_seconds,
            limit=limit,
        )
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc

    for item in result.get("candidates", []):
        evidence = item.get("evidence", {})
        click.echo(
            f"#{item.get('rank')} {item['can_id']} score={item.get('change_score')} "
            f"bytes={evidence.get('changed_bytes')}"
        )


@session_research_group.command("id")
@click.argument("session_id")
@click.argument("can_id")
@click.option("--baseline-event")
@click.option("--action-event")
@click.option("--window-seconds", default=3.0, show_default=True)
def session_research_id(
    session_id: str,
    can_id: str,
    baseline_event: str | None,
    action_event: str | None,
    window_seconds: float,
) -> None:
    """Analyze byte/bit activity for one CAN ID."""
    from canresearch.core.live_errors import LiveResearchError
    from canresearch.core.signal_research import analyze_can_id_activity

    try:
        result = analyze_can_id_activity(
            session_id,
            _parse_can_id(can_id),
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window_seconds,
        )
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"CAN ID: {result['can_id']}  frames action={result['action']['frame_count']}")
    for row in result["action"]["byte_activity"]:
        click.echo(
            f"  byte {row['byte']}: unique={row['unique_values']} "
            f"change_rate={row['change_rate']}"
        )
    click.echo(f"Field candidates: {len(result.get('field_candidates', []))}")


@session_research_group.command("counters")
@click.argument("session_id")
@click.argument("can_id")
def session_research_counters(session_id: str, can_id: str) -> None:
    """Detect counter candidates for one CAN ID."""
    from canresearch.core.signal_research import detect_counters_for_can_id

    try:
        result = detect_counters_for_can_id(session_id, _parse_can_id(can_id))
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    for item in result.get("candidates", []):
        click.echo(
            f"byte {item['byte_index']} {item['field_type']} "
            f"match={item['match_ratio']} modulus={item['modulus']}"
        )


@session_research_group.command("checksums")
@click.argument("session_id")
@click.argument("can_id")
def session_research_checksums(session_id: str, can_id: str) -> None:
    """Detect checksum candidates for one CAN ID."""
    from canresearch.core.signal_research import detect_checksums_for_can_id

    try:
        result = detect_checksums_for_can_id(session_id, _parse_can_id(can_id))
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    for item in result.get("candidates", []):
        click.echo(
            f"{item['algorithm']} byte={item['checksum_byte']} match={item['match_ratio']}"
        )


@session_research_group.command("repeat")
@click.argument("session_id")
@click.option("--baseline-events", required=True, help="Comma-separated baseline labels.")
@click.option("--action-events", required=True, help="Comma-separated action labels.")
@click.option("--window-seconds", default=3.0, show_default=True)
@click.option("--can-id", default=None)
def session_research_repeat(
    session_id: str,
    baseline_events: str,
    action_events: str,
    window_seconds: float,
    can_id: str | None,
) -> None:
    """Compare repeated baseline/action pairs for consistency."""
    from canresearch.core.live_errors import LiveResearchError
    from canresearch.core.signal_research import compare_repeated_actions

    base_labels = [part.strip() for part in baseline_events.split(",") if part.strip()]
    act_labels = [part.strip() for part in action_events.split(",") if part.strip()]
    kwargs: dict = {
        "session_id": session_id,
        "baseline_events": base_labels,
        "action_events": act_labels,
        "window_seconds": window_seconds,
    }
    if can_id is not None:
        kwargs["can_id"] = _parse_can_id(can_id)
    try:
        result = compare_repeated_actions(**kwargs)
    except LiveResearchError as exc:
        raise SystemExit(f"{exc.code}: {exc.message}") from exc

    for row in result.get("bit_consistency", [])[:20]:
        click.echo(
            f"{row['can_id']} bit {row['bit_index']} consistency={row['consistency']} "
            f"specificity={row['action_specificity_score']}"
        )


@session_group.group("asset")
def session_asset_group() -> None:
    """Manage assets linked to a capture session."""


@session_asset_group.command("add")
@click.argument("session_id")
@click.argument("asset_key")
@click.option(
    "--role",
    required=True,
    type=click.Choice(["tractor", "implement", "controller", "other"]),
    help="Asset role within this session.",
)
def session_asset_add(session_id: str, asset_key: str, role: str) -> None:
    """Link an asset to a capture session."""
    from canresearch.core.assets import link_session_asset

    try:
        record = link_session_asset(session_id, asset_key, role=role)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Linked {record.asset_key} to session {session_id} as {record.role}")


@session_asset_group.command("list")
@click.argument("session_id")
def session_asset_list(session_id: str) -> None:
    """List assets linked to a capture session."""
    from canresearch.core.assets import list_session_assets

    try:
        records = list_session_assets(session_id)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    if not records:
        click.echo(f"No assets linked to session {session_id}.")
        return

    click.echo(f"Assets for session {session_id}")
    for record in records:
        click.echo(
            f"{record.asset_key:<24}  {record.role:<11}  {record.display_name}"
        )


@session_asset_group.command("remove")
@click.argument("session_id")
@click.argument("asset_key")
def session_asset_remove(session_id: str, asset_key: str) -> None:
    """Remove an asset link from a capture session."""
    from canresearch.core.assets import unlink_session_asset

    try:
        unlink_session_asset(session_id, asset_key)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Removed {asset_key} from session {session_id}")


@main.group("asset")
def asset_group() -> None:
    """Manage physical assets (tractor, implement, controller, etc.)."""


@asset_group.command("add")
@click.option("--key", "asset_key", required=True, help="Stable asset key (lowercase).")
@click.option(
    "--type",
    "asset_type",
    required=True,
    type=click.Choice(["tractor", "implement", "controller", "other"]),
    help="Asset type.",
)
@click.option("--name", "display_name", required=True, help="Human-friendly display name.")
@click.option("--manufacturer", default=None, help="Manufacturer name.")
@click.option("--model", default=None, help="Model name or number.")
@click.option("--serial", "serial_number", default=None, help="Serial number.")
@click.option("--notes", default=None, help="Free-form notes.")
def asset_add(
    asset_key: str,
    asset_type: str,
    display_name: str,
    manufacturer: str | None,
    model: str | None,
    serial_number: str | None,
    notes: str | None,
) -> None:
    """Register a new asset."""
    from canresearch.core.assets import add_asset

    try:
        record = add_asset(
            asset_key=asset_key,
            asset_type=asset_type,
            display_name=display_name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            notes=notes,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Asset:       {record.asset_key}")
    click.echo(f"Type:        {record.asset_type}")
    click.echo(f"Name:        {record.display_name}")
    if record.manufacturer:
        click.echo(f"Manufacturer:{record.manufacturer}")
    if record.model:
        click.echo(f"Model:       {record.model}")
    if record.serial_number:
        click.echo(f"Serial:      {record.serial_number}")


@asset_group.command("list")
@click.option("--limit", default=100, show_default=True, help="Maximum assets to show.")
def asset_list(limit: int) -> None:
    """List registered assets."""
    from canresearch.core.assets import list_assets

    records = list_assets(limit=limit)
    if not records:
        click.echo("No assets registered.")
        return

    click.echo("Assets")
    for record in records:
        click.echo(
            f"{record.asset_key:<24}  {record.asset_type:<11}  {record.display_name}"
        )


@asset_group.command("show")
@click.argument("asset_key")
def asset_show(asset_key: str) -> None:
    """Show details for one asset."""
    from canresearch.core.assets import get_asset_by_key

    try:
        record = get_asset_by_key(asset_key)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    click.echo(f"Key:         {record.asset_key}")
    click.echo(f"Type:        {record.asset_type}")
    click.echo(f"Name:        {record.display_name}")
    if record.manufacturer:
        click.echo(f"Manufacturer:{record.manufacturer}")
    if record.model:
        click.echo(f"Model:       {record.model}")
    if record.serial_number:
        click.echo(f"Serial:      {record.serial_number}")
    if record.notes:
        click.echo(f"Notes:       {record.notes}")
    click.echo(f"Created:     {record.created_at.isoformat()}")
    click.echo(f"Updated:     {record.updated_at.isoformat()}")


@asset_group.group("node")
def asset_node_group() -> None:
    """Link observed J1939 NAME identities to assets."""


@asset_node_group.command("add")
@click.argument("asset_key")
@click.argument("j1939_name")
def asset_node_add(asset_key: str, j1939_name: str) -> None:
    """Link a J1939 NAME to an asset."""
    from canresearch.core.j1939_nodes import link_asset_node

    try:
        link_asset_node(asset_key, j1939_name, require_observed=True)
    except (KeyError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    click.echo(f"Linked {j1939_name} to asset {asset_key}")


@asset_node_group.command("list")
@click.argument("asset_key")
def asset_node_list(asset_key: str) -> None:
    """List J1939 NAMEs linked to an asset."""
    from canresearch.core.j1939_nodes import list_asset_nodes

    try:
        nodes = list_asset_nodes(asset_key)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    if not nodes:
        click.echo(f"No J1939 nodes linked to asset {asset_key}.")
        return

    click.echo(f"J1939 nodes for asset {asset_key}")
    for node in nodes:
        click.echo(
            f"{node.name.name_hex:<22}  "
            f"mfg={node.name.manufacturer_code:<4}  fn={node.name.function}"
        )


@asset_node_group.command("remove")
@click.argument("asset_key")
@click.argument("j1939_name")
def asset_node_remove(asset_key: str, j1939_name: str) -> None:
    """Remove a J1939 NAME link from an asset."""
    from canresearch.core.j1939_nodes import unlink_asset_node

    try:
        unlink_asset_node(asset_key, j1939_name)
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    click.echo(f"Removed {j1939_name} from asset {asset_key}")


@session_group.command("nodes")
@click.argument("session_id")
@click.option(
    "--refresh",
    is_flag=True,
    help="Rescan frames and refresh persisted node observations.",
)
@click.option(
    "--source-address",
    "source_address",
    type=lambda value: int(value, 0),
    default=None,
    help="Filter by claimed source address.",
)
@click.option(
    "--manufacturer-code",
    type=int,
    default=None,
    help="Filter by manufacturer code.",
)
@click.option("--show-raw", is_flag=True, help="Show full NAME field breakdown.")
def session_nodes(
    session_id: str,
    refresh: bool,
    source_address: int | None,
    manufacturer_code: int | None,
    show_raw: bool,
) -> None:
    """List J1939 Address Claim node identities observed in a session."""
    from canresearch.core.j1939_nodes import list_session_nodes, scan_session_j1939_nodes

    try:
        if refresh:
            result = scan_session_j1939_nodes(session_id, persist=True)
            nodes = list(result.nodes)
            warnings = result.warnings
            stats = result.stats
        else:
            nodes = list_session_nodes(session_id)
            if not nodes:
                result = scan_session_j1939_nodes(session_id, persist=True)
                nodes = list(result.nodes)
                warnings = result.warnings
                stats = result.stats
            else:
                warnings = ()
                stats = None
    except (KeyError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc

    if source_address is not None:
        nodes = [
            node
            for node in nodes
            if any(obs.source_address == source_address for obs in node.observations)
        ]
    if manufacturer_code is not None:
        nodes = [node for node in nodes if node.name.manufacturer_code == manufacturer_code]

    click.echo(f"Session: {session_id}")
    click.echo(f"Observed J1939 nodes: {len(nodes)}")
    if stats is not None:
        click.echo(f"Address claims:      {stats.address_claim_frames}")
        if stats.address_conflicts:
            click.echo(f"Address conflicts:   {stats.address_conflicts}")

    if not nodes:
        click.echo("No Address Claim nodes observed.")
        return

    click.echo("")
    click.echo(f"{'NAME':<20}  {'SA':<4}  {'Mfg':<5}  {'Fn':<4}  {'IG':<3}  {'AAC':<3}")
    for node in nodes:
        sa_text = "--"
        if node.latest_source_address is not None:
            sa_text = f"{node.latest_source_address:02X}"
        elif node.cannot_claim:
            sa_text = "FE"
        aac = "yes" if node.name.arbitrary_address_capable else "no"
        click.echo(
            f"{node.name.name_hex:<20}  {sa_text:<4}  "
            f"{node.name.manufacturer_code:<5}  {node.name.function:<4}  "
            f"{node.name.industry_group:<3}  {aac:<3}"
        )
        if show_raw:
            for line in node.name.format_summary():
                click.echo(f"  {line}")

    if warnings:
        click.echo("")
        click.echo("Warnings:")
        for warning in warnings:
            click.echo(f"  {warning.category}: {warning.message}")


@main.group("research")
def research_group() -> None:
    """Research candidate review and asset research DBC generation."""


@research_group.group("candidate")
def research_candidate_group() -> None:
    """Manage persisted research signal candidates."""


def _print_candidate(candidate: object) -> None:
    from canresearch.core.research_candidates import ResearchCandidateRecord, candidate_to_dict

    assert isinstance(candidate, ResearchCandidateRecord)
    data = candidate_to_dict(candidate)
    click.echo(f"ID: {data['id']}")
    click.echo(f"Asset: {data['asset_key']}")
    click.echo(f"Status: {data['status']}")
    click.echo(f"CAN ID: {data['can_id_hex']}")
    click.echo(f"Field: start={data['start_bit']} len={data['bit_length']} {data['byte_order']}")
    click.echo(f"Signedness: {data['signedness']}  Classification: {data['classification']}")
    if data["signal_name"]:
        click.echo(f"Signal name: {data['signal_name']}")
    if data["factor"] is not None:
        unit = data["unit"] or ""
        click.echo(
            f"Scale: factor={data['factor']} offset={data['offset']} unit={unit}"
        )
    if data["origin_session_id"]:
        click.echo(f"Origin session: {data['origin_session_id']}")
    if data["notes"]:
        click.echo(f"Notes: {data['notes']}")


@research_candidate_group.command("add")
@click.option("--asset", "asset_key", required=True)
@click.option("--session", "session_id", required=True)
@click.option("--can-id", required=True)
@click.option("--start-bit", required=True, type=int)
@click.option("--length", "bit_length", required=True, type=int)
@click.option(
    "--byte-order",
    type=click.Choice(["intel", "motorola"], case_sensitive=False),
    required=True,
)
@click.option("--signed/--unsigned", default=None)
@click.option("--name", "suggested_name", default=None)
@click.option("--factor", type=float, default=None)
@click.option("--offset", type=float, default=None)
@click.option("--unit", default=None)
@click.option("--notes", default=None)
@click.option(
    "--classification",
    type=click.Choice(["signal", "counter", "checksum", "reserved", "unknown"]),
    default="unknown",
    show_default=True,
)
def research_candidate_add(
    asset_key: str,
    session_id: str,
    can_id: str,
    start_bit: int,
    bit_length: int,
    byte_order: str,
    signed: bool | None,
    suggested_name: str | None,
    factor: float | None,
    offset: float | None,
    unit: str | None,
    notes: str | None,
    classification: str,
) -> None:
    """Create a persisted research candidate (does not confirm or write DBC)."""
    from canresearch.core.research_candidates import (
        ResearchCandidateError,
        Signedness,
        create_research_candidate,
    )

    signedness = (
        Signedness.SIGNED.value
        if signed is True
        else Signedness.UNSIGNED.value
        if signed is False
        else Signedness.UNKNOWN.value
    )
    try:
        candidate = create_research_candidate(
            asset_key=asset_key,
            session_id=session_id,
            can_id=_parse_can_id(can_id),
            start_bit=start_bit,
            bit_length=bit_length,
            byte_order=byte_order,
            signedness=signedness,
            classification=classification,
            suggested_name=suggested_name,
            factor=factor,
            offset=offset,
            unit=unit,
            notes=notes,
        )
    except (ResearchCandidateError, ValueError) as exc:
        if isinstance(exc, ResearchCandidateError):
            click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        else:
            click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
    click.echo("Research candidate created:")
    _print_candidate(candidate)


@research_candidate_group.command("list")
@click.option("--asset", "asset_key", default=None)
@click.option("--status", default=None)
@click.option("--session", "session_id", default=None)
@click.option("--limit", default=50, show_default=True)
def research_candidate_list(
    asset_key: str | None,
    status: str | None,
    session_id: str | None,
    limit: int,
) -> None:
    """List research candidates."""
    from canresearch.core.research_candidates import (
        ResearchCandidateError,
        list_research_candidates,
    )

    try:
        rows = list_research_candidates(
            asset_key=asset_key,
            status=status,
            session_id=session_id,
            limit=limit,
        )
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        raise SystemExit(1) from exc
    if not rows:
        click.echo("No research candidates.")
        return
    for row in rows:
        name = row.signal_name or row.suggested_name or "-"
        click.echo(
            f"{row.id}  {row.status:9}  {row.asset_key}  0x{row.can_id:X}  "
            f"{row.start_bit}|{row.bit_length}  {name}"
        )


@research_candidate_group.command("show")
@click.argument("candidate_id")
def research_candidate_show(candidate_id: str) -> None:
    """Show one research candidate."""
    from canresearch.core.research_candidates import ResearchCandidateError, get_research_candidate

    try:
        candidate = get_research_candidate(candidate_id)
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        raise SystemExit(1) from exc
    _print_candidate(candidate)


@research_candidate_group.command("review")
@click.argument("candidate_id")
@click.option("--notes", default=None)
def research_candidate_review(candidate_id: str, notes: str | None) -> None:
    """Mark a candidate as reviewed."""
    from canresearch.core.research_candidates import ResearchCandidateError, mark_candidate_reviewed

    try:
        result = mark_candidate_reviewed(candidate_id, notes=notes)
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        raise SystemExit(1) from exc
    click.echo(
        f"Candidate {candidate_id} marked reviewed "
        f"({result.from_status} → {result.to_status})"
    )


@research_candidate_group.command("confirm")
@click.argument("candidate_id")
@click.option("--name", required=True)
@click.option("--factor", required=True, type=float)
@click.option("--offset", required=True, type=float)
@click.option("--unit", default="")
@click.option("--signed/--unsigned", required=True)
@click.option("--minimum", type=float, default=None)
@click.option("--maximum", type=float, default=None)
@click.option("--notes", default=None)
@click.option(
    "--classification",
    type=click.Choice(["signal", "counter", "checksum", "reserved", "unknown"]),
    default=None,
)
def research_candidate_confirm(
    candidate_id: str,
    name: str,
    factor: float,
    offset: float,
    unit: str,
    signed: bool,
    minimum: float | None,
    maximum: float | None,
    notes: str | None,
    classification: str | None,
) -> None:
    """Confirm a reviewed candidate (does not write DBC automatically)."""
    from canresearch.core.research_candidates import (
        ResearchCandidateError,
        Signedness,
        confirm_candidate,
    )

    try:
        result = confirm_candidate(
            candidate_id,
            name=name,
            factor=factor,
            offset=offset,
            signedness=Signedness.SIGNED.value if signed else Signedness.UNSIGNED.value,
            unit=unit,
            minimum=minimum,
            maximum=maximum,
            classification=classification,
            notes=notes,
        )
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        if exc.details:
            click.echo(f"Details: {exc.details}", err=True)
        raise SystemExit(1) from exc
    click.echo(f"Candidate confirmed as {result.dbc_signal_name}")
    if result.name_sanitized:
        click.echo(f"  requested_name: {result.requested_name}")
        click.echo(f"  dbc_signal_name: {result.dbc_signal_name}")


@research_candidate_group.command("reject")
@click.argument("candidate_id")
@click.option("--notes", default=None)
def research_candidate_reject(candidate_id: str, notes: str | None) -> None:
    """Reject a candidate."""
    from canresearch.core.research_candidates import ResearchCandidateError, reject_candidate

    try:
        result = reject_candidate(candidate_id, notes=notes)
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        raise SystemExit(1) from exc
    click.echo(f"Candidate rejected ({result.from_status} → {result.to_status})")


@research_candidate_group.command("evidence")
@click.argument("candidate_id")
@click.option("--limit", default=50, show_default=True)
def research_candidate_evidence(candidate_id: str, limit: int) -> None:
    """List evidence attached to a candidate."""
    from canresearch.core.research_candidates import ResearchCandidateError, list_candidate_evidence

    try:
        rows = list_candidate_evidence(candidate_id, limit=limit)
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        raise SystemExit(1) from exc
    if not rows:
        click.echo("No evidence rows.")
        return
    for row in rows:
        click.echo(f"[{row.id}] {row.evidence_type} @ {row.created_at.isoformat()}")
        click.echo(f"  {row.evidence}")


@research_candidate_group.command("note")
@click.argument("candidate_id")
@click.option("--text", required=True)
def research_candidate_note(candidate_id: str, text: str) -> None:
    """Append a manual note as candidate evidence."""
    from canresearch.core.research_candidates import ResearchCandidateError, add_candidate_evidence

    try:
        row = add_candidate_evidence(
            candidate_id,
            evidence_type="manual_note",
            evidence={"text": text},
        )
    except ResearchCandidateError as exc:
        click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        raise SystemExit(1) from exc
    click.echo(f"Evidence added (id={row.id})")


@research_group.command("dbc")
@click.argument("asset_key")
@click.option("--output", "-o", default=None, help="Output DBC path.")
@click.option(
    "--include-protocol-fields",
    is_flag=True,
    default=False,
    help="Include confirmed counter/checksum/reserved fields.",
)
def research_dbc(asset_key: str, output: str | None, include_protocol_fields: bool) -> None:
    """Generate asset research DBC from confirmed candidates only."""
    from pathlib import Path

    from canresearch.core.research_dbc import write_asset_research_dbc

    try:
        summary = write_asset_research_dbc(
            asset_key,
            output=Path(output) if output else None,
            include_protocol_fields=include_protocol_fields,
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
    click.echo(f"Asset: {summary.asset_key}")
    click.echo(f"Confirmed signals: {summary.confirmed_signal_count}")
    click.echo(f"Messages: {summary.messages_generated}")
    click.echo(f"Signals: {summary.signals_generated}")
    click.echo(f"Skipped: {summary.signals_skipped}")
    if summary.warnings:
        click.echo("Warnings:")
        for warning in summary.warnings:
            click.echo(f"  {warning.category}: {warning.message}")
    click.echo(f"Written: {summary.output_path}")


@main.group("dbc")
def dbc_group() -> None:
    """Build and manage machine-specific DBC files."""


@dbc_group.command("build")
@click.option("--session", "session_id", default=None, help="Source session ID.")
@click.option("--machine", default=None, help="Target machine profile name.")
@click.option("--output", "-o", default=None, help="Output DBC path.")
def dbc_build(session_id: str | None, machine: str | None, output: str | None) -> None:
    """Build a base tractor DBC from a capture session."""
    click.echo("DBC build is not yet implemented.")
    if session_id:
        click.echo(f"  session: {session_id}")
    if machine:
        click.echo(f"  machine: {machine}")
    if output:
        click.echo(f"  output: {output}")


@main.group("reference")
def reference_group() -> None:
    """Import and manage local PGN/SPN reference data."""


@reference_group.command("import-dbc")
@click.argument("dbc_path", type=click.Path(exists=False))
def reference_import_dbc(dbc_path: str) -> None:
    """Import PGN/message definitions from a user-provided DBC file."""
    click.echo("Reference import-dbc is not yet implemented.")
    click.echo(f"  dbc_path: {dbc_path}")
    click.echo("Note: only import DBCs you are licensed to use.")


@reference_group.command("import-j1939")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_import_j1939(pdf_path: str, db_path: str | None) -> None:
    """Import J1939-71 PDF into the local reference catalogue."""
    from pathlib import Path

    from canresearch.references.importers.j1939_pdf_importer import J1939PdfImporter
    from canresearch.storage.database import default_db_path, initialize

    path = Path(pdf_path)
    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    importer = J1939PdfImporter()
    report = importer.import_file(path, conn)
    conn.close()

    click.echo(f"source: {path.name}")
    click.echo(f"SPNs parsed: {report.spns_parsed}")
    click.echo(f"PGNs parsed: {report.pgns_parsed}")
    click.echo(f"PGN/SPN mappings: {report.mappings_parsed}")
    click.echo(f"inserted: {report.inserted}")
    click.echo(f"updated: {report.updated}")
    click.echo(f"unchanged: {report.unchanged}")
    click.echo(f"warnings: {len(report.warnings)}")
    click.echo(f"errors: {report.failed}")
    for warning in report.warnings[:20]:
        click.echo(f"  warning: {warning}")
    if len(report.warnings) > 20:
        click.echo(f"  ... and {len(report.warnings) - 20} more warnings")


@reference_group.command("import-isobus-pdf")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_import_isobus_pdf(pdf_path: str, db_path: str | None) -> None:
    """Import ISOBUS DDI PDF snapshot into the local reference catalogue."""
    from pathlib import Path

    from canresearch.references.importers.isobus_pdf_importer import IsobusPdfImporter
    from canresearch.storage.database import default_db_path, initialize

    path = Path(pdf_path)
    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    importer = IsobusPdfImporter()
    report = importer.import_file(path, conn)
    conn.close()

    click.echo(f"source: {path.name}")
    click.echo(f"DDIs parsed: {report.ddis_parsed}")
    click.echo(f"inserted: {report.inserted}")
    click.echo(f"updated: {report.updated}")
    click.echo(f"unchanged: {report.unchanged}")
    click.echo(f"warnings: {len(report.warnings)}")
    click.echo(f"errors: {report.failed}")


@reference_group.command("validate")
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_validate(db_path: str | None) -> None:
    """Validate the local reference catalogue."""
    from pathlib import Path

    from canresearch.references.validation import validate_reference_catalogue
    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    report = validate_reference_catalogue(conn)
    conn.close()

    click.echo(f"errors: {len(report.errors)}")
    click.echo(f"warnings: {len(report.warnings)}")
    click.echo(f"info: {len(report.infos)}")
    for issue in report.issues[:50]:
        click.echo(f"  [{issue.severity}] {issue.category}: {issue.message}")
    if len(report.issues) > 50:
        click.echo(f"  ... and {len(report.issues) - 50} more issues")


@reference_group.command("stats")
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_stats(db_path: str | None) -> None:
    """Show reference catalogue statistics."""
    from pathlib import Path

    from canresearch.references.service import ReferenceService
    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    stats = ReferenceService(conn).stats()
    conn.close()
    for key, value in stats.items():
        click.echo(f"{key}: {value}")


@reference_group.command("pgn")
@click.argument("number", type=int)
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_pgn(number: int, db_path: str | None) -> None:
    """Look up a PGN by number."""
    from pathlib import Path

    from canresearch.references.service import ReferenceService
    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    service = ReferenceService(conn)
    rows = service.lookup_pgn(number)
    if not rows:
        click.echo(f"PGN {number} not found.")
        conn.close()
        return

    row = rows[0]
    click.echo(f"PGN: {row['pgn']}")
    click.echo(f"Name: {row['name']}")
    if row["acronym"]:
        click.echo(f"Acronym: {row['acronym']}")
    click.echo(f"Origin: {row['origin']}")
    click.echo(f"Source: {row['source_title']}")
    if row["coverage_date"]:
        click.echo(f"Coverage: through {row['coverage_date']}")
    if row["transmission_rate"]:
        click.echo(f"Transmission rate: {row['transmission_rate']}")
    if row["payload_length"] is not None:
        click.echo(f"Payload length: {row['payload_length']} bytes")
    mappings = service.pgn_spn_mappings(number, source_id=row["source_id"])
    if mappings:
        click.echo("SPNs:")
        for mapping in mappings:
            pos = mapping["raw_position_text"] or ""
            name = mapping["spn_name"] or ""
            click.echo(f"  {mapping['spn']:>5}  {pos:<12}  {name}")
    conn.close()


@reference_group.command("spn")
@click.argument("number", type=int)
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_spn(number: int, db_path: str | None) -> None:
    """Look up an SPN by number."""
    from pathlib import Path

    from canresearch.references.service import ReferenceService
    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    rows = ReferenceService(conn).lookup_spn(number)
    conn.close()
    if not rows:
        click.echo(f"SPN {number} not found.")
        return

    row = rows[0]
    click.echo(f"SPN: {row['spn']}")
    click.echo(f"Name: {row['name']}")
    click.echo(f"Origin: {row['origin']}")
    click.echo(f"Source: {row['source_title']}")
    if row["coverage_date"]:
        click.echo(f"Coverage: through {row['coverage_date']}")
    if row["definition"]:
        click.echo(f"Definition: {row['definition'][:200]}")
    if row["resolution"]:
        click.echo(f"Resolution: {row['resolution']}")
    if row["unit"]:
        click.echo(f"Unit: {row['unit']}")
    if row["data_length_bits"] is not None:
        click.echo(f"Data length: {row['data_length_bits']} bits")


@reference_group.command("ddi")
@click.argument("number", type=int)
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_ddi(number: int, db_path: str | None) -> None:
    """Look up an ISOBUS DDI by number."""
    from pathlib import Path

    from canresearch.references.service import ReferenceService
    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    rows = ReferenceService(conn).lookup_ddi(number)
    conn.close()
    if not rows:
        click.echo(f"DDI {number} not found.")
        return

    row = rows[0]
    click.echo(f"DDI: {row['ddi']}")
    click.echo(f"Name: {row['name']}")
    click.echo(f"Origin: {row['origin']}")
    click.echo(f"Source: {row['source_title']}")
    if row["definition"]:
        click.echo(f"Definition: {row['definition'][:200]}")
    if row["unit_symbol"]:
        click.echo(f"Unit: {row['unit_symbol']}")


@reference_group.group("source")
def reference_source_group() -> None:
    """List imported reference sources."""


@reference_source_group.command("list")
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_source_list(db_path: str | None) -> None:
    """List imported reference sources."""
    from pathlib import Path

    from canresearch.references.service import ReferenceService
    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    sources = ReferenceService(conn).list_sources()
    conn.close()
    if not sources:
        click.echo("No reference sources imported.")
        return
    for source in sources:
        click.echo(
            f"{source['id']:>3}  {source['source_key']:<24}  "
            f"{source['origin']:<18}  {source['title']}"
        )


@reference_group.command("warnings")
@click.option(
    "--db",
    "db_path",
    type=click.Path(),
    default=None,
    help="Reference database path (default: data/references/canresearch.db).",
)
def reference_warnings(db_path: str | None) -> None:
    """Show stored import/validation warnings."""
    from pathlib import Path

    from canresearch.storage.database import default_db_path, initialize

    db = Path(db_path) if db_path else default_db_path()
    conn = initialize(db)
    try:
        rows = conn.execute(
            """
            SELECT severity, category, message
            FROM reference_import_warnings
            ORDER BY id DESC LIMIT 100
            """
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    if not rows:
        click.echo("No stored warnings.")
        return
    for row in rows:
        click.echo(f"[{row['severity']}] {row['category']}: {row['message']}")


@main.group("mcp")
def mcp_group() -> None:
    """Run the MCP server for AI client integration."""


@mcp_group.command("tools")
def mcp_tools() -> None:
    """List MCP tools registered by the server."""
    from canresearch.mcp.server import (
        LIVE_TOOL_NAMES,
        READ_ONLY_TOOL_NAMES,
        SIGNAL_RESEARCH_TOOL_NAMES,
        list_tool_names,
    )

    click.echo("Read-only session/research tools:")
    for name in sorted(READ_ONLY_TOOL_NAMES):
        click.echo(f"  {name}")
    click.echo("Live CANsub research tools (passive):")
    for name in sorted(LIVE_TOOL_NAMES):
        click.echo(f"  {name}")
    click.echo("Signal research tools (candidate evidence):")
    for name in sorted(SIGNAL_RESEARCH_TOOL_NAMES):
        click.echo(f"  {name}")
    click.echo("")
    click.echo(
        "Candidate confirmation/rejection is CLI-only (human approval boundary)."
    )
    click.echo(f"Total: {len(list_tool_names())}")


@mcp_group.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind address for MCP server.")
@click.option("--port", default=8765, type=int, help="Bind port for MCP server.")
def mcp_serve(host: str, port: int) -> None:
    """Start the MCP server (stdio transport)."""
    from canresearch.mcp.server import serve

    click.echo(f"Starting MCP server on {host}:{port} (stdio transport) ...")
    serve(host=host, port=port)
