"""CLI smoke tests."""

from click.testing import CliRunner

from canresearch.cli import main


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "CAN research tool" in result.output


def test_cli_device_list() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["device", "list"])
    assert result.exit_code == 0
    assert "CANsub.2" in result.output


def test_cli_session_list() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["session", "list"])
    assert result.exit_code == 0


def test_reference_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["reference", "--help"])
    assert result.exit_code == 0
    assert "import-j1939" in result.output
    assert "validate" in result.output


def test_cli_mcp_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
