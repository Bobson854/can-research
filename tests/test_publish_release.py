"""Tests for release publish helper logic (no Git or remote operations)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PUBLISH_SCRIPT = ROOT / "scripts" / "publish_release.py"

sys.path.insert(0, str(ROOT / "scripts"))
import publish_release as pr  # noqa: E402


@pytest.mark.parametrize(
    ("version", "valid"),
    [
        ("0.1.0", True),
        ("1.2.3", True),
        ("0.0.0", True),
        ("1.0", False),
        ("v1.0.0", False),
        ("1.0.0-beta", True),
        ("not-a-version", False),
    ],
)
def test_validate_semver(version: str, valid: bool) -> None:
    if valid:
        pr.validate_semver(version)
    else:
        with pytest.raises(ValueError):
            pr.validate_semver(version)


def test_tag_version_agreement() -> None:
    assert pr.tag_for_version("0.1.1") == "v0.1.1"
    assert pr.version_from_tag("v0.1.1") == "0.1.1"
    assert pr.tag_matches_version("v0.1.1", "0.1.1")
    assert not pr.tag_matches_version("v0.1.0", "0.1.1")


def test_release_artifact_naming() -> None:
    assert pr.release_zip_name("0.1.1") == "CAN-Research-v0.1.1-windows.zip"
    path = pr.release_artifact_path(ROOT, "0.1.1")
    assert path == ROOT / "dist" / "releases" / "CAN-Research-v0.1.1-windows.zip"


def test_set_project_version_preserves_unrelated_toml(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\n'
        'name = "can-research"\n'
        'version = "0.1.0"\n'
        'description = "keep me"\n'
        '\n'
        '[tool.ruff]\n'
        'line-length = 100\n',
        encoding="utf-8",
    )
    updated = pr.set_project_version(pyproject, "0.2.0")
    assert 'version = "0.2.0"' in updated
    assert 'version = "0.1.0"' not in updated
    assert 'name = "can-research"' in updated
    assert "line-length = 100" in updated
    assert updated.count('version = ') == 1


def test_bump_version_cli(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(PUBLISH_SCRIPT),
            "bump-version",
            "--version",
            "0.1.1",
            "--pyproject",
            str(pyproject),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "0.1.0 -> 0.1.1" in result.stdout
    assert pr.read_project_version(pyproject) == "0.1.1"


def test_bump_version_rejects_same_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(PUBLISH_SCRIPT),
            "bump-version",
            "--version",
            "0.1.0",
            "--pyproject",
            str(pyproject),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "already" in result.stderr.lower()


def test_dry_run_script_includes_guarded_git_steps() -> None:
    publish_ps1 = ROOT / "scripts" / "publish-release.ps1"
    assert publish_ps1.is_file()
    text = publish_ps1.read_text(encoding="utf-8")
    assert "$DryRun" in text
    assert "git push origin" in text
    assert "build-release.ps1" in text
    assert "DRY RUN" in text


def test_tag_for_version_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), "tag-for-version", "--version", "0.1.2"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "v0.1.2"
