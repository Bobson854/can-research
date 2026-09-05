"""Tests for asset registry and session associations."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from canresearch.cli import main
from canresearch.core.assets import (
    add_asset,
    get_asset_by_key,
    link_session_asset,
    list_assets,
    list_session_assets,
    unlink_session_asset,
)
from canresearch.core.sessions import create_session, session_frames_path
from canresearch.storage.database import initialize


@pytest.fixture
def asset_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.assets.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    initialize(db_path)
    return {"db_path": db_path}


def _create_session(db_path: Path, session_id: str = "sess01") -> str:
    frames_path = session_frames_path(session_id)
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    frames_path.write_text("", encoding="utf-8")
    create_session(
        name="asset-test",
        host="127.0.0.1",
        channel=1,
        device_id=None,
        frame_store_path=str(frames_path),
        db_path=db_path,
        session_id=session_id,
    )
    return session_id


def test_add_and_show_asset(asset_env) -> None:
    record = add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="John Deere 6155R Workshop Tractor",
        manufacturer="John Deere",
        model="6155R",
        db_path=asset_env["db_path"],
    )
    assert record.asset_key == "jd_6155r_01"
    assert record.asset_type == "tractor"
    assert record.manufacturer == "John Deere"

    fetched = get_asset_by_key("jd_6155r_01", db_path=asset_env["db_path"])
    assert fetched.display_name == record.display_name


def test_asset_key_must_be_unique(asset_env) -> None:
    add_asset(
        asset_key="edge101_bench_01",
        asset_type="controller",
        display_name="EDGE101 Controller 1",
        db_path=asset_env["db_path"],
    )
    with pytest.raises(ValueError, match="already exists"):
        add_asset(
            asset_key="edge101_bench_01",
            asset_type="controller",
            display_name="Duplicate",
            db_path=asset_env["db_path"],
        )


def test_invalid_asset_type(asset_env) -> None:
    with pytest.raises(ValueError, match="Invalid asset type"):
        add_asset(
            asset_key="bad_type",
            asset_type="combine",
            display_name="Bad",
            db_path=asset_env["db_path"],
        )


def test_invalid_asset_key(asset_env) -> None:
    with pytest.raises(ValueError, match="lowercase"):
        add_asset(
            asset_key="Bad-Key",
            asset_type="other",
            display_name="Bad",
            db_path=asset_env["db_path"],
        )


def test_list_assets(asset_env) -> None:
    add_asset(
        asset_key="weedit_quadro_01",
        asset_type="implement",
        display_name="WEED-IT Quadro Unit 1",
        db_path=asset_env["db_path"],
    )
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="John Deere 6155R Workshop Tractor",
        db_path=asset_env["db_path"],
    )
    keys = [item.asset_key for item in list_assets(db_path=asset_env["db_path"])]
    assert keys == ["jd_6155r_01", "weedit_quadro_01"]


def test_link_tractor_and_implement(asset_env) -> None:
    session_id = _create_session(asset_env["db_path"], "abc123")
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="John Deere 6155R Workshop Tractor",
        db_path=asset_env["db_path"],
    )
    add_asset(
        asset_key="weedit_quadro_01",
        asset_type="implement",
        display_name="WEED-IT Quadro Unit 1",
        db_path=asset_env["db_path"],
    )
    link_session_asset(
        session_id,
        "jd_6155r_01",
        role="tractor",
        db_path=asset_env["db_path"],
    )
    link_session_asset(
        session_id,
        "weedit_quadro_01",
        role="implement",
        db_path=asset_env["db_path"],
    )

    linked = list_session_assets(session_id, db_path=asset_env["db_path"])
    assert len(linked) == 2
    roles = {item.asset_key: item.role for item in linked}
    assert roles == {
        "jd_6155r_01": "tractor",
        "weedit_quadro_01": "implement",
    }


def test_duplicate_session_link_rejected(asset_env) -> None:
    session_id = _create_session(asset_env["db_path"])
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="Tractor",
        db_path=asset_env["db_path"],
    )
    link_session_asset(session_id, "jd_6155r_01", role="tractor", db_path=asset_env["db_path"])
    with pytest.raises(ValueError, match="already linked"):
        link_session_asset(session_id, "jd_6155r_01", role="tractor", db_path=asset_env["db_path"])


def test_unlink_session_asset(asset_env) -> None:
    session_id = _create_session(asset_env["db_path"])
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="Tractor",
        db_path=asset_env["db_path"],
    )
    link_session_asset(session_id, "jd_6155r_01", role="tractor", db_path=asset_env["db_path"])
    unlink_session_asset(session_id, "jd_6155r_01", db_path=asset_env["db_path"])
    assert list_session_assets(session_id, db_path=asset_env["db_path"]) == []


def test_session_without_assets_remains_valid(asset_env) -> None:
    session_id = _create_session(asset_env["db_path"])
    assert list_session_assets(session_id, db_path=asset_env["db_path"]) == []


def test_cli_asset_add_and_list(asset_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("canresearch.core.assets.default_db_path", lambda: asset_env["db_path"])
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "asset",
            "add",
            "--key",
            "jd_6155r_01",
            "--type",
            "tractor",
            "--name",
            "John Deere 6155R Workshop Tractor",
            "--manufacturer",
            "John Deere",
            "--model",
            "6155R",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "jd_6155r_01" in result.output

    listed = runner.invoke(main, ["asset", "list"])
    assert listed.exit_code == 0, listed.output
    assert "jd_6155r_01" in listed.output


def test_cli_session_asset_commands(asset_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("canresearch.core.assets.default_db_path", lambda: asset_env["db_path"])
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: asset_env["db_path"])
    session_id = _create_session(asset_env["db_path"], "abc123")
    runner = CliRunner()

    runner.invoke(
        main,
        [
            "asset",
            "add",
            "--key",
            "jd_6155r_01",
            "--type",
            "tractor",
            "--name",
            "John Deere 6155R Workshop Tractor",
        ],
    )
    runner.invoke(
        main,
        [
            "asset",
            "add",
            "--key",
            "weedit_quadro_01",
            "--type",
            "implement",
            "--name",
            "WEED-IT Quadro Unit 1",
        ],
    )
    add_tractor = runner.invoke(
        main,
        ["session", "asset", "add", session_id, "jd_6155r_01", "--role", "tractor"],
    )
    assert add_tractor.exit_code == 0, add_tractor.output
    add_implement = runner.invoke(
        main,
        ["session", "asset", "add", session_id, "weedit_quadro_01", "--role", "implement"],
    )
    assert add_implement.exit_code == 0, add_implement.output

    listed = runner.invoke(main, ["session", "asset", "list", session_id])
    assert listed.exit_code == 0, listed.output
    assert "jd_6155r_01" in listed.output
    assert "weedit_quadro_01" in listed.output
