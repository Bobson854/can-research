"""File-backed DBC source registry and bounded discovery."""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from canresearch.config import resolve_data_dir
from canresearch.core.assets import default_dbc_filename
from canresearch.core.dbc_knowledge import (
    VALID_DBC_SOURCE_TYPES,
    DbcKnowledgeError,
    DbcSourceMeta,
    DbcSourceNotFoundError,
    LoadedDbcSource,
)
from canresearch.core.dbc_reader import read_dbc_file

SOURCE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class DbcRegistryEntry:
    key: str
    display_name: str
    path: str
    source_type: str
    asset_key: str | None = None


class DbcRegistryError(DbcKnowledgeError):
    """Registry configuration error."""


def dbc_root(data_dir: Path | None = None) -> Path:
    root = resolve_data_dir() if data_dir is None else Path(data_dir)
    return root / "dbc"


def manifest_path(data_dir: Path | None = None) -> Path:
    return dbc_root(data_dir) / "manifest.toml"


def _validate_source_key(key: str) -> str:
    cleaned = key.strip()
    if not cleaned or not SOURCE_KEY_PATTERN.fullmatch(cleaned):
        msg = "source key must start with letter/digit and use [A-Za-z0-9_-] only"
        raise DbcRegistryError(msg)
    return cleaned


def _validate_source_type(source_type: str) -> str:
    cleaned = source_type.strip()
    if cleaned not in VALID_DBC_SOURCE_TYPES:
        msg = f"invalid source_type {cleaned!r}; expected one of {sorted(VALID_DBC_SOURCE_TYPES)}"
        raise DbcRegistryError(msg)
    return cleaned


def _resolve_registered_path(path_text: str, *, root: Path) -> Path:
    raw = Path(path_text)
    resolved = raw if raw.is_absolute() else (root / raw)
    resolved = resolved.resolve()
    root_resolved = root.resolve()
    if not resolved.is_file():
        msg = f"DBC file not found: {resolved}"
        raise DbcRegistryError(msg)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        library = root_resolved / "library"
        library.mkdir(parents=True, exist_ok=True)
        try:
            resolved.relative_to(library.resolve())
        except ValueError as exc:
            msg = f"DBC path must be under {root_resolved} or {library}: {resolved}"
            raise DbcRegistryError(msg) from exc
    return resolved


def load_manifest_entries(data_dir: Path | None = None) -> tuple[DbcRegistryEntry, ...]:
    path = manifest_path(data_dir)
    if not path.exists():
        return ()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    sources = raw.get("sources", [])
    if sources is None:
        return ()
    if not isinstance(sources, list):
        msg = f"Invalid manifest {path}: sources must be a table array"
        raise DbcRegistryError(msg)
    entries: list[DbcRegistryEntry] = []
    for item in sources:
        if not isinstance(item, dict):
            msg = f"Invalid manifest {path}: each source must be a table"
            raise DbcRegistryError(msg)
        key = _validate_source_key(str(item.get("key", "")))
        path_text = str(item.get("path", "")).strip()
        if not path_text:
            msg = f"Manifest source {key} missing path"
            raise DbcRegistryError(msg)
        display_name = str(item.get("display_name", key)).strip() or key
        source_type = _validate_source_type(str(item.get("source_type", "user_supplied")))
        asset_key_raw = item.get("asset_key")
        asset_key = str(asset_key_raw).strip() if asset_key_raw else None
        entries.append(
            DbcRegistryEntry(
                key=key,
                display_name=display_name,
                path=path_text,
                source_type=source_type,
                asset_key=asset_key or None,
            )
        )
    return tuple(entries)


def save_manifest_entries(
    entries: tuple[DbcRegistryEntry, ...],
    data_dir: Path | None = None,
) -> Path:
    path = manifest_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CAN Research DBC knowledge sources", ""]
    for entry in entries:
        lines.extend(
            [
                "[[sources]]",
                f'key = "{entry.key}"',
                f'path = "{entry.path.replace(chr(92), "/")}"',
                f'display_name = "{entry.display_name}"',
                f'source_type = "{entry.source_type}"',
            ]
        )
        if entry.asset_key:
            lines.append(f'asset_key = "{entry.asset_key}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def register_dbc_source(
    *,
    key: str,
    path: Path,
    display_name: str | None = None,
    source_type: str = "user_supplied",
    asset_key: str | None = None,
    data_dir: Path | None = None,
) -> DbcRegistryEntry:
    """Register or replace a DBC source in the manifest."""
    cleaned_key = _validate_source_key(key)
    cleaned_type = _validate_source_type(source_type)
    root = dbc_root(data_dir)
    library = root / "library"
    library.mkdir(parents=True, exist_ok=True)
    source_path = path.resolve()
    if not source_path.is_file():
        msg = f"DBC file not found: {source_path}"
        raise DbcRegistryError(msg)
    dest = library / f"{cleaned_key}.dbc"
    if source_path != dest.resolve():
        shutil.copy2(source_path, dest)
    path_text = f"library/{cleaned_key}.dbc"
    entry = DbcRegistryEntry(
        key=cleaned_key,
        display_name=(display_name or cleaned_key).strip() or cleaned_key,
        path=path_text,
        source_type=cleaned_type,
        asset_key=asset_key,
    )
    existing = [item for item in load_manifest_entries(data_dir) if item.key != cleaned_key]
    save_manifest_entries((*existing, entry), data_dir)
    return entry


def _asset_dbc_entries(asset_key: str, *, cwd: Path | None = None) -> tuple[DbcRegistryEntry, ...]:
    base = cwd or Path.cwd()
    entries: list[DbcRegistryEntry] = []
    for dbc_type, source_type in (("standard", "standard"), ("research", "confirmed_research")):
        filename = default_dbc_filename(asset_key, dbc_type)
        path = base / filename
        if path.is_file():
            entries.append(
                DbcRegistryEntry(
                    key=f"asset_{asset_key}_{dbc_type}",
                    display_name=f"{asset_key} {dbc_type} DBC",
                    path=str(path.resolve()),
                    source_type=source_type,
                    asset_key=asset_key,
                )
            )
    return tuple(entries)


def list_dbc_source_meta(
    *,
    asset_key: str | None = None,
    data_dir: Path | None = None,
    cwd: Path | None = None,
) -> tuple[DbcSourceMeta, ...]:
    """List registered and optional asset-scoped DBC sources (metadata only)."""
    root = dbc_root(data_dir)
    metas: list[DbcSourceMeta] = []
    for entry in load_manifest_entries(data_dir):
        try:
            resolved = _resolve_registered_path(entry.path, root=root)
        except DbcRegistryError:
            continue
        metas.append(
            DbcSourceMeta(
                key=entry.key,
                display_name=entry.display_name,
                path=str(resolved),
                source_type=entry.source_type,
                asset_key=entry.asset_key,
            )
        )
    if asset_key:
        for entry in _asset_dbc_entries(asset_key, cwd=cwd):
            path = Path(entry.path)
            if path.is_file():
                metas.append(
                    DbcSourceMeta(
                        key=entry.key,
                        display_name=entry.display_name,
                        path=str(path.resolve()),
                        source_type=entry.source_type,
                        asset_key=entry.asset_key,
                    )
                )
    return tuple(metas)


def load_dbc_source(
    source_key: str,
    *,
    data_dir: Path | None = None,
    cwd: Path | None = None,
) -> LoadedDbcSource:
    """Load one registered or asset-scoped DBC source by key."""
    for meta in list_dbc_source_meta(data_dir=data_dir, cwd=cwd):
        if meta.key != source_key:
            continue
        path = Path(meta.path)
        database, warnings = read_dbc_file(path)
        message_count = len(database.messages)
        signal_count = sum(len(message.signals) for message in database.messages)
        enriched = DbcSourceMeta(
            key=meta.key,
            display_name=meta.display_name,
            path=meta.path,
            source_type=meta.source_type,
            asset_key=meta.asset_key,
            message_count=message_count,
            signal_count=signal_count,
        )
        return LoadedDbcSource(meta=enriched, database=database, warnings=warnings)
    msg = f"DBC source not found: {source_key}"
    raise DbcSourceNotFoundError(msg)


def load_dbc_sources(
    *,
    source_keys: tuple[str, ...] | None = None,
    asset_key: str | None = None,
    data_dir: Path | None = None,
    cwd: Path | None = None,
) -> tuple[LoadedDbcSource, ...]:
    """Load multiple DBC sources. Empty source_keys loads all registered (+ asset if given)."""
    metas = list_dbc_source_meta(asset_key=asset_key, data_dir=data_dir, cwd=cwd)
    if source_keys:
        allowed = set(source_keys)
        metas = [meta for meta in metas if meta.key in allowed]
        missing = allowed - {meta.key for meta in metas}
        if missing:
            msg = f"DBC source(s) not found: {', '.join(sorted(missing))}"
            raise DbcSourceNotFoundError(msg)
    loaded: list[LoadedDbcSource] = []
    for meta in metas:
        loaded.append(load_dbc_source(meta.key, data_dir=data_dir, cwd=cwd))
    return tuple(loaded)


def inspect_dbc_source(
    source_key: str,
    *,
    data_dir: Path | None = None,
    cwd: Path | None = None,
) -> LoadedDbcSource:
    """Load and return full inspection payload for one source."""
    return load_dbc_source(source_key, data_dir=data_dir, cwd=cwd)
