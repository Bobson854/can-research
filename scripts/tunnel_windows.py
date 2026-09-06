from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import tomllib
from pathlib import Path

CONFIG_PATH = Path("data/config.toml")
DEFAULT_HEALTH_HOST = "127.0.0.1"
DEFAULT_HEALTH_PORT = 8081
DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "CAN Research" / "tunnel-client"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def settings() -> dict[str, str | int | Path]:
    cfg = load_config()
    instance = cfg.get("instance", {})
    tunnel = cfg.get("tunnel", {})
    instance_key = str(instance.get("instance_key", "local")).strip() or "local"
    profile = str(tunnel.get("profile", f"can-research-{instance_key}")).strip()
    health_host = str(tunnel.get("health_host", DEFAULT_HEALTH_HOST)).strip() or DEFAULT_HEALTH_HOST
    health_port = int(tunnel.get("health_port", DEFAULT_HEALTH_PORT))
    install_dir = Path(os.path.expandvars(str(tunnel.get("install_dir", DEFAULT_INSTALL_DIR)))).expanduser()
    exe = install_dir / "tunnel-client.exe"
    return {
        "instance_key": instance_key,
        "profile": profile,
        "health_host": health_host,
        "health_port": health_port,
        "install_dir": install_dir,
        "exe": exe,
    }


def source_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_source = os.environ.get("CANRESEARCH_TUNNEL_CLIENT_SOURCE")
    if env_source:
        p = Path(os.path.expandvars(env_source)).expanduser()
        candidates.append(p / "tunnel-client.exe" if p.is_dir() else p)

    downloads = Path.home() / "Downloads"
    if downloads.exists():
        candidates.extend(downloads.glob("tunnel-client*/tunnel-client.exe"))
        candidates.extend(downloads.glob("tunnel-client.exe"))

    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{letter}:/Downloads")
        if root.exists():
            candidates.extend(root.glob("tunnel-client*/tunnel-client.exe"))
            candidates.extend(root.glob("tunnel-client.exe"))

    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def install() -> int:
    cfg = settings()
    target = Path(cfg["exe"])
    if target.exists():
        print(f"[OK] tunnel client already installed: {target}")
        return 0

    sources = [p for p in source_candidates() if p.exists() and p.is_file()]
    if not sources:
        print("[FAIL] OpenAI tunnel-client.exe was not found.")
        print(f"       Permanent install target: {target}")
        print("       Download/extract the OpenAI Windows AMD64 tunnel client, then either:")
        print("       1. rerun setup.cmd while it is still in a Downloads folder, or")
        print("       2. set CANRESEARCH_TUNNEL_CLIENT_SOURCE to the executable/folder and rerun setup.cmd.")
        return 2

    source = max(sources, key=lambda p: p.stat().st_mtime)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[OK] tunnel client installed: {target}")
    print(f"     migrated from: {source}")
    return 0


def tcp_open(host: str, port: int, timeout: float = 0.75) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def status() -> int:
    cfg = settings()
    exe = Path(cfg["exe"])
    host = str(cfg["health_host"])
    port = int(cfg["health_port"])
    profile = str(cfg["profile"])
    ok = True

    if exe.exists():
        print(f"[OK]   tunnel client: {exe}")
    else:
        print(f"[FAIL] tunnel client missing: {exe}")
        ok = False

    print(f"       profile: {profile}")
    print(f"       health:  {host}:{port}")

    if os.environ.get("CONTROL_PLANE_API_KEY"):
        print("[OK]   CONTROL_PLANE_API_KEY is present in this process environment")
    else:
        print("[WARN] CONTROL_PLANE_API_KEY is not present in this process environment")

    if tcp_open(host, port):
        print("[OK]   tunnel health listener is reachable")
    else:
        print("[FAIL] tunnel health listener is not reachable")
        ok = False

    return 0 if ok else 1


def emit_env() -> int:
    cfg = settings()
    print(f'set "TUNNEL_EXE={cfg["exe"]}"')
    print(f'set "TUNNEL_DIR={cfg["install_dir"]}"')
    print(f'set "TUNNEL_PROFILE={cfg["profile"]}"')
    print(f'set "TUNNEL_HEALTH_HOST={cfg["health_host"]}"')
    print(f'set "TUNNEL_HEALTH_PORT={cfg["health_port"]}"')
    return 0


def show() -> int:
    cfg = settings()
    for key in ("instance_key", "profile", "health_host", "health_port", "install_dir", "exe"):
        print(f"{key}: {cfg[key]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows OpenAI tunnel helper for CAN Research")
    parser.add_argument("command", choices=("install", "status", "env", "show"))
    args = parser.parse_args()
    return {"install": install, "status": status, "env": emit_env, "show": show}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
