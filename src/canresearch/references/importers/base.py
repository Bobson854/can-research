"""Base importer interface."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from canresearch.references.models import ImportReport, ReferenceOrigin


class BaseImporter(ABC):
    """Common importer contract for reference sources."""

    source_key: str
    source_type: str
    title: str
    revision: str
    coverage_date: str
    origin: ReferenceOrigin

    @abstractmethod
    def parse(self, path: Path) -> ImportReport:
        """Parse source file and return parse summary (without DB persistence)."""

    @abstractmethod
    def import_file(self, path: Path, conn) -> ImportReport:  # noqa: ANN001
        """Parse and persist to database."""

    @staticmethod
    def fingerprint(path: Path) -> str:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()
