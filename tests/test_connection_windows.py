"""Tests for scripts/connection_windows.py."""

from __future__ import annotations

import io
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.connection_windows as cw  # noqa: E402


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cw, "CONFIG_PATH", data / "config.toml")
    return data


def write_config(config_dir: Path, text: str) -> None:
    (config_dir / "config.toml").write_text(text, encoding="utf-8")


def runtime_env_config(
    instance_key: str = "local",
    install_dir: str = "__INSTALL_DIR__",
    *,
    include_secrets: bool = False,
) -> str:
    suffix = cw.instance_env_suffix(instance_key)
    secrets_block = ""
    if include_secrets:
        secrets_block = f"""
[connection.secrets]
api_key_env = "CANRESEARCH_{suffix}_API_KEY"
tunnel_id_env = "CANRESEARCH_{suffix}_TUNNEL_ID"
"""
    return f"""
[instance]
instance_key = "{instance_key}"

[connection]
kind = "openai-runtime-env"
mcp_url = "http://127.0.0.1:8765/mcp"
health_host = "127.0.0.1"
health_port = 8081
{secrets_block}
[tunnel]
profile = "can-research-{instance_key}"
install_dir = "{install_dir}"
"""


def test_instance_env_suffix_deterministic() -> None:
    assert cw.instance_env_suffix("local") == "LOCAL"
    assert cw.instance_env_suffix("laptop") == "LAPTOP"
    assert cw.instance_env_suffix("office") == "OFFICE"
    assert cw.instance_env_suffix("work-shop") == "WORK_SHOP"
    assert cw.instance_env_suffix("office_v2") == "OFFICE_V2"
    assert cw.default_secret_env_names("local") == (
        "CANRESEARCH_LOCAL_API_KEY",
        "CANRESEARCH_LOCAL_TUNNEL_ID",
    )
    assert cw.default_secret_env_names("laptop") == (
        "CANRESEARCH_LAPTOP_API_KEY",
        "CANRESEARCH_LAPTOP_TUNNEL_ID",
    )


def test_config_parsing_defaults(config_dir: Path) -> None:
    write_config(
        config_dir,
        """
[instance]
instance_key = "travel"

[tunnel]
health_port = 9090
""",
    )
    cfg = cw.settings()
    assert cfg.instance_key == "travel"
    assert cfg.kind is None
    assert cfg.health_port == 9090
    assert cfg.profile == "can-research-travel"
    assert cfg.api_key_env == "CANRESEARCH_TRAVEL_API_KEY"
    assert cfg.tunnel_id_env == "CANRESEARCH_TRAVEL_TUNNEL_ID"
    assert cw.resolve_kind(cfg) == "openai-profile-legacy"


def test_openai_runtime_env_config(config_dir: Path, tmp_path: Path) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    write_config(
        config_dir,
        f"""
[instance]
instance_key = "local"

[connection]
kind = "openai-runtime-env"
mcp_url = "http://127.0.0.1:8765/mcp"

[tunnel]
install_dir = "{install.as_posix()}"
""",
    )
    cfg = cw.settings()
    assert cfg.kind == "openai-runtime-env"
    assert cfg.mcp_url == "http://127.0.0.1:8765/mcp"
    assert cfg.api_key_env == "CANRESEARCH_LOCAL_API_KEY"
    assert cfg.tunnel_id_env == "CANRESEARCH_LOCAL_TUNNEL_ID"
    assert cw.resolve_kind(cfg) == "openai-runtime-env"


def test_derived_secret_names_when_secrets_section_omitted(config_dir: Path, tmp_path: Path) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    write_config(
        config_dir,
        f"""
[instance]
instance_key = "laptop"

[connection]
kind = "openai-runtime-env"

[tunnel]
install_dir = "{install.as_posix()}"
""",
    )
    cfg = cw.settings()
    assert cfg.api_key_env == "CANRESEARCH_LAPTOP_API_KEY"
    assert cfg.tunnel_id_env == "CANRESEARCH_LAPTOP_TUNNEL_ID"


def test_explicit_secret_name_override(config_dir: Path) -> None:
    write_config(
        config_dir,
        """
[instance]
instance_key = "laptop"

[connection]
kind = "openai-runtime-env"

[connection.secrets]
api_key_env = "CANRESEARCH_CUSTOM_API_KEY"
tunnel_id_env = "CANRESEARCH_CUSTOM_TUNNEL_ID"
""",
    )
    cfg = cw.settings()
    assert cfg.api_key_env == "CANRESEARCH_CUSTOM_API_KEY"
    assert cfg.tunnel_id_env == "CANRESEARCH_CUSTOM_TUNNEL_ID"


@pytest.mark.parametrize(
    "tunnel_id,valid",
    [
        ("tunnel_" + "a" * 32, True),
        ("tunnel_" + "0" * 32, True),
        ("tunnel_ABCDEF0123456789abcdef012345678", False),
        ("tunnel_short", False),
        ("not_a_tunnel", False),
    ],
)
def test_tunnel_id_validation(tunnel_id: str, valid: bool) -> None:
    assert bool(cw.TUNNEL_ID_PATTERN.fullmatch(tunnel_id)) is valid


def test_redact_never_shows_secret() -> None:
    secret = "sk-super-secret-runtime-key-value"
    rendered = cw.redact(secret)
    assert secret not in rendered
    assert "redacted" in rendered


def test_build_child_env_injects_runtime_variables(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    exe = install / "tunnel-client.exe"
    exe.write_text("stub", encoding="utf-8")
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))

    api_env, tunnel_env = cw.default_secret_env_names("local")
    monkeypatch.setenv(api_env, "test-api-key-value")
    monkeypatch.setenv(tunnel_env, "tunnel_" + "a" * 32)

    backend = cw.OpenaiRuntimeEnvBackend(cw.settings())
    env = backend.build_child_env()

    assert env["CONTROL_PLANE_API_KEY"] == "test-api-key-value"
    assert env["CONTROL_PLANE_TUNNEL_ID"] == "tunnel_" + "a" * 32
    assert env["MCP_SERVER_URL"] == "http://127.0.0.1:8765/mcp"
    assert env["HEALTH_LISTEN_ADDR"] == "127.0.0.1:8081"


def test_launch_argv_never_uses_doctor_or_init(config_dir: Path, tmp_path: Path) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))
    backend = cw.OpenaiRuntimeEnvBackend(cw.settings())
    argv = backend.launch_argv()
    joined = " ".join(argv).lower()
    assert "doctor" not in joined
    assert "init" not in joined
    assert argv[-1] == "run"


def test_missing_connection_section_gives_configure_action(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_config(
        config_dir,
        """
[connection]
kind = "unknown-backend"
""",
    )
    code = cw.validate_config_cmd()
    out = capsys.readouterr().out
    assert code == 2
    assert cw.CONFIGURE_CMD in out


def test_start_check_reports_configure_when_secrets_missing(
    config_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    (install / "tunnel-client.exe").write_text("stub", encoding="utf-8")
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))

    with patch.object(cw, "read_user_env", return_value=None):
        backend = cw.OpenaiRuntimeEnvBackend(cw.settings())
        code, messages = backend.start_check()

    assert code == 3
    text = "\n".join(messages)
    assert cw.CONFIGURE_CMD in text


def test_start_check_reuses_healthy_listener(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    (install / "tunnel-client.exe").write_text("stub", encoding="utf-8")
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))

    api_env, tunnel_env = cw.default_secret_env_names("local")
    monkeypatch.setenv(api_env, "key")
    monkeypatch.setenv(tunnel_env, "tunnel_" + "b" * 32)

    with patch.object(cw, "tcp_open", return_value=True):
        backend = cw.OpenaiRuntimeEnvBackend(cw.settings())
        code, messages = backend.start_check()

    assert code == 0
    assert any("already running" in m for m in messages)


def test_status_output_does_not_echo_secrets(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    (install / "tunnel-client.exe").write_text("stub", encoding="utf-8")
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))

    secret_key = "sk-test-secret-should-not-appear"
    secret_tunnel = "tunnel_" + "c" * 32
    api_env, tunnel_env = cw.default_secret_env_names("local")

    def fake_read(name: str) -> str | None:
        if name == api_env:
            return secret_key
        if name == tunnel_env:
            return secret_tunnel
        return None

    with patch.object(cw, "read_user_env", side_effect=fake_read):
        with patch.object(cw, "tcp_open", return_value=True):
            code = cw.status_cmd()

    out = capsys.readouterr().out
    assert code == 0
    assert secret_key not in out
    assert secret_tunnel not in out


def test_configure_reuses_persisted_values(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    exe = install / "tunnel-client.exe"
    exe.write_text("stub", encoding="utf-8")
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))

    api_env, tunnel_env = cw.default_secret_env_names("local")
    monkeypatch.setenv(api_env, "persisted-key")
    monkeypatch.setenv(tunnel_env, "tunnel_" + "d" * 32)

    def fake_runtime(_exe: Path) -> tuple[bool, str]:
        return True, "CONTROL_PLANE_API_KEY CONTROL_PLANE_TUNNEL_ID MCP_SERVER_URL HEALTH_LISTEN_ADDR"

    with patch.object(cw, "runtime_supports_env_model", side_effect=fake_runtime):
        with patch.object(cw, "persist_user_env") as persist:
            code = cw.configure_cmd()

    assert code == 0
    persist.assert_not_called()
    out = capsys.readouterr().out
    assert "persisted-key" not in out
    assert "tunnel_" + "d" * 32 not in out


def test_legacy_doctor_skipped_for_runtime_env(config_dir: Path, tmp_path: Path) -> None:
    install = tmp_path / "tunnel"
    install.mkdir()
    write_config(config_dir, runtime_env_config(install_dir=str(install).replace("\\", "/")))
    with patch.object(cw.subprocess, "run") as run:
        code = cw.legacy_doctor_cmd()
    assert code == 0
    run.assert_not_called()


def test_runtime_probe_checks_help_tokens(tmp_path: Path) -> None:
    exe = tmp_path / "tunnel-client.exe"
    exe.write_text("stub", encoding="utf-8")

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[-1] == "--version":
            return subprocess.CompletedProcess(args, 0, "v0.0.14", "")
        return subprocess.CompletedProcess(
            args,
            0,
            "Uses CONTROL_PLANE_API_KEY CONTROL_PLANE_TUNNEL_ID MCP_SERVER_URL HEALTH_LISTEN_ADDR",
            "",
        )

    with patch.object(cw.subprocess, "run", side_effect=fake_run):
        ok, _ = cw.runtime_supports_env_model(exe)
    assert ok is True


def _install_runtime_config(config_dir: Path, tmp_path: Path, instance_key: str = "local") -> Path:
    install = tmp_path / "tunnel"
    install.mkdir()
    (install / "tunnel-client.exe").write_text("stub", encoding="utf-8")
    write_config(
        config_dir,
        runtime_env_config(instance_key=instance_key, install_dir=str(install).replace("\\", "/")),
    )
    return install


def _fake_runtime(_exe: Path) -> tuple[bool, str]:
    return True, "CONTROL_PLANE_API_KEY CONTROL_PLANE_TUNNEL_ID MCP_SERVER_URL HEALTH_LISTEN_ADDR"


def test_configure_migrates_legacy_secrets_without_prompt(
    config_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_runtime_config(config_dir, tmp_path, instance_key="laptop")
    cfg = cw.settings()
    legacy_key = "sk-legacy-runtime-key-from-user-env"
    legacy_tunnel = "tunnel_" + "e" * 32

    def fake_read(name: str) -> str | None:
        if name == cfg.api_key_env or name == cfg.tunnel_id_env:
            return None
        if name == cw.LEGACY_API_KEY_ENV:
            return legacy_key
        if name == cw.LEGACY_TUNNEL_ID_ENV:
            return legacy_tunnel
        return None

    with patch.object(cw, "runtime_supports_env_model", side_effect=_fake_runtime):
        with patch.object(cw, "read_user_env", side_effect=fake_read):
            with patch.object(cw, "persist_user_env") as persist:
                with patch.object(cw.getpass, "getpass", side_effect=AssertionError("should not prompt")):
                    with patch("builtins.input", side_effect=AssertionError("should not prompt")):
                        code = cw.configure_cmd()

    assert code == 0
    persist.assert_any_call(cfg.api_key_env, legacy_key)
    persist.assert_any_call(cfg.tunnel_id_env, legacy_tunnel)
    out = capsys.readouterr().out
    assert f"Migrated existing persisted API-key reference to {cfg.api_key_env}" in out
    assert f"Migrated existing persisted tunnel identity to {cfg.tunnel_id_env}" in out
    assert legacy_key not in out
    assert legacy_tunnel not in out


def test_configure_invalid_legacy_tunnel_id_not_migrated(
    config_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_runtime_config(config_dir, tmp_path, instance_key="laptop")
    cfg = cw.settings()
    valid_tunnel = "tunnel_" + "f" * 32

    def fake_read(name: str) -> str | None:
        if name == cfg.api_key_env:
            return "namespaced-key"
        if name == cfg.tunnel_id_env:
            return None
        if name == cw.LEGACY_TUNNEL_ID_ENV:
            return "tunnel_invalid_legacy"
        return None

    with patch.object(cw, "runtime_supports_env_model", side_effect=_fake_runtime):
        with patch.object(cw, "read_user_env", side_effect=fake_read):
            with patch.object(cw, "persist_user_env") as persist:
                with patch("builtins.input", return_value=valid_tunnel):
                    code = cw.configure_cmd()

    assert code == 0
    tunnel_calls = [call for call in persist.call_args_list if call.args[0] == cfg.tunnel_id_env]
    assert len(tunnel_calls) == 1
    assert tunnel_calls[0].args[1] == valid_tunnel
    out = capsys.readouterr().out
    assert "Migrated existing persisted tunnel identity" not in out
    assert "tunnel_invalid_legacy" not in out


def test_configure_namespaced_values_precede_legacy(
    config_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_runtime_config(config_dir, tmp_path, instance_key="laptop")
    cfg = cw.settings()
    namespaced_key = "sk-namespaced-preferred-key"
    namespaced_tunnel = "tunnel_" + "9" * 32

    def fake_read(name: str) -> str | None:
        if name == cfg.api_key_env:
            return namespaced_key
        if name == cfg.tunnel_id_env:
            return namespaced_tunnel
        if name == cw.LEGACY_API_KEY_ENV:
            return "sk-legacy-should-not-win"
        if name == cw.LEGACY_TUNNEL_ID_ENV:
            return "tunnel_" + "8" * 32
        return None

    with patch.object(cw, "runtime_supports_env_model", side_effect=_fake_runtime):
        with patch.object(cw, "read_user_env", side_effect=fake_read):
            with patch.object(cw, "persist_user_env") as persist:
                code = cw.configure_cmd()

    assert code == 0
    persist.assert_not_called()
    out = capsys.readouterr().out
    assert "Migrated existing persisted" not in out
    assert namespaced_key not in out
    assert namespaced_tunnel not in out
    assert "sk-legacy-should-not-win" not in out


def test_run_tunnel_launches_subprocess_with_child_env(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install = _install_runtime_config(config_dir, tmp_path, instance_key="laptop")
    cfg = cw.settings()
    secret_key = "sk-run-tunnel-secret-key-value"
    secret_tunnel = "tunnel_" + "a" * 32
    monkeypatch.setenv(cfg.api_key_env, secret_key)
    monkeypatch.setenv(cfg.tunnel_id_env, secret_tunnel)

    completed = subprocess.CompletedProcess(args=["run"], returncode=0)

    with patch.object(cw.subprocess, "run", return_value=completed) as run:
        code = cw.run_tunnel_cmd()

    assert code == 0
    run.assert_called_once()
    argv, kwargs = run.call_args.args, run.call_args.kwargs
    assert argv[0][-1] == "run"
    env = kwargs["env"]
    assert env["CONTROL_PLANE_API_KEY"] == secret_key
    assert env["CONTROL_PLANE_TUNNEL_ID"] == secret_tunnel
    assert env["MCP_SERVER_URL"] == cfg.mcp_url
    assert env["HEALTH_LISTEN_ADDR"] == f"{cfg.health_host}:{cfg.health_port}"
    assert kwargs["cwd"] == str(install)
    out = capsys.readouterr().out
    assert secret_key not in out
    assert secret_tunnel not in out


def test_run_tunnel_propagates_exit_code(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_runtime_config(config_dir, tmp_path, instance_key="laptop")
    cfg = cw.settings()
    monkeypatch.setenv(cfg.api_key_env, "key")
    monkeypatch.setenv(cfg.tunnel_id_env, "tunnel_" + "b" * 32)

    with patch.object(
        cw.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(args=["run"], returncode=7),
    ):
        code = cw.run_tunnel_cmd()

    assert code == 7


def test_start_cmd_runtime_env_launch_flow() -> None:
    cmd_text = (ROOT / "start-can-research.cmd").read_text(encoding="utf-8")
    lower = cmd_text.lower()

    assert "connection_windows.py start-check" in lower
    assert ":launch_runtime_env_tunnel" in lower
    assert "connection_windows.py run-tunnel" in lower
    assert "if %start_rc% equ 10 goto launch_tunnel" in lower

    runtime_start = lower.index(":launch_runtime_env_tunnel")
    legacy_start = lower.index(":launch_legacy_tunnel")
    runtime_block = lower[runtime_start : lower.index(":wait_for_tunnel")]
    legacy_block = lower[legacy_start:runtime_start]
    assert "doctor" not in runtime_block
    assert "legacy-doctor" not in runtime_block
    assert "legacy-doctor" in legacy_block
    assert "run --profile" in legacy_block
