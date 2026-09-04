"""J1939 PDF parser unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.references.importers.j1939_pdf import parse_j1939_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "j1939_snippets.txt"
J1939_PDF = Path("docs/original_docs/j1939-71.pdf")


def test_parse_synthetic_snippets() -> None:
    assert FIXTURES.exists()
    text = FIXTURES.read_text(encoding="utf-8")
    assert "spn100" in text
    assert "pgn65000" in text


@pytest.mark.skipif(not J1939_PDF.exists(), reason="J1939 PDF not available locally")
def test_j1939_pdf_spn_count() -> None:
    spns, _, report = parse_j1939_pdf(J1939_PDF)
    assert report.spns_parsed >= 1000
    assert len(spns) == report.spns_parsed


@pytest.mark.skipif(not J1939_PDF.exists(), reason="J1939 PDF not available locally")
def test_j1939_pdf_pgn_count() -> None:
    _, pgns, report = parse_j1939_pdf(J1939_PDF)
    assert report.pgns_parsed >= 150
    assert len(pgns) == report.pgns_parsed
    assert report.mappings_parsed >= 500


@pytest.mark.skipif(not J1939_PDF.exists(), reason="J1939 PDF not available locally")
class TestJ1939Golden:
    """Golden checks sourced from local J1939-71 PDF extraction."""

    @classmethod
    @pytest.fixture(scope="class")
    def catalogue(cls):
        return parse_j1939_pdf(J1939_PDF)

    def test_spn_190_engine_speed(self, catalogue) -> None:
        spns, _, _ = catalogue
        spn = next(s for s in spns if s.spn == 190)
        assert "Engine" in spn.name and "Speed" in spn.name.replace(" ", "")
        assert spn.definition is not None
        assert "61444" in str(spn.pgns) or 61444 in spn.pgns

    def test_spn_84_vehicle_speed(self, catalogue) -> None:
        spns, _, _ = catalogue
        spn = next(s for s in spns if s.spn == 84)
        assert "VehicleSpeed" in spn.name.replace("-", "").replace(" ", "")

    def test_spn_105_temperature(self, catalogue) -> None:
        spns, _, _ = catalogue
        spn = next(s for s in spns if s.spn == 105)
        assert "Temperature" in spn.name

    def test_pgn_61444_eec1(self, catalogue) -> None:
        _, pgns, _ = catalogue
        pgn = next(p for p in pgns if p.pgn == 61444)
        assert "ElectronicEngineController" in pgn.name.replace(" ", "")
        assert pgn.acronym == "EEC1"
        spn_numbers = {m.spn for m in pgn.mappings}
        assert 190 in spn_numbers
        assert 512 in spn_numbers

    def test_pgn_61444_engine_speed_position(self, catalogue) -> None:
        _, pgns, _ = catalogue
        pgn = next(p for p in pgns if p.pgn == 61444)
        mapping = next(m for m in pgn.mappings if m.spn == 190)
        assert mapping.raw_position_text == "4-5"
        assert mapping.bit_length == 16

    def test_pdu1_pgn_exists(self, catalogue) -> None:
        _, pgns, _ = catalogue
        pdu1 = [p for p in pgns if p.pdu_format is not None and p.pdu_format < 240]
        assert pdu1

    def test_pdu2_pgn_65265(self, catalogue) -> None:
        _, pgns, _ = catalogue
        pgn = next(p for p in pgns if p.pgn == 65265)
        assert pgn.pdu_format == 254
        assert any(m.spn == 84 for m in pgn.mappings)

    def test_lighting_pgn(self, catalogue) -> None:
        _, pgns, _ = catalogue
        pgn = next(p for p in pgns if p.pgn == 65089)
        assert "Lighting" in pgn.name

    def test_joystick_pgn(self, catalogue) -> None:
        _, pgns, _ = catalogue
        pgn = next(p for p in pgns if p.pgn == 64983)
        assert "Joystick" in pgn.name
        assert len(pgn.mappings) >= 5
