"""Release ZIP build validation tests."""

from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT / "scripts" / "build_release.py"


@pytest.fixture(scope="module")
def release_zip(tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("releases")
    subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--output-dir", str(out_dir)],
        cwd=ROOT,
        check=True,
    )
    zips = list(out_dir.glob("CAN-Research-v*-windows.zip"))
    assert len(zips) == 1
    return zips[0]


def test_release_zip_opens(release_zip: Path) -> None:
    with zipfile.ZipFile(release_zip) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
    assert any(n.endswith("README-FIRST.txt") for n in names)
    assert not any("tests/" in n.replace("\\", "/") for n in names)
    assert not any("docs/original_docs/" in n.replace("\\", "/") for n in names)


def test_release_includes_skill_packages(release_zip: Path) -> None:
    with zipfile.ZipFile(release_zip) as zf:
        names = [n.replace("\\", "/") for n in zf.namelist()]
    for skill in ("can-onboarding", "can-reference-builder", "can-signal-research"):
        path = next(n for n in names if n.endswith(f"skills/dist/{skill}.skill.zip"))
        with zipfile.ZipFile(release_zip) as outer:
            inner = zipfile.ZipFile(io.BytesIO(outer.read(path)))
            assert f"{skill}/SKILL.md" in inner.namelist()


def test_release_includes_runtime_scripts(release_zip: Path) -> None:
    """setup.cmd and start-can-research.cmd require these scripts in the ZIP."""
    required = (
        "scripts/mcp_verify_http.py",
        "scripts/package_skill.py",
        "scripts/tunnel_windows.py",
    )
    with zipfile.ZipFile(release_zip) as zf:
        names = [n.replace("\\", "/") for n in zf.namelist()]
        for suffix in required:
            matches = [n for n in names if n.endswith(suffix)]
            assert len(matches) == 1, f"expected one {suffix}, found {matches}"
            assert zf.getinfo(matches[0]).file_size > 0
