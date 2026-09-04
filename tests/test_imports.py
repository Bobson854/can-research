"""Verify package imports."""

import canresearch
from canresearch.core import j1939, sessions
from canresearch.storage import database


def test_package_version() -> None:
    assert canresearch.__version__ == "0.1.0"


def test_core_modules_import() -> None:
    assert j1939.parse_j1939_id is not None
    assert sessions.CaptureStore is not None
    assert database.initialize is not None
