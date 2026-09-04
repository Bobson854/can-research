"""ISOBUS DDI PDF parser."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from canresearch.references.models import ImportReport, ParsedDdi, ReferenceOrigin

DDI_BLOCK = re.compile(r"DD Entity\s+(\d+)\s*-\s*(.+?)(?=DD Entity\s+\d+\s*-|@ Copyright|$)", re.S)
FIELD_PATTERNS = {
    "definition": re.compile(r"Definition\s+(.+?)(?=Comment|Typically used by|$)", re.S),
    "comment": re.compile(r"Comment\s+(.+?)(?=Typically used by|Class\(es\)|Unit Symbol|$)", re.S),
    "unit_symbol": re.compile(r"Unit Symbol\s+(.+?)(?=Resolution|SAE SPN|$)", re.S),
    "resolution": re.compile(r"Resolution\s+(.+?)(?=SAE SPN|CANBus Range|$)", re.S),
    "sae_spn": re.compile(r"SAE SPN\s+(.+?)(?=CANBus Range|Display Range|$)", re.S),
    "can_range": re.compile(r"CANBus Range\s+(.+?)(?=Display Range|Submit by|$)", re.S),
    "display_range": re.compile(r"Display Range\s+(.+?)(?=Submit by|Submit Date|$)", re.S),
    "submit_by": re.compile(r"Submit by\s+(.+?)(?=Submit Date|Submit Company|$)", re.S),
    "submit_date": re.compile(r"Submit Date\s+(.+?)(?=Submit Company|Revision Number|$)", re.S),
    "submit_company": re.compile(r"Submit Company\s+(.+?)(?=Revision Number|Current Status|$)", re.S),
    "revision_number": re.compile(r"Revision Number\s+(\d+)", re.S),
    "current_status": re.compile(r"Current Status\s+(.+?)(?=Status Date|Status Comments|$)", re.S),
    "status_date": re.compile(r"Status Date\s+(.+?)(?=Status Comments|DD Entity|$)", re.S),
    "status_comments": re.compile(r"Status Comments\s+(.+?)(?=DD Entity|@ Copyright|$)", re.S),
}
DEVICE_CLASS = re.compile(r"(?:Typically used by Device|Class\(es\))\s*(.+?)(?=Unit Symbol|$)", re.S)
DEVICE_LINE = re.compile(r"(\d+)\s*-\s*(.+)")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value.strip())
    return text or None


def _parse_range(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    cleaned = _clean(text)
    if not cleaned:
        return None, None
    parts = re.split(r"\s*-\s*", cleaned, maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return cleaned, None


def _parse_unit(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    cleaned = _clean(text)
    if not cleaned or "not defined" in cleaned.lower():
        return None, None
    if " - " in cleaned:
        symbol, desc = cleaned.split(" - ", 1)
        return symbol.strip(), desc.strip()
    return cleaned, None


def _parse_device_classes(block: str) -> list[tuple[int, str | None]]:
    section = DEVICE_CLASS.search(block)
    if not section:
        return []
    classes: list[tuple[int, str | None]] = []
    for line in section.group(1).splitlines():
        line = line.strip()
        if not line or line.lower().startswith("device"):
            continue
        match = DEVICE_LINE.match(line)
        if match:
            classes.append((int(match.group(1)), _clean(match.group(2))))
    return classes


def parse_isobus_pdf(pdf_path: Path) -> tuple[list[ParsedDdi], ImportReport]:
    report = ImportReport(source_key="isobus-ddi-snapshot", source_path=str(pdf_path))
    ddis: list[ParsedDdi] = []

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    for match in DDI_BLOCK.finditer(full_text):
        ddi_num = int(match.group(1))
        block = match.group(0)
        name = _clean(match.group(2).split("\n")[0]) or f"DDI {ddi_num}"

        fields = {key: _clean(pat.search(block).group(1)) if pat.search(block) else None for key, pat in FIELD_PATTERNS.items()}

        sae_spn = None
        if fields["sae_spn"] and fields["sae_spn"].lower() != "not specified":
            spn_match = re.search(r"(\d+)", fields["sae_spn"])
            if spn_match:
                sae_spn = int(spn_match.group(1))

        can_min, can_max = _parse_range(fields.get("can_range"))
        display_min, display_max = _parse_range(fields.get("display_range"))
        unit_symbol, unit_description = _parse_unit(fields.get("unit_symbol"))

        revision = None
        if fields.get("revision_number"):
            revision = int(fields["revision_number"])

        ddis.append(
            ParsedDdi(
                ddi=ddi_num,
                name=name,
                definition=fields.get("definition"),
                comment=fields.get("comment"),
                unit_symbol=unit_symbol,
                unit_description=unit_description,
                resolution=fields.get("resolution"),
                can_min=can_min,
                can_max=can_max,
                display_min=display_min,
                display_max=display_max,
                sae_spn=sae_spn,
                submit_by=fields.get("submit_by"),
                submit_date=fields.get("submit_date"),
                submit_company=fields.get("submit_company"),
                revision_number=revision,
                current_status=fields.get("current_status"),
                status_date=fields.get("status_date"),
                status_comments=fields.get("status_comments"),
                device_classes=_parse_device_classes(block),
                raw_text=block[:2000],
            )
        )

    report.ddis_parsed = len(ddis)
    return ddis, report


ISOBUS_SOURCE_META = {
    "source_key": "isobus-ddi-snapshot",
    "source_type": "isobus_pdf",
    "title": "ISO 11783-11 ISOBUS Data Dictionary snapshot",
    "revision": "2024-10-05",
    "coverage_date": "2024-10-05",
    "origin": ReferenceOrigin.ISOBUS_ADDITION,
}
