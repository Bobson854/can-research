"""Future ISOBUS web importers (not implemented)."""

from __future__ import annotations

from pathlib import Path

from canresearch.references.importers.base import BaseImporter
from canresearch.references.models import ImportReport, ReferenceOrigin


class IsobusPgnSpnWebImporter(BaseImporter):
    """Placeholder for https://www.isobus.net/isobus/pGNAndSPN imports."""

    source_key = "isobus-web-pgn-spn"
    source_type = "isobus_web"
    title = "ISOBUS PGN/SPN web catalogue"
    revision = ""
    coverage_date = ""
    origin = ReferenceOrigin.ISOBUS_ADDITION

    def parse(self, path: Path) -> ImportReport:
        raise NotImplementedError("ISOBUS web PGN/SPN import is not yet implemented")

    def import_file(self, path: Path, conn) -> ImportReport:  # noqa: ANN001
        raise NotImplementedError("ISOBUS web PGN/SPN import is not yet implemented")


class IsobusDdiWebImporter(BaseImporter):
    """Placeholder for ISOBUS data dictionary web imports."""

    source_key = "isobus-web-ddi"
    source_type = "isobus_web"
    title = "ISOBUS DDI web catalogue"
    revision = ""
    coverage_date = ""
    origin = ReferenceOrigin.ISOBUS_ADDITION

    def parse(self, path: Path) -> ImportReport:
        raise NotImplementedError("ISOBUS DDI web import is not yet implemented")

    def import_file(self, path: Path, conn) -> ImportReport:  # noqa: ANN001
        raise NotImplementedError("ISOBUS DDI web import is not yet implemented")
