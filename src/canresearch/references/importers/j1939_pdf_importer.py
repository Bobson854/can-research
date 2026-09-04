"""Persist J1939 PDF parse results into SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from canresearch.references.importers.base import BaseImporter
from canresearch.references.importers.j1939_pdf import J1939_SOURCE_META, parse_j1939_pdf
from canresearch.references.models import ImportReport, ReferenceOrigin
from canresearch.references.service import ReferenceService


class J1939PdfImporter(BaseImporter):
    source_key = J1939_SOURCE_META["source_key"]
    source_type = J1939_SOURCE_META["source_type"]
    title = J1939_SOURCE_META["title"]
    revision = J1939_SOURCE_META["revision"]
    coverage_date = J1939_SOURCE_META["coverage_date"]
    origin = ReferenceOrigin.J1939_BASE_2001

    def parse(self, path: Path) -> ImportReport:
        _, _, report = parse_j1939_pdf(path)
        report.source_path = str(path)
        return report

    def import_file(self, path: Path, conn: sqlite3.Connection) -> ImportReport:
        spns, pgns, report = parse_j1939_pdf(path)
        report.source_path = str(path)
        service = ReferenceService(conn)

        source_id = service.ensure_source(
            source_key=self.source_key,
            source_type=self.source_type,
            title=self.title,
            revision=self.revision,
            coverage_date=self.coverage_date,
            origin=self.origin.value,
            source_path=str(path),
            fingerprint=self.fingerprint(path),
        )

        for spn in spns:
            result = service.upsert_spn(source_id, self.origin.value, spn)
            report.inserted += result["inserted"]
            report.updated += result["updated"]
            report.unchanged += result["unchanged"]

        for pgn in pgns:
            result = service.upsert_pgn(source_id, self.origin.value, pgn)
            report.inserted += result["inserted"]
            report.updated += result["updated"]
            report.unchanged += result["unchanged"]
            for mapping in pgn.mappings:
                service.upsert_pgn_spn_mapping(source_id, pgn.pgn, mapping)

        conn.commit()
        return report
