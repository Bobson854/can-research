"""Windows connection layer for CAN Research tunnel startup.

Supports backend-aware configuration, one-time interactive setup, start
preflight, and diagnostics. Keeps secrets out of TOML and normal output.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import socket
import subprocess
import sys
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("data/config.toml")
DEFAULT_HEALTH_HOST = "127.0.0.1"
DEFAULT_HEALTH_PORT = 8081
DEFAULT_MCP_URL = "http://127.0.0.1:8765/mcp"
DEFAULT_INSTALL_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    / "CAN Research"
    / "tunnel-client"
)

TUNNEL_ID_PATTERN = re.compile(r"^tunnel_[a-z0-9]{32}$")
CONFIGURE_CMD = "uv run python scripts\\connection_windows.py configure"

LEGACY_API_KEY_ENV = "CONTROL_PLANE_API_KEY"
LEGACY_TUNNEL_ID_ENV = "CONTROL_PLANE_TUNNEL_ID"

SUPPORTED_KINDS = frozenset({"openai-runtime-env", "openai-profile-legacy"})


@dataclass(frozen=True)
class ConnectionSettings:
    instance_key: str
    kind: str | None
    mcp_url: str
    health_host: str
    health_port: int
    install_dir: Path
    exe: Path
    api_key_env: str
    tunnel_id_env: str
    profile: str
    connection_section_present: bool


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def instance_env_suffix(instance_key: str) -> str:
    """Derive a deterministic, valid Windows env-var token from instance_key."""
    normalized = instance_key.strip().upper().replace("-", "_")
    normalized = re.sub(r"[^A-Z0-9_]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "LOCAL"


def default_secret_env_names(instance_key: str) -> tuple[str, str]:
    suffix = instance_env_suffix(instance_key)
    return (
        f"CANRESEARCH_{suffix}_API_KEY",
        f"CANRESEARCH_{suffix}_TUNNEL_ID",
    )


def settings() -> ConnectionSettings:
    cfg = load_config()
    instance = cfg.get("instance", {})
    tunnel = cfg.get("tunnel", {})
    connection = cfg.get("connection", {})
    secrets = connection.get("secrets", {}) if isinstance(connection, dict) else {}

    instance_key = str(instance.get("instance_key", "local")).strip() or "local"
    default_api_env, default_tunnel_env = default_secret_env_names(instance_key)

    kind_raw = connection.get("kind") if isinstance(connection, dict) else None
    kind = str(kind_raw).strip() if kind_raw else None

    mcp_url = str(connection.get("mcp_url", DEFAULT_MCP_URL)).strip() or DEFAULT_MCP_URL
    health_host = str(connection.get("health_host", tunnel.get("health_host", DEFAULT_HEALTH_HOST))).strip()
    health_host = health_host or DEFAULT_HEALTH_HOST
    health_port = int(connection.get("health_port", tunnel.get("health_port", DEFAULT_HEALTH_PORT)))

    install_dir = Path(
        os.path.expandvars(str(tunnel.get("install_dir", DEFAULT_INSTALL_DIR)))
    ).expanduser()
    exe = install_dir / "tunnel-client.exe"
    profile = str(tunnel.get("profile", f"can-research-{instance_key}")).strip()

    api_key_env = default_api_env
    tunnel_id_env = default_tunnel_env
    if isinstance(secrets, dict):
        if "api_key_env" in secrets:
            api_key_env = str(secrets["api_key_env"]).strip() or default_api_env
        if "tunnel_id_env" in secrets:
            tunnel_id_env = str(secrets["tunnel_id_env"]).strip() or default_tunnel_env

    return ConnectionSettings(
        instance_key=instance_key,
        kind=kind or None,
        mcp_url=mcp_url,
        health_host=health_host,
        health_port=health_port,
        install_dir=install_dir,
        exe=exe,
        api_key_env=api_key_env,
        tunnel_id_env=tunnel_id_env,
        profile=profile,
        connection_section_present=isinstance(connection, dict) and bool(connection),
    )


def resolve_kind(cfg: ConnectionSettings) -> str | None:
    if cfg.kind in SUPPORTED_KINDS:
        return cfg.kind
    if not cfg.connection_section_present:
        return "openai-profile-legacy"
    return None


def tcp_open(host: str, port: int, timeout: float = 0.75) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def read_user_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            raw, _ = winreg.QueryValueEx(key, name)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    except OSError:
        return None
    return None


def persist_user_env(name: str, value: str) -> None:
    os.environ[name] = value
    if sys.platform != "win32":
        return
    subprocess.run(
        ["setx", name, value],
        check=True,
        capture_output=True,
        text=True,
    )


def redact(value: str | None) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "(set, redacted)"
    return f"(set, {len(value)} chars, redacted)"


def migrate_legacy_secrets(cfg: ConnectionSettings) -> tuple[str | None, str | None, list[str]]:
    """Copy generic User-level OpenAI runtime vars into namespaced vars once.

    Does not read, alter, or delete the legacy generic variables.
    """
    messages: list[str] = []
    api_key = read_user_env(cfg.api_key_env)
    tunnel_id = read_user_env(cfg.tunnel_id_env)

    if not api_key:
        legacy_api = read_user_env(LEGACY_API_KEY_ENV)
        if legacy_api:
            persist_user_env(cfg.api_key_env, legacy_api)
            api_key = legacy_api
            messages.append(
                f"[OK] Migrated existing persisted API-key reference to {cfg.api_key_env}"
            )

    if not tunnel_id:
        legacy_tunnel = read_user_env(LEGACY_TUNNEL_ID_ENV)
        if legacy_tunnel and TUNNEL_ID_PATTERN.fullmatch(legacy_tunnel):
            persist_user_env(cfg.tunnel_id_env, legacy_tunnel)
            tunnel_id = legacy_tunnel
            messages.append(
                f"[OK] Migrated existing persisted tunnel identity to {cfg.tunnel_id_env}"
            )

    return api_key, tunnel_id, messages


def runtime_supports_env_model(exe: Path) -> tuple[bool, str]:
    if not exe.exists():
        return False, f"tunnel executable missing: {exe}"
    try:
        version = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        help_run = subprocess.run(
            [str(exe), "run", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"failed to probe tunnel runtime: {exc}"

    combined = f"{version.stdout}\n{version.stderr}\n{help_run.stdout}\n{help_run.stderr}"
    required = ("CONTROL_PLANE_API_KEY", "CONTROL_PLANE_TUNNEL_ID", "MCP_SERVER_URL", "HEALTH_LISTEN_ADDR")
    missing = [token for token in required if token not in combined]
    if missing:
        return False, f"runtime run --help missing expected tokens: {', '.join(missing)}"
    if help_run.returncode not in (0, 1):
        return False, "runtime run --help returned unexpected exit code"
    return True, combined.strip()


class ConnectionBackend(ABC):
    kind: str

    def __init__(self, cfg: ConnectionSettings) -> None:
        self.cfg = cfg

    @abstractmethod
    def validate_config(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def configure_interactive(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def build_child_env(self) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def launch_argv(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def status_lines(self) -> tuple[list[str], int]:
        """Return (lines, exit_code). exit_code 0 = healthy."""
        raise NotImplementedError

    @abstractmethod
    def start_check(self) -> tuple[int, list[str]]:
        """Return (code, messages). 0=healthy reuse, 10=launch needed."""
        raise NotImplementedError


class OpenaiRuntimeEnvBackend(ConnectionBackend):
    kind = "openai-runtime-env"

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self.cfg.kind != self.kind:
            errors.append(f"[connection].kind must be {self.kind!r}")
        if not self.cfg.mcp_url.startswith("http"):
            errors.append("[connection].mcp_url must be an http(s) URL")
        if self.cfg.health_port < 1 or self.cfg.health_port > 65535:
            errors.append("[connection].health_port must be between 1 and 65535")
        return errors

    def _read_secrets(self) -> tuple[str | None, str | None]:
        return read_user_env(self.cfg.api_key_env), read_user_env(self.cfg.tunnel_id_env)

    def configure_interactive(self) -> int:
        errors = self.validate_config()
        if errors:
            for line in errors:
                print(f"[FAIL] {line}")
            return 1

        ok, detail = runtime_supports_env_model(self.cfg.exe)
        if not ok:
            print(f"[FAIL] {detail}")
            return 1
        print("[OK]   OpenAI tunnel runtime supports environment-backed run")

        api_key, tunnel_id, migrate_messages = migrate_legacy_secrets(self.cfg)
        for line in migrate_messages:
            print(line)

        if not api_key:
            entered = getpass.getpass(
                f"Enter OpenAI runtime API key (stored as User env {self.cfg.api_key_env}): "
            ).strip()
            if not entered:
                print("[FAIL] API key is required.")
                return 1
            persist_user_env(self.cfg.api_key_env, entered)
            api_key = entered
            print(f"[OK]   Persisted {self.cfg.api_key_env} (value redacted)")
        else:
            print(f"[OK]   Reusing persisted {self.cfg.api_key_env} {redact(api_key)}")

        if not tunnel_id:
            entered = input(
                f"Enter OpenAI tunnel ID for {self.cfg.api_key_env} "
                f"(stored as User env {self.cfg.tunnel_id_env}): "
            ).strip()
            if not TUNNEL_ID_PATTERN.fullmatch(entered):
                print("[FAIL] Tunnel ID must match ^tunnel_[a-z0-9]{32}$")
                return 1
            persist_user_env(self.cfg.tunnel_id_env, entered)
            tunnel_id = entered
            print(f"[OK]   Persisted {self.cfg.tunnel_id_env} (value redacted)")
        else:
            if not TUNNEL_ID_PATTERN.fullmatch(tunnel_id):
                print(f"[FAIL] Persisted {self.cfg.tunnel_id_env} has invalid format.")
                print(f"       Run configure again to replace it.")
                return 1
            print(f"[OK]   Reusing persisted {self.cfg.tunnel_id_env} {redact(tunnel_id)}")

        print("[OK]   Connection configuration complete.")
        print(f"       Normal startup: .\\start-can-research.cmd")
        return 0

    def build_child_env(self) -> dict[str, str]:
        api_key, tunnel_id = self._read_secrets()
        if not api_key or not tunnel_id:
            raise RuntimeError("connection secrets are not configured")
        env = os.environ.copy()
        env["CONTROL_PLANE_API_KEY"] = api_key
        env["CONTROL_PLANE_TUNNEL_ID"] = tunnel_id
        env["MCP_SERVER_URL"] = self.cfg.mcp_url
        env["HEALTH_LISTEN_ADDR"] = f"{self.cfg.health_host}:{self.cfg.health_port}"
        return env

    def launch_argv(self) -> list[str]:
        argv = [str(self.cfg.exe), "run"]
        joined = " ".join(argv).lower()
        if "doctor" in joined or "init" in joined:
            raise RuntimeError("openai-runtime-env must not invoke doctor or init")
        return argv

    def status_lines(self) -> tuple[list[str], int]:
        lines: list[str] = []
        ok = True
        lines.append(f"       backend: {self.kind}")
        lines.append(f"       instance: {self.cfg.instance_key}")
        lines.append(f"       mcp_url: {self.cfg.mcp_url}")
        lines.append(f"       health:  {self.cfg.health_host}:{self.cfg.health_port}")

        if self.cfg.exe.exists():
            lines.append(f"[OK]   tunnel executable: {self.cfg.exe}")
        else:
            lines.append(f"[FAIL] tunnel executable missing: {self.cfg.exe}")
            lines.append("       Run setup.cmd")
            return lines, 4

        config_errors = self.validate_config()
        if config_errors:
            lines.append("[FAIL] connection not configured")
            for err in config_errors:
                lines.append(f"       {err}")
            lines.append(f"       Next: {CONFIGURE_CMD}")
            return lines, 2

        api_key, tunnel_id = self._read_secrets()
        if api_key:
            lines.append(f"[OK]   {self.cfg.api_key_env} {redact(api_key)}")
        else:
            lines.append(f"[FAIL] {self.cfg.api_key_env} is not persisted")
            ok = False

        if tunnel_id:
            if TUNNEL_ID_PATTERN.fullmatch(tunnel_id):
                lines.append(f"[OK]   {self.cfg.tunnel_id_env} {redact(tunnel_id)}")
            else:
                lines.append(f"[FAIL] {self.cfg.tunnel_id_env} has invalid format")
                ok = False
        else:
            lines.append(f"[FAIL] {self.cfg.tunnel_id_env} is not persisted")
            ok = False

        if not api_key or not tunnel_id:
            lines.append(f"       Next: {CONFIGURE_CMD}")

        if tcp_open(self.cfg.health_host, self.cfg.health_port):
            lines.append("[OK]   tunnel health listener is reachable")
        else:
            lines.append("[FAIL] tunnel health listener is not reachable")
            ok = False

        if not ok and (not api_key or not tunnel_id):
            return lines, 3
        return lines, 0 if ok else 1

    def start_check(self) -> tuple[int, list[str]]:
        if not self.cfg.exe.exists():
            return 4, [f"[FAIL] tunnel executable missing: {self.cfg.exe}", "       Run setup.cmd"]

        config_errors = self.validate_config()
        if config_errors:
            msgs = ["[FAIL] connection not configured", f"       Next: {CONFIGURE_CMD}"]
            msgs.extend(f"       {e}" for e in config_errors)
            return 2, msgs

        api_key, tunnel_id = self._read_secrets()
        if not api_key or not tunnel_id:
            missing = []
            if not api_key:
                missing.append(self.cfg.api_key_env)
            if not tunnel_id:
                missing.append(self.cfg.tunnel_id_env)
            return 3, [
                "[FAIL] persisted connection secrets are missing",
                f"       Missing: {', '.join(missing)}",
                f"       Next: {CONFIGURE_CMD}",
            ]

        if tcp_open(self.cfg.health_host, self.cfg.health_port):
            return 0, ["[OK]   OpenAI tunnel already running (health listener reachable)"]

        return 10, ["[INFO] OpenAI tunnel will be started"]


class OpenaiProfileLegacyBackend(ConnectionBackend):
    kind = "openai-profile-legacy"

    def validate_config(self) -> list[str]:
        if not self.cfg.profile:
            return ["[tunnel].profile is required for legacy profile mode"]
        return []

    def configure_interactive(self) -> int:
        print("[INFO] Legacy profile mode does not use connection_windows.py configure.")
        print("       See docs/MCP_SETUP.md (Office/profile workflow).")
        return 0

    def build_child_env(self) -> dict[str, str]:
        return os.environ.copy()

    def launch_argv(self) -> list[str]:
        return [
            str(self.cfg.exe),
            "run",
            "--profile",
            self.cfg.profile,
            "--health.listen-addr",
            f"{self.cfg.health_host}:{self.cfg.health_port}",
        ]

    def status_lines(self) -> tuple[list[str], int]:
        lines: list[str] = []
        ok = True
        lines.append(f"       backend: {self.kind} (legacy profile metadata)")
        lines.append(f"       profile: {self.cfg.profile}")
        lines.append(f"       health:  {self.cfg.health_host}:{self.cfg.health_port}")

        if self.cfg.exe.exists():
            lines.append(f"[OK]   tunnel executable: {self.cfg.exe}")
        else:
            lines.append(f"[FAIL] tunnel executable missing: {self.cfg.exe}")
            lines.append("       Run setup.cmd")
            return lines, 4

        if os.environ.get("CONTROL_PLANE_API_KEY") or read_user_env("CONTROL_PLANE_API_KEY"):
            lines.append("[OK]   CONTROL_PLANE_API_KEY is available")
        else:
            lines.append("[WARN] CONTROL_PLANE_API_KEY is not available in this process")

        if tcp_open(self.cfg.health_host, self.cfg.health_port):
            lines.append("[OK]   tunnel health listener is reachable")
        else:
            lines.append("[FAIL] tunnel health listener is not reachable")
            ok = False

        return lines, 0 if ok else 1

    def start_check(self) -> tuple[int, list[str]]:
        if not self.cfg.exe.exists():
            return 4, [f"[FAIL] tunnel executable missing: {self.cfg.exe}", "       Run setup.cmd"]

        if tcp_open(self.cfg.health_host, self.cfg.health_port):
            return 0, ["[OK]   OpenAI tunnel already running (health listener reachable)"]

        if not (os.environ.get("CONTROL_PLANE_API_KEY") or read_user_env("CONTROL_PLANE_API_KEY")):
            return 3, [
                "[FAIL] CONTROL_PLANE_API_KEY is not available",
                "       If set with setx, open a new terminal.",
            ]

        return 10, ["[INFO] OpenAI tunnel will be started (legacy profile mode)"]


def get_backend(cfg: ConnectionSettings | None = None) -> ConnectionBackend | None:
    cfg = cfg or settings()
    kind = resolve_kind(cfg)
    if kind == "openai-runtime-env":
        return OpenaiRuntimeEnvBackend(cfg)
    if kind == "openai-profile-legacy":
        return OpenaiProfileLegacyBackend(cfg)
    return None


def validate_config_cmd() -> int:
    cfg = settings()
    kind = resolve_kind(cfg)
    if kind is None:
        print("[FAIL] connection not configured for a supported backend")
        print(f"       Next: {CONFIGURE_CMD}")
        return 2
    backend = get_backend(cfg)
    assert backend is not None
    errors = backend.validate_config()
    if errors:
        for err in errors:
            print(f"[FAIL] {err}")
        return 1
    print(f"[OK]   connection backend: {kind}")
    return 0


def configure_cmd() -> int:
    cfg = settings()
    kind = resolve_kind(cfg)
    if kind != "openai-runtime-env":
        print("[FAIL] configure applies to [connection].kind = \"openai-runtime-env\" only.")
        if kind is None:
            print("       Add a [connection] section to data/config.toml first.")
            print("       See config.toml.example")
        return 2
    backend = get_backend(cfg)
    assert isinstance(backend, OpenaiRuntimeEnvBackend)
    return backend.configure_interactive()


def status_cmd() -> int:
    cfg = settings()
    kind = resolve_kind(cfg)
    if kind is None:
        print("[FAIL] connection not configured")
        print(f"       Next: {CONFIGURE_CMD}")
        return 2
    backend = get_backend(cfg)
    assert backend is not None
    lines, code = backend.status_lines()
    for line in lines:
        print(line)
    return code


def start_check_cmd() -> int:
    cfg = settings()
    kind = resolve_kind(cfg)
    if kind is None:
        print("[FAIL] connection not configured")
        print(f"       Next: {CONFIGURE_CMD}")
        return 2
    backend = get_backend(cfg)
    assert backend is not None
    code, messages = backend.start_check()
    for line in messages:
        print(line)
    return code


def emit_env_cmd() -> int:
    cfg = settings()
    kind = resolve_kind(cfg) or ""
    print(f'set "CONN_KIND={kind}"')
    print(f'set "TUNNEL_EXE={cfg.exe}"')
    print(f'set "TUNNEL_DIR={cfg.install_dir}"')
    print(f'set "TUNNEL_PROFILE={cfg.profile}"')
    print(f'set "TUNNEL_HEALTH_HOST={cfg.health_host}"')
    print(f'set "TUNNEL_HEALTH_PORT={cfg.health_port}"')
    print(f'set "CONN_MCP_URL={cfg.mcp_url}"')
    print(f'set "CONN_CONFIGURE_CMD={CONFIGURE_CMD}"')
    return 0


def run_tunnel_process(argv: list[str], env: dict[str, str] | None, cwd: Path | None) -> int:
    """Run tunnel-client in the foreground with inherited stdio."""
    run_cwd = str(cwd) if cwd is not None and cwd.exists() else None
    result = subprocess.run(argv, env=env, cwd=run_cwd)
    return int(result.returncode)


def run_tunnel_cmd() -> int:
    cfg = settings()
    backend = get_backend(cfg)
    if backend is None:
        print("[FAIL] connection not configured")
        return 2
    if isinstance(backend, OpenaiRuntimeEnvBackend):
        try:
            env = backend.build_child_env()
        except RuntimeError as exc:
            print(f"[FAIL] {exc}")
            print(f"       Next: {CONFIGURE_CMD}")
            return 3
        argv = backend.launch_argv()
        return run_tunnel_process(argv, env, cfg.install_dir)

    argv = backend.launch_argv()
    return run_tunnel_process(argv, None, cfg.install_dir)


def wait_health_cmd(timeout_s: float) -> int:
    cfg = settings()
    deadline = __import__("time").time() + timeout_s
    while __import__("time").time() < deadline:
        if tcp_open(cfg.health_host, cfg.health_port):
            return 0
        __import__("time").sleep(1)
    return 1


def legacy_doctor_cmd() -> int:
    """Run tunnel-client doctor for legacy profile mode only."""
    cfg = settings()
    if resolve_kind(cfg) != "openai-profile-legacy":
        return 0
    if not cfg.exe.exists():
        print(f"[FAIL] tunnel executable missing: {cfg.exe}")
        return 1
    result = subprocess.run(
        [
            str(cfg.exe),
            "doctor",
            "--profile",
            cfg.profile,
            "--explain",
            "--health.listen-addr",
            f"{cfg.health_host}:{cfg.health_port}",
        ],
        check=False,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows connection helper for CAN Research")
    parser.add_argument(
        "command",
        choices=(
            "validate",
            "configure",
            "status",
            "start-check",
            "env",
            "run-tunnel",
            "wait-health",
            "legacy-doctor",
        ),
    )
    parser.add_argument("--timeout", type=float, default=12.0, help="wait-health timeout seconds")
    args = parser.parse_args()

    handlers = {
        "validate": validate_config_cmd,
        "configure": configure_cmd,
        "status": status_cmd,
        "start-check": start_check_cmd,
        "env": emit_env_cmd,
        "run-tunnel": run_tunnel_cmd,
        "wait-health": lambda: wait_health_cmd(args.timeout),
        "legacy-doctor": legacy_doctor_cmd,
    }
    return handlers[args.command]()


if __name__ == "__main__":
    sys.exit(main())
