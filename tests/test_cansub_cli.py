"""CLI tests for CANsub device commands."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from canresearch.cansub.client import CansubChannelStatus, CansubDeviceInfo
from canresearch.cli import main


def test_device_list_without_host_shows_discovery_stub() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["device", "list"])
        assert result.exit_code == 0
        assert "discovery is not yet implemented" in result.output


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
    assert "192.0.2.1" in result.output
    assert "7413f810" in result.output


def test_device_info_uses_config_host(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('[cansub]\nhost = "configured.local"\n', encoding="utf-8")

    seen: dict[str, str] = {}

    def fake_probe(host: str, **kwargs):
        _ = kwargs
        seen["host"] = host
        return CansubDeviceInfo(host=host, device_id="abcd1234")

    monkeypatch.setattr("canresearch.cansub.client.probe_host", fake_probe)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "info"])
    assert result.exit_code == 0
    assert seen["host"] == "configured.local"
    assert "abcd1234" in result.output


def test_device_info_cli_host_overrides_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[cansub]\nhost = "configured.local"\n', encoding="utf-8")

    seen: dict[str, str] = {}

    def fake_probe(host: str, **kwargs):
        _ = kwargs
        seen["host"] = host
        return CansubDeviceInfo(host=host)

    monkeypatch.setattr("canresearch.cansub.client.probe_host", fake_probe)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "info", "--host", "override.local"])
    assert result.exit_code == 0
    assert seen["host"] == "override.local"


def test_device_info_missing_host_exits() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["device", "info"])
        assert result.exit_code != 0
        assert "No CANsub.2 host configured" in result.output


def test_config_show_and_set_host() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        set_result = runner.invoke(main, ["config", "set-host", "7413f810-usb.local"])
        assert set_result.exit_code == 0
        show_result = runner.invoke(main, ["config", "show"])
        assert show_result.exit_code == 0
        assert "7413f810-usb.local" in show_result.output


def test_device_channel_info(monkeypatch) -> None:
    def fake_get_channel_info(host: str, channel: int, **kwargs):
        _ = kwargs
        return CansubChannelStatus(
            channel=channel,
            host=host,
            state="stopped",
            frame_count=0,
            phy={"listen_only": False},
        )

    monkeypatch.setattr("canresearch.cansub.client.get_channel_info", fake_get_channel_info)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "channel-info", "1", "--host", "192.0.2.1"])
    assert result.exit_code == 0
    assert "Channel 1" in result.output
    assert "stopped" in result.output


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


def test_device_rx_uses_config_host(tmp_path: Path, monkeypatch) -> None:
    from canresearch.cansub.ws_client import CansubRxResult

    config_path = tmp_path / "config.toml"
    config_path.write_text('[cansub]\nhost = "configured.local"\n', encoding="utf-8")
    seen: dict[str, str] = {}

    def fake_rx(host: str, channel: int, **kwargs):
        _ = channel, kwargs
        seen["host"] = host
        return CansubRxResult(
            host=host,
            channel=1,
            connected=True,
            duration_s=1.0,
            frame_count=0,
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.cansub.ws_client.receive_frames_sync", fake_rx)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "rx", "1", "--duration", "1"])
    assert result.exit_code == 0
    assert seen["host"] == "configured.local"
    assert "Frames:     0" in result.output


def test_device_rx_cli_host_override(tmp_path: Path, monkeypatch) -> None:
    from canresearch.cansub.ws_client import CansubRxResult

    config_path = tmp_path / "config.toml"
    config_path.write_text('[cansub]\nhost = "configured.local"\n', encoding="utf-8")
    seen: dict[str, str] = {}

    def fake_rx(host: str, channel: int, **kwargs):
        _ = channel, kwargs
        seen["host"] = host
        return CansubRxResult(
            host=host,
            channel=1,
            connected=True,
            duration_s=1.0,
            frame_count=0,
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.cansub.ws_client.receive_frames_sync", fake_rx)
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "rx", "1", "--host", "override.local"])
    assert result.exit_code == 0
    assert seen["host"] == "override.local"


def test_device_rx_keyboard_interrupt(monkeypatch) -> None:
    def fake_rx(*args, **kwargs):
        _ = args, kwargs
        raise KeyboardInterrupt

    monkeypatch.setattr("canresearch.cansub.ws_client.receive_frames_sync", fake_rx)

    runner = CliRunner()
    result = runner.invoke(main, ["device", "rx", "1", "--host", "192.0.2.1"])
    assert result.exit_code == 0
    assert "Interrupted" in result.output
