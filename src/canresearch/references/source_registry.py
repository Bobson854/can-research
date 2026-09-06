"""File-backed registry for original reference source documents."""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from canresearch.config import resolve_data_dir

SOURCE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

VALID_REFERENCE_SOURCE_TYPES: frozenset[str] = frozenset(
    {"standard", "oem", "supplier", "user_dbc", "user_document", "research", "other"}
)
VALID_REFERENCE_VISIBILITY: frozenset[str] = frozenset({"public", "private", "licensed"})


class ReferenceSourceRegistryError(Exception):
    """Reference source registry operation failed."""


class ReferenceSourceNotFoundError(ReferenceSourceRegistryError):
    """Requested reference source key does not exist."""


@dataclass(frozen=True, slots=True)
class ReferenceSourceRecord:
    key: str
    display_name: str
    source_type: str
    visibility: str
    original_filename: str
    stored_path: str
    vendor: str | None = None
    version: str | None = None
    document_date: str | None = None
    notes: str | None = None
    registered_at: str = ""


def reference_sources_root(data_dir: Path | None = None) -> Path:
    root = resolve_data_dir() if data_dir is None else Path(data_dir)
    return root / "reference_sources"


def manifest_path(data_dir: Path | None = None) -> Path:
    return reference_sources_root(data_dir) / "manifest.toml"


def _validate_key(key: str) -> str:
    cleaned = key.strip()
    if not cleaned or not SOURCE_KEY_PATTERN.fullmatch(cleaned):
        msg = "source key must start with letter/digit and use [A-Za-z0-9_-] only"
        raise ReferenceSourceRegistryError(msg)
    return cleaned


def _validate_source_type(source_type: str) -> str:
    cleaned = source_type.strip()
    if cleaned not in VALID_REFERENCE_SOURCE_TYPES:
        expected = ", ".join(sorted(VALID_REFERENCE_SOURCE_TYPES))
        msg = f"invalid source_type {cleaned!r}; expected one of: {expected}"
        raise ReferenceSourceRegistryError(msg)
    return cleaned


def _validate_visibility(visibility: str) -> str:
    cleaned = visibility.strip()
    if cleaned not in VALID_REFERENCE_VISIBILITY:
        expected = ", ".join(sorted(VALID_REFERENCE_VISIBILITY))
        msg = f"invalid visibility {cleaned!r}; expected one of: {expected}"
        raise ReferenceSourceRegistryError(msg)
    return cleaned


def _visibility_dir(visibility: str) -> str:
    if visibility == "public":
        return "public"
    return "private"


def _resolve_stored_path(path_text: str, *, root: Path) -> Path:
    raw = Path(path_text)
    resolved = raw if raw.is_absolute() else (root / raw)
    resolved = resolved.resolve()
    root_resolved = root.resolve()
    if not resolved.is_file():
        msg = f"Reference source file not found: {resolved}"
        raise ReferenceSourceRegistryError(msg)
    for subdir in ("public", "private"):
        try:
            resolved.relative_to((root_resolved / subdir).resolve())
            return resolved
        except ValueError:
            continue
    msg = f"Reference source path must be under {root_resolved / 'public'} or private: {resolved}"
    raise ReferenceSourceRegistryError(msg)


def load_manifest_entries(data_dir: Path | None = None) -> tuple[ReferenceSourceRecord, ...]:
    path = manifest_path(data_dir)
    if not path.exists():
        return ()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    sources = raw.get("sources", [])
    if sources is None:
        return ()
    if not isinstance(sources, list):
        msg = f"Invalid manifest {path}: sources must be a table array"
        raise ReferenceSourceRegistryError(msg)
    entries: list[ReferenceSourceRecord] = []
    for item in sources:
        if not isinstance(item, dict):
            msg = f"Invalid manifest {path}: each source must be a table"
            raise ReferenceSourceRegistryError(msg)
        key = _validate_key(str(item.get("key", "")))
        entries.append(
            ReferenceSourceRecord(
                key=key,
                display_name=str(item.get("display_name", key)),
                source_type=str(item.get("source_type", "other")),
                visibility=str(item.get("visibility", "private")),
                original_filename=str(item.get("original_filename", "")),
                stored_path=str(item.get("stored_path", "")),
                vendor=item.get("vendor"),
                version=item.get("version"),
                document_date=item.get("document_date"),
                notes=item.get("notes"),
                registered_at=str(item.get("registered_at", "")),
            )
        )
    return tuple(entries)


def save_manifest_entries(
    entries: tuple[ReferenceSourceRecord, ...],
    data_dir: Path | None = None,
) -> Path:
    path = manifest_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        path.write_text("version = 1\n\n", encoding="utf-8")
        return path
    blocks: list[str] = ["version = 1", ""]
    for entry in entries:
        blocks.append("[[sources]]")
        blocks.append(f'key = "{entry.key}"')
        blocks.append(f'display_name = "{entry.display_name}"')
        blocks.append(f'source_type = "{entry.source_type}"')
        blocks.append(f'visibility = "{entry.visibility}"')
        blocks.append(f'original_filename = "{entry.original_filename}"')
        blocks.append(f'stored_path = "{entry.stored_path}"')
        if entry.vendor:
            blocks.append(f'vendor = "{entry.vendor}"')
        if entry.version:
            blocks.append(f'version = "{entry.version}"')
        if entry.document_date:
            blocks.append(f'document_date = "{entry.document_date}"')
        if entry.notes:
            escaped = entry.notes.replace('"', '\\"')
            blocks.append(f'notes = "{escaped}"')
        blocks.append(f'registered_at = "{entry.registered_at}"')
        blocks.append("")
    path.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    return path


def register_reference_source(
    *,
    key: str,
    path: Path,
    display_name: str | None = None,
    source_type: str = "user_document",
    visibility: str = "private",
    vendor: str | None = None,
    version: str | None = None,
    document_date: str | None = None,
    notes: str | None = None,
    data_dir: Path | None = None,
) -> ReferenceSourceRecord:
    """Copy a source file into the managed area and register it."""
    validated_key = _validate_key(key)
    validated_type = _validate_source_type(source_type)
    validated_visibility = _validate_visibility(visibility)
    if not path.is_file():
        msg = f"Source file not found: {path}"
        raise ReferenceSourceRegistryError(msg)

    root = reference_sources_root(data_dir)
    subdir = root / _visibility_dir(validated_visibility)
    subdir.mkdir(parents=True, exist_ok=True)

    original_filename = path.name
    dest = subdir / f"{validated_key}{path.suffix.lower()}"
    shutil.copy2(path, dest)

    stored_rel = dest.relative_to(root).as_posix()
    registered_at = datetime.now(tz=UTC).isoformat()
    record = ReferenceSourceRecord(
        key=validated_key,
        display_name=display_name or original_filename,
        source_type=validated_type,
        visibility=validated_visibility,
        original_filename=original_filename,
        stored_path=stored_rel,
        vendor=vendor,
        version=version,
        document_date=document_date,
        notes=notes,
        registered_at=registered_at,
    )

    existing = {entry.key: entry for entry in load_manifest_entries(data_dir)}
    existing[validated_key] = record
    save_manifest_entries(tuple(existing.values()), data_dir)
    return record


def get_reference_source(key: str, data_dir: Path | None = None) -> ReferenceSourceRecord:
    for entry in load_manifest_entries(data_dir):
        if entry.key == key:
            return entry
    msg = f"Reference source not found: {key}"
    raise ReferenceSourceNotFoundError(msg)


def list_reference_sources(
    data_dir: Path | None = None,
) -> tuple[ReferenceSourceRecord, ...]:
    return load_manifest_entries(data_dir)


def source_file_path(record: ReferenceSourceRecord, data_dir: Path | None = None) -> Path:
    root = reference_sources_root(data_dir)
    return _resolve_stored_path(record.stored_path, root=root)


def source_exists(key: str, data_dir: Path | None = None) -> bool:
    try:
        get_reference_source(key, data_dir=data_dir)
    except ReferenceSourceNotFoundError:
        return False
    return True
