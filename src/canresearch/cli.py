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
def capture_stop() -> None:
    """Stop the active capture session."""
    click.echo("Capture stop is not yet implemented.")


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


@mcp_group.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind address for MCP server.")
@click.option("--port", default=8765, type=int, help="Bind port for MCP server.")
def mcp_serve(host: str, port: int) -> None:
    """Start the MCP server (stdio transport)."""
    from canresearch.mcp.server import serve

    click.echo(f"Starting MCP server on {host}:{port} (stdio transport) ...")
    serve(host=host, port=port)
