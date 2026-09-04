"""Persist ISOBUS DDI PDF parse results."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from canresearch.references.importers.base import BaseImporter
from canresearch.references.importers.isobus_pdf import ISOBUS_SOURCE_META, parse_isobus_pdf
from canresearch.references.models import ImportReport, ReferenceOrigin
from canresearch.references.service import ReferenceService


class IsobusPdfImporter(BaseImporter):
    source_key = ISOBUS_SOURCE_META["source_key"]
    source_type = ISOBUS_SOURCE_META["source_type"]
    title = ISOBUS_SOURCE_META["title"]
    revision = ISOBUS_SOURCE_META["revision"]
    coverage_date = ISOBUS_SOURCE_META["coverage_date"]
    origin = ReferenceOrigin.ISOBUS_ADDITION

    def parse(self, path: Path) -> ImportReport:
        _, report = parse_isobus_pdf(path)
        report.source_path = str(path)
        return report

    def import_file(self, path: Path, conn: sqlite3.Connection) -> ImportReport:
        ddis, report = parse_isobus_pdf(path)
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

        for ddi in ddis:
            result = service.upsert_ddi(source_id, self.origin.value, ddi)
            report.inserted += result["inserted"]
            report.updated += result["updated"]
            report.unchanged += result["unchanged"]

        conn.commit()
        return report
