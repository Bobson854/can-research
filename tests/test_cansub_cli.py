"""CLI tests for CANsub device commands."""

from __future__ import annotations

from click.testing import CliRunner

from canresearch.cansub.client import CansubDeviceInfo
from canresearch.cli import main


def test_device_list_without_host_shows_discovery_stub() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["device", "list"])
    assert result.exit_code == 0
    assert "discovery is not yet implemented" in result.output
    assert "--host" in result.output or "Tip:" in result.output


def test_device_list_with_host(monkeypatch) -> None:
    def fake_probe(host: str, *, timeout: float = 5.0, verify_tls: bool = False):
        _ = timeout, verify_tls
        return CansubDeviceInfo(
            host=host,
            api_version="03.00",
            device_id="7413f810",
            firmware_version="02.03.00",
            channels=[1, 2],
        )

    monkeypatch.setattr("canresearch.cansub.client.probe_host", fake_probe)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "list", "--host", "192.0.2.1"])
    assert result.exit_code == 0
    assert "CANsub.2" in result.output
    assert "192.0.2.1" in result.output
    assert "7413f810" in result.output
    assert "Channels:" in result.output


def test_device_info_command(monkeypatch) -> None:
    monkeypatch.setattr(
        "canresearch.cansub.client.probe_host",
        lambda host, **kwargs: CansubDeviceInfo(host=host, device_id="abcd1234"),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["device", "info", "--host", "192.0.2.2"])
    assert result.exit_code == 0
    assert "abcd1234" in result.output


def test_device_list_connection_error(monkeypatch) -> None:
    from canresearch.cansub.exceptions import CansubConnectionError

    def fake_probe(host: str, **kwargs):
        _ = host, kwargs
        raise CansubConnectionError("Unable to connect to CANsub.2 at 192.0.2.3: timeout")

    monkeypatch.setattr("canresearch.cansub.client.probe_host", fake_probe)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "list", "--host", "192.0.2.3"])
    assert result.exit_code == 1
    assert "timeout" in result.output
