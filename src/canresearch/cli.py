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
def device_list() -> None:
    """List connected CANsub.2 devices (USB or Ethernet)."""
    click.echo("CANsub.2 device discovery is not yet implemented.")
    click.echo("Planned: scan USB and Ethernet for CSS Electronics CANsub.2 adapters.")


@main.group("capture")
def capture_group() -> None:
    """Start and stop live CAN capture sessions."""


@capture_group.command("start")
@click.option("--device", default=None, help="Device identifier from 'device list'.")
@click.option("--name", default=None, help="Optional session label.")
def capture_start(device: str | None, name: str | None) -> None:
    """Start a new capture session."""
    click.echo("Capture start is not yet implemented.")
    if device:
        click.echo(f"  device: {device}")
    if name:
        click.echo(f"  name: {name}")


@capture_group.command("stop")
def capture_stop() -> None:
    """Stop the active capture session."""
    click.echo("Capture stop is not yet implemented.")


@main.group("session")
def session_group() -> None:
    """Inspect recorded capture sessions."""


@session_group.command("list")
def session_list() -> None:
    """List stored capture sessions."""
    click.echo("Session list is not yet implemented.")
    click.echo("Planned: read session metadata from SQLite.")


@session_group.command("summary")
@click.argument("session_id", required=False, default=None)
def session_summary(session_id: str | None) -> None:
    """Summarize a capture session (observed PGNs, rates, etc.)."""
    click.echo("Session summary is not yet implemented.")
    if session_id:
        click.echo(f"  session_id: {session_id}")


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
