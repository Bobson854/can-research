#!/usr/bin/env python3
"""Build a ChatGPT skill.zip from canonical repo source.

Usage from repo root:
    uv run python scripts/package_skill.py skills/can-onboarding
    uv run python scripts/package_skill.py skills/can-reference-builder skills/can-signal-research

The generated skill.zip is intentionally local-only/gitignored. The repository stores
Skill source, not deployment ZIP binaries.
"""

from __future__ import annotations

import hashlib
import re
import sys
import zipfile
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
SKIP_NAMES = {"skill.zip", "__pycache__"}


def validate_skill_source(skill_dir: Path) -> str:
    if not skill_dir.is_dir():
        raise ValueError(f"Skill directory not found: {skill_dir}")

    skill_md = skill_dir / "SKILL.md"
    agent_yaml = skill_dir / "agents" / "openai.yaml"
    if not skill_md.is_file():
        raise ValueError(f"Missing SKILL.md: {skill_md}")
    if not agent_yaml.is_file():
        raise ValueError(f"Missing agents/openai.yaml: {agent_yaml}")

    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must begin with YAML frontmatter")

    frontmatter = match.group(1)
    name_match = re.search(r"(?m)^name:\s*([^\n]+?)\s*$", frontmatter)
    desc_match = re.search(r"(?m)^description:\s*(?:>|>-|\||\|-)?\s*(.*)$", frontmatter)
    if not name_match:
        raise ValueError("SKILL.md frontmatter is missing name")
    if not desc_match:
        raise ValueError("SKILL.md frontmatter is missing description")

    name = name_match.group(1).strip().strip('"\'')
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError(f"Invalid Skill name: {name!r}")
    if skill_dir.name != name:
        raise ValueError(
            f"Skill directory name {skill_dir.name!r} must match frontmatter name {name!r}"
        )
    return name


def should_include(path: Path, skill_dir: Path) -> bool:
    rel = path.relative_to(skill_dir)
    if path.name in SKIP_NAMES:
        return False
    if any(part.startswith(".") for part in rel.parts):
        return False
    if any(part == "__pycache__" for part in rel.parts):
        return False
    return path.is_file()


def build_skill(skill_arg: str) -> Path:
    skill_dir = Path(skill_arg).resolve()
    name = validate_skill_source(skill_dir)
    output = skill_dir / "skill.zip"

    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if not should_include(path, skill_dir):
                continue
            arcname = Path(name) / path.relative_to(skill_dir)
            zf.write(path, arcname.as_posix())

    with zipfile.ZipFile(output, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            output.unlink(missing_ok=True)
            raise ValueError(f"ZIP integrity check failed at {bad}")
        names = zf.namelist()
        required = {f"{name}/SKILL.md", f"{name}/agents/openai.yaml"}
        missing = required.difference(names)
        if missing:
            output.unlink(missing_ok=True)
            raise ValueError(f"ZIP missing required files: {sorted(missing)}")
        if any(not member.startswith(f"{name}/") for member in names):
            output.unlink(missing_ok=True)
            raise ValueError("ZIP contains entries outside the Skill root folder")

    size = output.stat().st_size
    if size > MAX_BYTES:
        output.unlink(missing_ok=True)
        raise ValueError(f"ZIP exceeds 25 MiB upload limit: {size:,} bytes")

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Built: {output}")
    print(f"Size:  {size:,} bytes")
    print(f"SHA256: {digest}")
    print("ZIP integrity: OK")
    return output


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/package_skill.py <skill-dir> [<skill-dir> ...]")
        return 2

    try:
        for arg in sys.argv[1:]:
            build_skill(arg)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
