"""Reference import and idempotency tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.references.importers.j1939_pdf_importer import J1939PdfImporter
from canresearch.references.service import ReferenceService
from canresearch.references.validation import validate_reference_catalogue
from canresearch.storage.database import initialize

J1939_PDF = Path("docs/original_docs/j1939-71.pdf")
ISOBUS_PDF = Path("docs/original_docs/isobus_data.pdf")


@pytest.mark.skipif(not J1939_PDF.exists(), reason="J1939 PDF not available locally")
def test_j1939_import_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "refs.db"
    conn = initialize(db_path)
    importer = J1939PdfImporter()

    first = importer.import_file(J1939_PDF, conn)
    stats1 = ReferenceService(conn).stats()

    second = importer.import_file(J1939_PDF, conn)
    stats2 = ReferenceService(conn).stats()

    assert stats1["spns"] == stats2["spns"]
    assert stats1["pgns"] == stats2["pgns"]
    assert first.spns_parsed == second.spns_parsed
    assert second.inserted == 0
    assert stats1["spns"] == stats2["spns"]
    assert stats1["pgns"] == stats2["pgns"]
    assert stats1["mappings"] == stats2["mappings"]

    validation = validate_reference_catalogue(conn)
    duplicate_errors = [e for e in validation.errors if e.category.startswith("duplicate")]
    assert not duplicate_errors

    conn.close()


@pytest.mark.skipif(not J1939_PDF.exists(), reason="J1939 PDF not available locally")
def test_j1939_lookup_after_import(tmp_path: Path) -> None:
    db_path = tmp_path / "refs.db"
    conn = initialize(db_path)
    J1939PdfImporter().import_file(J1939_PDF, conn)
    service = ReferenceService(conn)

    pgn_rows = service.lookup_pgn(61444)
    assert pgn_rows
    assert pgn_rows[0]["origin"] == "j1939_base_2001"

    spn_rows = service.lookup_spn(190)
    assert spn_rows
    mappings = service.pgn_spn_mappings(61444, source_id=pgn_rows[0]["source_id"])
    assert any(m["spn"] == 190 for m in mappings)

    conn.close()


@pytest.mark.skipif(not ISOBUS_PDF.exists(), reason="ISOBUS PDF not available locally")
def test_isobus_import(tmp_path: Path) -> None:
    from canresearch.references.importers.isobus_pdf_importer import IsobusPdfImporter

    db_path = tmp_path / "refs.db"
    conn = initialize(db_path)
    report = IsobusPdfImporter().import_file(ISOBUS_PDF, conn)
    stats = ReferenceService(conn).stats()

    assert report.ddis_parsed > 100
    assert stats["ddis"] == report.ddis_parsed

    rows = ReferenceService(conn).lookup_ddi(1)
    assert rows
    assert rows[0]["origin"] == "isobus_addition"

    conn.close()
