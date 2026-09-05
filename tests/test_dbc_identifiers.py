"""Tests for DBC identifier sanitisation."""

from __future__ import annotations

from canresearch.core.dbc_identifiers import sanitize_dbc_identifier, unique_signal_identifier


def test_hyphen_replaced() -> None:
    assert sanitize_dbc_identifier("E-Stop_Set") == "E_Stop_Set"


def test_leading_digit_prefixed() -> None:
    assert sanitize_dbc_identifier("18173201_Connected") == "CAN18173201_Connected"


def test_duplicate_signal_names_use_spn_suffix() -> None:
    used: set[str] = set()
    first = unique_signal_identifier("Engine_Speed", 190, used)
    second = unique_signal_identifier("Engine_Speed", 512, used)
    assert first == "Engine_Speed"
    assert second == "Engine_Speed_SPN512"
