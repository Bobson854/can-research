#!/usr/bin/env python3
"""Build a versioned Windows release ZIP for CAN Research.

Usage (from repository root):
    uv run python scripts/build_release.py
    uv run python scripts/build_release.py --output-dir dist/releases

Creates:
    dist/releases/CAN-Research-v<version>-windows.zip

The ZIP contains a top-level folder CAN-Research-v<version>/ with runtime files,
documentation, Skill source, and pre-built Skill packages under skills/dist/.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Authoritative version: pyproject.toml [project].version
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)

SKILL_DIRS = (
    "skills/can-onboarding",
    "skills/can-reference-builder",
    "skills/can-signal-research",
)

ROOT_FILES = (
    "README-FIRST.txt",
    "README.md",
    "LICENSE",
    "setup.cmd",
    "start-can-research.cmd",
    "status.cmd",
    "pyproject.toml",
    "uv.lock",
    "config.toml.example",
)

COPY_DIRS = (
    "src",
    "docs",
    "skills",
    "schemas",
    "config",
)

RELEASE_SCRIPT_FILES = (
    "mcp_verify_http.py",
    "package_skill.py",
)

# Paths that must never appear inside the release artifact.
FORBIDDEN_ZIP_FRAGMENTS = (
    "/.git/",
    "/.github/",
    "/.venv/",
    "/__pycache__/",
    "/.pytest_cache/",
    "/data/config.toml",
    "/docs/original_docs/",
    "/references/private/",
    "/tests/",
    "\\.git\\",
    "\\.venv\\",
    "\\__pycache__\\",
    "\\tests\\",
)

REQUIRED_ZIP_SUFFIXES = (
    "README-FIRST.txt",
    "setup.cmd",
    "start-can-research.cmd",
    "status.cmd",
    "pyproject.toml",
    "uv.lock",
    "config.toml.example",
    "docs/INSTALLATION.md",
    "docs/AI_INTEGRATION.md",
    "docs/SKILL_INSTALLATION.md",
    "docs/CANSUB_SETUP.md",
    "scripts/mcp_verify_http.py",
    "scripts/package_skill.py",
    "skills/dist/can-onboarding.skill.zip",
    "skills/dist/can-reference-builder.skill.zip",
    "skills/dist/can-signal-research.skill.zip",
)

SKIP_DIR_NAMES = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "tests",
    "dist",
    "build",
    "htmlcov",
    ".cursor",
    ".vscode",
    "original_docs",
    "private",
    "node_modules",
}

SKIP_FILE_NAMES = {
    "skill.zip",
    ".DS_Store",
    "Thumbs.db",
    "Desktop.ini",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_version(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if not match:
        raise ValueError("Could not read version from pyproject.toml [project].version")
    return match.group(1)


def release_folder_name(version: str) -> str:
    return f"CAN-Research-v{version}"


def release_zip_name(version: str) -> str:
    return f"CAN-Research-v{version}-windows.zip"


def _ignore_factory(root: Path):
    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        dir_path = Path(directory)
        for name in names:
            if name in SKIP_DIR_NAMES or name in SKIP_FILE_NAMES:
                ignored.add(name)
                continue
            if name.endswith((".pyc", ".pyo", ".log", ".stackdump")):
                ignored.add(name)
                continue
            full = dir_path / name
            try:
                rel = full.relative_to(root).as_posix()
            except ValueError:
                continue
            if rel.startswith("docs/original_docs"):
                ignored.add(name)
            if rel.startswith("references/private"):
                ignored.add(name)
            if rel.startswith("skills/") and name == "skill.zip":
                ignored.add(name)
        return ignored

    return _ignore


def _require_paths(root: Path) -> None:
    missing: list[str] = []
    for name in ROOT_FILES:
        if not (root / name).is_file():
            missing.append(name)
    for dirname in COPY_DIRS:
        if not (root / dirname).is_dir():
            missing.append(f"{dirname}/")
    scripts_dir = root / "scripts"
    for script_name in RELEASE_SCRIPT_FILES:
        if not (scripts_dir / script_name).is_file():
            missing.append(f"scripts/{script_name}")
    for skill in SKILL_DIRS:
        if not (root / skill / "SKILL.md").is_file():
            missing.append(f"{skill}/SKILL.md")
        if not (root / skill / "agents" / "openai.yaml").is_file():
            missing.append(f"{skill}/agents/openai.yaml")
    if missing:
        raise FileNotFoundError(
            "Release build missing required inputs:\n  - " + "\n  - ".join(missing)
        )


def package_skills(root: Path, staging: Path) -> None:
    """Build Skill ZIPs into staging/skills/dist/."""
    dist_dir = staging / "skills" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    for skill_rel in SKILL_DIRS:
        skill_dir = root / skill_rel
        subprocess.run(
            [sys.executable, str(root / "scripts" / "package_skill.py"), str(skill_dir)],
            cwd=root,
            check=True,
        )
        built = skill_dir / "skill.zip"
        if not built.is_file():
            raise FileNotFoundError(f"Skill packaging did not produce {built}")
        skill_name = skill_dir.name
        dest = dist_dir / f"{skill_name}.skill.zip"
        shutil.copy2(built, dest)
        # Remove transient build artifact from staging if copied into tree later
        print(f"Skill package: {dest.relative_to(staging)} ({dest.stat().st_size:,} bytes)")


def stage_release(root: Path, staging: Path) -> None:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for name in ROOT_FILES:
        shutil.copy2(root / name, staging / name)

    ignore = _ignore_factory(root)
    for dirname in COPY_DIRS:
        src = root / dirname
        dest = staging / dirname
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=ignore)

    scripts_dest = staging / "scripts"
    scripts_dest.mkdir(parents=True)
    for script_name in RELEASE_SCRIPT_FILES:
        shutil.copy2(root / "scripts" / script_name, scripts_dest / script_name)

    package_skills(root, staging)


def create_zip(staging: Path, zip_path: Path, top_folder: str) -> None:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_dir():
                continue
            arcname = Path(top_folder) / path.relative_to(staging)
            zf.write(path, arcname.as_posix())

    bad = zipfile.ZipFile(zip_path).testzip()
    if bad is not None:
        raise ValueError(f"Release ZIP integrity check failed at {bad}")


def validate_release_zip(zip_path: Path, version: str) -> None:
    top = release_folder_name(version)
    names = zipfile.ZipFile(zip_path).namelist()

    if not any(n.startswith(f"{top}/") for n in names):
        raise ValueError(f"ZIP missing top-level folder {top}/")

    normalized = [n.replace("\\", "/") for n in names]
    for fragment in FORBIDDEN_ZIP_FRAGMENTS:
        frag = fragment.replace("\\", "/")
        if any(frag in n for n in normalized):
            raise ValueError(f"Forbidden path fragment in release ZIP: {fragment}")

    for suffix in REQUIRED_ZIP_SUFFIXES:
        expected = f"{top}/{suffix}"
        if expected not in normalized:
            raise ValueError(f"Release ZIP missing required path: {expected}")

    for skill in ("can-onboarding", "can-reference-builder", "can-signal-research"):
        prefix = f"{top}/skills/dist/{skill}.skill.zip"
        if prefix not in normalized:
            raise ValueError(f"Missing skill package: {prefix}")
        # Validate skill zip internal structure
        with zipfile.ZipFile(zip_path) as outer:
            inner_bytes = outer.read(prefix)
        import io

        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
            inner_bad = inner.testzip()
            if inner_bad is not None:
                raise ValueError(f"Skill ZIP corrupt ({skill}): {inner_bad}")
            inner_names = inner.namelist()
            if f"{skill}/SKILL.md" not in inner_names:
                raise ValueError(f"Skill ZIP missing SKILL.md: {skill}")
            if f"{skill}/agents/openai.yaml" not in inner_names:
                raise ValueError(f"Skill ZIP missing agents/openai.yaml: {skill}")

    print(f"Release validation OK ({len(names)} entries)")


def build_release(*, output_dir: Path | None = None, keep_staging: bool = False) -> Path:
    root = repo_root()
    _require_paths(root)
    version = read_version(root)
    top_folder = release_folder_name(version)
    out_dir = output_dir or (root / "dist" / "releases")
    out_dir.mkdir(parents=True, exist_ok=True)

    staging = root / "dist" / "release-staging" / top_folder
    zip_path = out_dir / release_zip_name(version)

    print(f"Building CAN Research release v{version}")
    print(f"Staging: {staging}")
    stage_release(root, staging)
    create_zip(staging, zip_path, top_folder)
    validate_release_zip(zip_path, version)

    if not keep_staging:
        shutil.rmtree(staging.parent, ignore_errors=True)

    size = zip_path.stat().st_size
    print(f"Artifact: {zip_path}")
    print(f"Size:     {size:,} bytes")
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for the ZIP (default: dist/releases)",
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Keep dist/release-staging for inspection",
    )
    args = parser.parse_args()
    try:
        build_release(output_dir=args.output_dir, keep_staging=args.keep_staging)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
