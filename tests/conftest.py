"""Shared hermetic test defaults."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _hermetic_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from reading the developer's data/config.toml."""
    config_path = tmp_path / "hermetic_config.toml"
    config_path.write_text(
        """
[instance]
instance_key = "test"

[paths]
data_dir = "data"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("canresearch.config.default_config_path", lambda: config_path)


@pytest.fixture(autouse=True)
def _noop_capture_prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip network timing preparation unless a test replaces this mock."""

    def _prepare(*args, **kwargs):
        _ = args, kwargs
        return None

    monkeypatch.setattr(
        "canresearch.core.capture_prepare.prepare_channel_for_capture",
        _prepare,
    )
