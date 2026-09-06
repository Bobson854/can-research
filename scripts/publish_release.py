#!/usr/bin/env python3
"""Release publish helpers — version bump, validation, artifact naming.

Used by scripts/publish-release.ps1 and tests. Does not run Git or push tags.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

PROJECT_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$')


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def validate_semver(version: str) -> None:
    if not SEMVER_PATTERN.fullmatch(version.strip()):
        raise ValueError(f"Invalid semantic version: {version!r} (expected X.Y.Z)")


def tag_for_version(version: str) -> str:
    validate_semver(version)
    return f"v{version}"


def version_from_tag(tag: str) -> str:
    tag = tag.strip()
    if not tag.startswith("v"):
        raise ValueError(f"Tag must start with 'v': {tag!r}")
    version = tag[1:]
    validate_semver(version)
    return version


def tag_matches_version(tag: str, version: str) -> bool:
    try:
        return tag_for_version(version) == tag.strip()
    except ValueError:
        return False


def read_project_version(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_project:
            match = PROJECT_VERSION_LINE.match(line)
            if match:
                return match.group(1)
    raise ValueError(f"Could not read [project].version from {pyproject_path}")


def set_project_version(pyproject_path: Path, new_version: str) -> str:
    """Return updated pyproject.toml text with only [project].version changed."""
    validate_semver(new_version)
    text = pyproject_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_project = False
    replaced = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_project:
            match = PROJECT_VERSION_LINE.match(line.rstrip("\r\n"))
            if match:
                newline = "\n" if line.endswith("\n") else ""
                lines[index] = f'version = "{new_version}"{newline}'
                replaced = True
                break
    if not replaced:
        raise ValueError(f"Could not find [project].version in {pyproject_path}")
    return "".join(lines)


def write_project_version(pyproject_path: Path, new_version: str) -> None:
    pyproject_path.write_text(set_project_version(pyproject_path, new_version), encoding="utf-8")


def release_zip_name(version: str) -> str:
    validate_semver(version)
    return f"CAN-Research-v{version}-windows.zip"


def release_artifact_path(root: Path, version: str, output_dir: Path | None = None) -> Path:
    out = output_dir or (root / "dist" / "releases")
    return out / release_zip_name(version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    bump = sub.add_parser("bump-version", help="Update [project].version in pyproject.toml")
    bump.add_argument("--version", required=True)
    bump.add_argument(
        "--pyproject",
        type=Path,
        default=None,
        help="Path to pyproject.toml (default: repository root)",
    )

    sub.add_parser("read-version", help="Print [project].version")

    artifact = sub.add_parser("artifact-path", help="Print expected release ZIP path")
    artifact.add_argument("--version", required=True)
    artifact.add_argument("--output-dir", type=Path, default=None)

    validate = sub.add_parser("validate-version", help="Validate semver and exit 0/1")
    validate.add_argument("--version", required=True)

    tag_cmd = sub.add_parser("tag-for-version", help="Print Git tag for a version")
    tag_cmd.add_argument("--version", required=True)

    args = parser.parse_args()
    root = repo_root()
    pyproject = (args.pyproject if hasattr(args, "pyproject") and args.pyproject else root / "pyproject.toml")

    try:
        if args.command == "bump-version":
            current = read_project_version(pyproject)
            if current == args.version:
                print(f"ERROR: version is already {current}", file=sys.stderr)
                return 1
            write_project_version(pyproject, args.version)
            print(f"Updated {pyproject.name}: {current} -> {args.version}")
            return 0
        if args.command == "read-version":
            print(read_project_version(pyproject))
            return 0
        if args.command == "artifact-path":
            print(release_artifact_path(root, args.version, args.output_dir))
            return 0
        if args.command == "validate-version":
            validate_semver(args.version)
            return 0
        if args.command == "tag-for-version":
            print(tag_for_version(args.version))
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
