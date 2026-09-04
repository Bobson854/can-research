"""J1939-71 PDF parser for Section 5.2 (SPNs) and 5.3 (PGNs)."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from canresearch.references.models import (
    ImportReport,
    ParsedPgn,
    ParsedPgnSpnMapping,
    ParsedSpn,
    ReferenceOrigin,
)

SPN_BLOCK_START = re.compile(r"(?=spn(\d+)\s*-)", re.IGNORECASE)
PGN_BLOCK_START = re.compile(r"(?=pgn(\d+)-)", re.IGNORECASE)
SECTION_53_MARKER = re.compile(r"5\.3\.?\s*Parameter\s*Group\s*Definitions", re.IGNORECASE)

SPN_FIELDS = {
    "data_length": re.compile(r"DataLength:\s*(.+?)(?=Resolution:|Type:|SuspectParameterNumber:|$)", re.I | re.S),
    "resolution": re.compile(r"Resolution:\s*(.+?)(?=DataRange:|Type:|SuspectParameterNumber:|$)", re.I | re.S),
    "data_range": re.compile(r"DataRange:\s*(.+?)(?=Type:|SuspectParameterNumber:|$)", re.I | re.S),
    "data_type": re.compile(r"Type:\s*(.+?)(?=SuspectParameterNumber:|ParameterGroupNumber:|$)", re.I | re.S),
    "spn_confirm": re.compile(r"SuspectParameterNumber:\s*(\d+)", re.I),
    "pgn_list": re.compile(r"ParameterGroupNumber:\s*\[(.*?)\]", re.I | re.S),
}

PGN_HEADER_FIELDS = {
    "transmission_rate": re.compile(
        r"TransmissionRepetitionRate:\s*(.+?)(?=DataLength:|DataPage:|$)", re.I | re.S
    ),
    "data_length": re.compile(r"DataLength:\s*(.+?)(?=DataPage:|PDUFormat:|$)", re.I | re.S),
    "data_page": re.compile(r"DataPage:\s*(\d+)", re.I),
    "pdu_format": re.compile(r"PDUFormat:\s*(\d+|DA)", re.I),
    "pdu_specific": re.compile(r"PDUSpecific:\s*(\d+|DA|Group\s*Extension)", re.I),
    "default_priority": re.compile(r"DefaultPriority:\s*(\d+)", re.I),
    "pgn_confirm": re.compile(r"ParameterGroupNumber:\s*(\d+)", re.I),
}

MAPPING_ROW = re.compile(
    r"^([\d.]+(?:-\d+)?)\s+(\d+\s*(?:bits|bytes|byte))\s+(.+?)\s+(\d+)\s*$",
    re.I | re.M,
)

BITS_RE = re.compile(r"(\d+)\s*bits?", re.I)
BYTES_RE = re.compile(r"(\d+)\s*bytes?", re.I)
BYTE_RANGE_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:-(\d+))?(?:\.(\d+))?$")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _parse_data_length_bits(text: str | None) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    cleaned = _normalize_whitespace(text)
    if "variable" in cleaned.lower():
        return None, cleaned
    bits = BITS_RE.search(cleaned)
    if bits:
        return int(bits.group(1)), cleaned
    byte_match = BYTES_RE.search(cleaned)
    if byte_match:
        return int(byte_match.group(1)) * 8, cleaned
    return None, cleaned


def _parse_resolution_parts(text: str | None) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    if not text:
        return None, None, None, None, None
    cleaned = _normalize_whitespace(text)
    unit = None
    offset = None
    minimum = None
    maximum = None

    if "offset" in cleaned.lower():
        offset_match = re.search(r"(-?\d+(?:\.\d+)?)\s*offset", cleaned, re.I)
        if offset_match:
            offset = offset_match.group(1)

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*to\s*([\d,]+(?:\.\d+)?)", cleaned, re.I)
    if range_match:
        minimum = range_match.group(1)
        maximum = range_match.group(2).replace(",", "")

    unit_match = re.search(r"/([^/,]+)", cleaned)
    if unit_match:
        unit = unit_match.group(1).strip()

    return cleaned, offset, minimum, maximum, unit


def _parse_pgn_list(raw: str | None) -> list[int]:
    if not raw or not raw.strip():
        return []
    return [int(x) for x in re.findall(r"\d+", raw)]


def _clean_name(text: str) -> str:
    cleaned = re.sub(r"\.{3,}.*$", "", text)
    cleaned = re.sub(r"\s+\d+\s*$", "", cleaned)
    return _normalize_whitespace(cleaned)


def _split_spn_name_definition(header_tail: str) -> tuple[str, str | None]:
    header_tail = header_tail.split("DataLength:")[0].strip()
    if not header_tail:
        return "", None
    if "-" not in header_tail:
        return _clean_name(header_tail), None
    name_part, definition = header_tail.rsplit("-", 1)
    definition = definition.strip() or None
    return _clean_name(name_part), definition


def _parse_position(raw: str) -> tuple[int | None, int | None, int | None, str]:
    """Return start_byte, start_bit, bit_length estimate, raw text."""
    raw = raw.strip()
    match = BYTE_RANGE_RE.match(raw)
    if not match:
        return None, None, None, raw
    start_byte = int(match.group(1))
    start_bit = int(match.group(2)) if match.group(2) else None
    end_byte = int(match.group(3)) if match.group(3) else None
    end_bit = int(match.group(4)) if match.group(4) else None
    if end_byte is not None and end_bit is not None:
        return start_byte, start_bit, None, raw
    if end_byte is not None and start_bit is not None:
        return start_byte, start_bit, None, raw
    return start_byte, start_bit, None, raw


def _parse_mapping_length(text: str) -> int | None:
    bits = BITS_RE.search(text)
    if bits:
        return int(bits.group(1))
    byte_match = BYTES_RE.search(text)
    if byte_match:
        return int(byte_match.group(1)) * 8
    return None


def _parse_pgn_header(block: str) -> tuple[int, str, str | None, dict[str, object]]:
    match = re.match(r"pgn(\d+)-(.+)", block, re.I | re.S)
    if not match:
        msg = "Invalid PGN block header"
        raise ValueError(msg)
    pgn = int(match.group(1))
    remainder = match.group(2)

    name_part = remainder
    acronym = None
    dash_parts = re.split(r"-", remainder, maxsplit=2)
    if dash_parts:
        name_part = dash_parts[0]
    if len(dash_parts) > 1:
        acronym = _clean_name(dash_parts[1])
    if len(dash_parts) > 2 and acronym and acronym.endswith(" "):
        acronym = acronym.strip()

    name = _clean_name(name_part.replace("-", " "))

    fields: dict[str, object] = {}
    for key, pattern in PGN_HEADER_FIELDS.items():
        found = pattern.search(block)
        if not found:
            continue
        fields[key] = found.group(1).strip()

    payload_length = None
    dl = fields.get("data_length")
    if isinstance(dl, str):
        byte_match = BYTES_RE.search(dl)
        if byte_match:
            payload_length = int(byte_match.group(1))

    pdu_format = None
    pf = fields.get("pdu_format")
    if isinstance(pf, str) and pf.isdigit():
        pdu_format = int(pf)

    pdu_specific = None
    ps = fields.get("pdu_specific")
    if isinstance(ps, str) and ps.isdigit():
        pdu_specific = int(ps)

    default_priority = None
    dp = fields.get("default_priority")
    if isinstance(dp, str) and dp.isdigit():
        default_priority = int(dp)

    data_page = None
    dpage = fields.get("data_page")
    if isinstance(dpage, str) and dpage.isdigit():
        data_page = int(dpage)

    return (
        pgn,
        name,
        acronym,
        {
            "transmission_rate": fields.get("transmission_rate"),
            "payload_length": payload_length,
            "default_priority": default_priority,
            "data_page": data_page,
            "pdu_format": pdu_format,
            "pdu_specific": pdu_specific,
        },
    )


def _extract_pages_text(pdf_path: Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append((index, text))
    return pages


def _split_sections(pages: list[tuple[int, str]]) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    full_text = "\n".join(text for _, text in pages)
    markers = list(SECTION_53_MARKER.finditer(full_text))
    if markers:
        split_at = markers[-1].start()
        spn_text = full_text[:split_at]
        pgn_text = full_text[split_at:]
        return spn_text, pgn_text, warnings

    warnings.append("Could not locate Section 5.3 marker; using page heuristic split")
    spn_text = "\n".join(text for page_no, text in pages if page_no < 291)
    pgn_text = "\n".join(text for page_no, text in pages if page_no >= 291)
    return spn_text, pgn_text, warnings


def parse_j1939_pdf(pdf_path: Path) -> tuple[list[ParsedSpn], list[ParsedPgn], ImportReport]:
    """Parse J1939-71 PDF into SPN and PGN records."""
    report = ImportReport(
        source_key="j1939-71-dec2003",
        source_path=str(pdf_path),
    )

    pages = _extract_pages_text(pdf_path)
    spn_section, pgn_section, split_warnings = _split_sections(pages)
    report.warnings.extend(split_warnings)

    page_lookup: dict[int, int] = {}
    offset = 0
    for page_no, text in pages:
        page_lookup[offset] = page_no
        offset += len(text) + 1

    def page_for_index(index: int) -> int | None:
        best = None
        for start, page_no in page_lookup.items():
            if start <= index:
                best = page_no
            else:
                break
        return best

    spns: list[ParsedSpn] = []
    spn_blocks = SPN_BLOCK_START.split(spn_section)
    for block in spn_blocks:
        block = block.strip()
        if not block or not block.lower().startswith("spn"):
            continue
        if "SuspectParameterNumber:" not in block:
            continue
        header = re.match(r"spn(\d+)\s*-\s*(.*)", block, re.I | re.S)
        if not header:
            report.warnings.append(f"Malformed SPN block near: {block[:80]!r}")
            continue
        spn_num = int(header.group(1))
        name, definition = _split_spn_name_definition(header.group(2))

        confirm = SPN_FIELDS["spn_confirm"].search(block)
        if confirm and int(confirm.group(1)) != spn_num:
            report.warnings.append(f"SPN number mismatch in block for spn{spn_num}")

        dl_text = SPN_FIELDS["data_length"].search(block)
        data_length_text = _normalize_whitespace(dl_text.group(1)) if dl_text else None
        data_length_bits, _ = _parse_data_length_bits(data_length_text)

        res_text = SPN_FIELDS["resolution"].search(block)
        resolution, offset, minimum, maximum, unit = _parse_resolution_parts(
            res_text.group(1) if res_text else None
        )

        dr = SPN_FIELDS["data_range"].search(block)
        if dr and not minimum:
            _, _, minimum, maximum, _ = _parse_resolution_parts(f"DataRange: {dr.group(1)}")

        dtype = SPN_FIELDS["data_type"].search(block)
        data_type = _normalize_whitespace(dtype.group(1)) if dtype else None

        status = None
        if definition and (
            "obsolete" in definition.lower() or "not to be used" in definition.lower()
        ):
            status = "obsolete"

        pgn_raw = SPN_FIELDS["pgn_list"].search(block)
        pgns = _parse_pgn_list(pgn_raw.group(1) if pgn_raw else None)

        idx = spn_section.find(block[: min(40, len(block))])
        spns.append(
            ParsedSpn(
                spn=spn_num,
                name=name,
                definition=definition,
                description=definition,
                data_length_bits=data_length_bits,
                data_length_text=data_length_text,
                resolution=resolution,
                offset=offset,
                minimum=minimum,
                maximum=maximum,
                unit=unit,
                data_type=data_type,
                status=status,
                source_page=page_for_index(idx) if idx >= 0 else None,
                raw_text=block[:2000],
                pgns=pgns,
            )
        )

    pgns: list[ParsedPgn] = []
    pgn_blocks = PGN_BLOCK_START.split(pgn_section)
    for block in pgn_blocks:
        block = block.strip()
        if not block or not block.lower().startswith("pgn"):
            continue
        if "ParameterGroupNumber:" not in block:
            continue
        try:
            pgn_num, name, acronym, meta = _parse_pgn_header(block)
        except ValueError:
            report.warnings.append(f"Malformed PGN block near: {block[:80]!r}")
            continue

        table_start = block.find("BitStartPosition")
        mapping_text = block[table_start:] if table_start >= 0 else ""
        mappings: list[ParsedPgnSpnMapping] = []
        order = 0
        for row in MAPPING_ROW.finditer(mapping_text):
            pos_raw, length_raw, desc_raw, spn_raw = row.groups()
            order += 1
            start_byte, start_bit, _, pos_text = _parse_position(pos_raw)
            bit_length = _parse_mapping_length(length_raw)
            mappings.append(
                ParsedPgnSpnMapping(
                    spn=int(spn_raw),
                    position_order=order,
                    start_byte=start_byte,
                    start_bit=start_bit,
                    bit_length=bit_length,
                    raw_position_text=pos_raw,
                    spn_description=_normalize_whitespace(desc_raw),
                    length_text=length_raw,
                )
            )

        idx = pgn_section.find(block[: min(40, len(block))])
        pgns.append(
            ParsedPgn(
                pgn=pgn_num,
                name=name,
                acronym=acronym,
                transmission_rate=(
                    str(meta["transmission_rate"]) if meta.get("transmission_rate") else None
                ),
                payload_length=meta.get("payload_length"),  # type: ignore[arg-type]
                default_priority=meta.get("default_priority"),  # type: ignore[arg-type]
                data_page=meta.get("data_page"),  # type: ignore[arg-type]
                pdu_format=meta.get("pdu_format"),  # type: ignore[arg-type]
                pdu_specific=meta.get("pdu_specific"),  # type: ignore[arg-type]
                source_page=page_for_index(idx) if idx >= 0 else None,
                raw_text=block[:2000],
                mappings=mappings,
            )
        )

    report.spns_parsed = len(spns)
    report.pgns_parsed = len(pgns)
    report.mappings_parsed = sum(len(p.mappings) for p in pgns)
    return spns, pgns, report


J1939_SOURCE_META = {
    "source_key": "j1939-71-dec2003",
    "source_type": "j1939_pdf",
    "title": "SAE J1939-71 DEC2003",
    "revision": "DEC2003",
    "coverage_date": "2001-12",
    "origin": ReferenceOrigin.J1939_BASE_2001,
}
