from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from backend.app.extraction.document import DocumentContent, PageContent
from backend.app.schemas import BomItem, ExtractedField, ExtractionMethod, Note

T = TypeVar("T")


@dataclass(frozen=True)
class MatchEvidence:
    value: str
    page: int
    method: ExtractionMethod
    confidence: float


def unknown() -> ExtractedField:
    return ExtractedField(value=None, page=None, confidence=0.0, extraction_method=None)


def known(
    value: T,
    page: int | None,
    confidence: float,
    method: ExtractionMethod,
) -> ExtractedField[T]:
    return ExtractedField(
        value=value,
        page=page,
        confidence=confidence,
        extraction_method=method,
    )


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n:;,-")


def _collapse_spaced_characters(text: str) -> str:
    pattern = re.compile(r"(?<!\w)(?:[A-Z0-9]\s+){4,}[A-Z0-9](?!\w)")
    return pattern.sub(lambda match: re.sub(r"\s+", "", match.group(0)), text)


def page_search_text(page: PageContent) -> str:
    spatial = "\n".join(line.text for line in page.lines)
    return _collapse_spaced_characters(f"{page.text}\n{spatial}")


def find_first(
    document: DocumentContent,
    patterns: Iterable[str],
    *,
    flags: int = re.IGNORECASE,
    clean: Callable[[str], str] = _clean,
    confidence: float = 0.9,
) -> MatchEvidence | None:
    for page in document.pages:
        text = page_search_text(page)
        for pattern in patterns:
            match = re.search(pattern, text, flags)
            if match:
                value = clean(match.group(1))
                if value:
                    method = (
                        ExtractionMethod.OCR
                        if page.method == ExtractionMethod.OCR
                        else ExtractionMethod.COORDINATE_TEXT
                    )
                    adjusted = (
                        min(confidence, 0.68) if method == ExtractionMethod.OCR else confidence
                    )
                    return MatchEvidence(value, page.number, method, adjusted)
    return None


def evidence_field(evidence: MatchEvidence | None) -> ExtractedField[str]:
    if evidence is None:
        return unknown()
    return known(evidence.value, evidence.page, evidence.confidence, evidence.method)


def extract_title_identifiers(
    document: DocumentContent,
) -> tuple[ExtractedField[str], ExtractedField[str], ExtractedField[str]]:
    separated = re.compile(
        r"\bSIZE\s+DWG(?:\s+NO\.?)?\s+REV\s*$\n"
        r"(?:[^\n]*\n){0,2}?[^\n]*?\bCOMPONENT\s+"
        r"(?P<size>[A-E](?:[0-4])?)\s+(?:NO\s+)?"
        r"(?P<drawing>(?=[A-Z0-9._/-]*\d)[A-Z0-9][A-Z0-9._/-]{4,})\s+"
        r"(?P<revision>[A-Z0-9]{1,4})\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    inline = re.compile(
        r"\bSIZE\s+(?P<size>[A-E](?:[0-4])?)\s+"
        r"DWG(?:\s+NO\.?)?\s+(?P<drawing>[A-Z0-9][A-Z0-9._/-]{4,})\s+"
        r"REV\s+(?P<revision>[A-Z0-9]{1,4})\b",
        re.IGNORECASE,
    )
    for page in document.pages:
        spatial = _collapse_spaced_characters("\n".join(line.text for line in page.lines))
        match = inline.search(spatial) or separated.search(spatial)
        if not match:
            continue
        method = (
            ExtractionMethod.OCR
            if page.method == ExtractionMethod.OCR
            else ExtractionMethod.COORDINATE_TEXT
        )
        confidence = 0.67 if method == ExtractionMethod.OCR else 0.97
        return (
            known(_clean(match.group("drawing")), page.number, confidence, method),
            known(_clean(match.group("revision")), page.number, confidence, method),
            known(_clean(match.group("size")), page.number, confidence, method),
        )
    return unknown(), unknown(), unknown()


def extract_compact_title_metrics(
    document: DocumentContent,
) -> tuple[
    ExtractedField[str],
    ExtractedField[str],
    ExtractedField[str],
    ExtractedField[int],
    ExtractedField[int],
]:
    pattern = re.compile(
        r"\bKILOGRAMS?\s+(?P<weight>\d+(?:\.\d+)?)\s+"
        r"(?P<scale>\d+(?:\.\d+)?(?:\s*:\s*\d+(?:\.\d+)?)?)\s+"
        r"(?P<units>[A-Zµ\"]{1,12})\s+(?P<sheet>\d+)\s+(?P<total>\d+)\s*$\n"
        r"[^\n]*\bWEIGHT\s+SCALE\s*:\s+UNITS\s*:\s+SHEET\s+OF\b",
        re.IGNORECASE | re.MULTILINE,
    )
    for page in document.pages:
        spatial = "\n".join(line.text for line in page.lines)
        match = pattern.search(spatial)
        if not match:
            continue
        method = (
            ExtractionMethod.OCR
            if page.method == ExtractionMethod.OCR
            else ExtractionMethod.COORDINATE_TEXT
        )
        confidence = 0.64 if method == ExtractionMethod.OCR else 0.91
        return (
            known(match.group("weight"), page.number, confidence, method),
            known(_clean(match.group("scale")), page.number, confidence, method),
            known(match.group("units"), page.number, confidence, method),
            known(int(match.group("sheet")), page.number, confidence, method),
            known(int(match.group("total")), page.number, confidence, method),
        )
    return unknown(), unknown(), unknown(), unknown(), unknown()


def extract_revision_record(
    document: DocumentContent,
) -> tuple[ExtractedField[str], ExtractedField[str], ExtractedField[str]]:
    row_pattern = re.compile(
        r"(?:^|\n)\s*(?P<ecn>(?=[A-Z0-9-]*\d)[A-Z0-9-]{5,})\s+"
        r"(?P<description>[^\n]*?)\s+"
        r"(?P<date>\d{1,2}[/-][A-Za-z0-9]{1,3}[/-]\d{2,4})\s+"
        r"(?P<changed>[A-Z][A-Z0-9_.-]{1,})\s+"
        r"(?P<approved>[A-Z][A-Z0-9_.-]{1,})(?:\s|$)",
        re.IGNORECASE,
    )
    for page in document.pages:
        match = row_pattern.search(page_search_text(page))
        if not match:
            continue
        method = (
            ExtractionMethod.OCR
            if page.method == ExtractionMethod.OCR
            else ExtractionMethod.COORDINATE_TEXT
        )
        confidence = 0.65 if method == ExtractionMethod.OCR else 0.88
        return (
            known(_clean(match.group("ecn")), page.number, confidence, method),
            known(_clean(match.group("description")), page.number, confidence, method),
            known(_clean(match.group("approved")), page.number, confidence, method),
        )
    return unknown(), unknown(), unknown()


def extract_notes(
    document: DocumentContent, bom_items: list[BomItem] | None = None
) -> ExtractedField[list[Note]]:
    collected: list[Note] = []
    first_page: int | None = None
    first_method: ExtractionMethod | None = None
    for page in document.pages:
        text = page.text
        marker = re.search(r"\bNOTES?\s*:", text, re.IGNORECASE)
        if not marker:
            continue
        section = text[marker.end() :]
        stop = re.search(
            r"(?:CLUB CAR IS THE SOLE OWNER|IF PRINTED|DRAWN\s*$|SUPPLIER DRAWING|"
            r"FOR REFERENCE ONLY|SERVICE PARTS APPLICABLE|QTY\s+ITEM\s+PART\s+NO|"
            r"BOM\s*$|PART\s+NO\.?\s+DESCRIPTION)",
            section,
            re.IGNORECASE | re.MULTILINE,
        )
        if stop:
            section = section[: stop.start()]
        raw_matches = list(
            re.finditer(
                r"(?<![\d.])(\d{1,3})(?:[.)]\s*|\s+(?=[A-Z]))",
                section,
            )
        )
        matches = []
        for match in raw_matches:
            number = int(match.group(1))
            if not matches or number == int(matches[-1].group(1)) + 1:
                matches.append(match)
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
            value = _clean(section[match.end() : end])
            for item in bom_items or []:
                if not item.part_number or not item.description:
                    continue
                row_pattern = r"\s+(?:\d+(?:\.\d+)?\s+\d+\s+)?" + re.escape(item.part_number)
                row_pattern += r"\s+" + re.escape(item.description).replace(r"\ ", r"\s+")
                value = re.sub(row_pattern, " ", value, flags=re.IGNORECASE)
            value = _clean(value)
            if value:
                collected.append(Note(number=match.group(1), text=value))
        if collected and first_page is None:
            first_page = page.number
            first_method = page.method

    if not collected or first_page is None or first_method is None:
        return unknown()
    confidence = 0.62 if first_method == ExtractionMethod.OCR else 0.87
    method = (
        ExtractionMethod.OCR
        if first_method == ExtractionMethod.OCR
        else ExtractionMethod.NATIVE_TEXT
    )
    return known(collected, first_page, confidence, method)


def extract_standards(document: DocumentContent) -> ExtractedField[list[str]]:
    patterns = [
        r"\bASME\s*Y\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?\b",
        r"\bASTM\s*[A-Z]\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?\b",
        r"\bSAE\s*&?\s*[A-Z]\s*\d+(?:\.\d+)*(?:\s*-\s*\d+)?(?!\d)",
        r"\bFMVSS\s*-?\s*\d+(?:\.\d+)*\b",
        r"\bISO\s*\d+(?:\s*-\s*\d+)*\b",
        r"\b(?:ANSI|IEC|DIN|EN)\s*[A-Z]?\s*\d+(?:[./-]\d+)*\b",
        r"\bPES\s*0*\d{3,}\b",
        r"\bCAL\s*117\b",
    ]
    values: list[str] = []
    first_page: int | None = None
    first_method: ExtractionMethod | None = None
    for page in document.pages:
        text = page_search_text(page)
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = re.sub(r"\s+", " ", match.group(0).upper()).strip().rstrip(".,;:")
                value = re.sub(r"\s*-\s*", "-", value)
                value = re.sub(r"^(ASME)(?=Y)", r"\1 ", value)
                value = re.sub(r"^(ASTM|SAE)(?=[A-Z]\d)", r"\1 ", value)
                value = re.sub(
                    r"^(ASME|ASTM|SAE|FMVSS|ANSI|ISO|IEC|DIN|EN)\s+(?=[A-Z]?\d)",
                    r"\1 ",
                    value,
                )
                if value not in values:
                    values.append(value)
                    first_page = first_page or page.number
                    first_method = first_method or page.method
    if not values or first_page is None or first_method is None:
        return unknown()
    method = (
        ExtractionMethod.OCR
        if first_method == ExtractionMethod.OCR
        else ExtractionMethod.NATIVE_TEXT
    )
    return known(values, first_page, 0.66 if method == ExtractionMethod.OCR else 0.9, method)


def extract_native_bom(document: DocumentContent) -> tuple[list[BomItem], int | None]:
    quantity_row = re.compile(
        r"^\s*(?P<qty>\d+(?:\.\d+)?)\s+(?P<item>\d+)\s+"
        r"(?P<part>[A-Z0-9][A-Z0-9._/-]{4,})\s+(?P<description>.+)$",
        re.IGNORECASE,
    )
    part_row = re.compile(
        r"(?:^|\s)(?P<part>[A-Z0-9][A-Z0-9._/-]{5,})\s+"
        r"(?P<description>.*?)(?=\s+[A-Z0-9][A-Z0-9._/-]{5,}\s+|$)",
        re.IGNORECASE,
    )

    def valid_part_number(value: str) -> bool:
        upper = value.upper()
        return (
            len(re.findall(r"\d", value)) >= 3
            and not re.fullmatch(r"\d{1,4}[/-]\d{1,2}[/-]\d{2,4}", value)
            and not re.fullmatch(r"\d{5,}[A-Z]{4,}", upper)
            and not upper.startswith(("PES", "ASME", "ASTM", "SAE", "ISO", "FMVSS"))
        )

    def clean_description(value: str) -> str:
        value = re.split(
            r"\s+(?:CLUB CAR IS|COPIES OF|DRAWN\b|MODELED\b|DATE\b|ECN\b|"
            r"ALL DIMENSIONS\b|IF PRINTED\b|FOR SUPPLIER TOLERANCES\b|"
            r"AND MAY BE\b|PART\s+THIRD ANGLE\b|\d+[.)]\s+[A-Z])",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        return _clean(value)

    for page in document.pages:
        text = page.text
        lines = text.splitlines()
        header_indexes = [
            index
            for index, line in enumerate(lines)
            if re.search(
                r"\b(?:BOM|QTY\s+ITEM\s+PART\s+NO|"
                r"(?:SERVICE\s+)?PART\s+NO\.?\s*(?:DESCRIPTION|NAME))\b",
                line,
                re.IGNORECASE,
            )
        ]
        if not header_indexes:
            continue
        rows: list[BomItem] = []
        seen_parts: set[str] = set()
        for header_position, header_index in enumerate(header_indexes):
            end = (
                header_indexes[header_position + 1]
                if header_position + 1 < len(header_indexes)
                else min(len(lines), header_index + 45)
            )
            for line in lines[header_index + 1 : end]:
                quantity_match = quantity_row.match(line)
                matches = [quantity_match] if quantity_match else list(part_row.finditer(line))
                for match in matches:
                    if match is None:
                        continue
                    values = match.groupdict()
                    part = _clean(values["part"])
                    description = clean_description(values["description"])
                    if not valid_part_number(part) or len(description) < 2:
                        continue
                    if re.match(
                        r"^(?:PART NUMBER|INITIAL(?:\s+RELEASE)?|"
                        r"PRODUCTION(?:\s+RELEASE)?|DESCRIPTION OF CHANGE)$",
                        description,
                        re.IGNORECASE,
                    ):
                        continue
                    if part in seen_parts:
                        continue
                    seen_parts.add(part)
                    rows.append(
                        BomItem(
                            item=values.get("item"),
                            quantity=values.get("qty"),
                            part_number=part,
                            description=description,
                        )
                    )
        if rows:
            return rows, page.number
    return [], None


def part_numbers_from_bom(items: list[BomItem]) -> list[str]:
    values: list[str] = []
    for item in items:
        value = item.part_number
        if value and value not in {"-", "--"} and value not in values:
            values.append(value)
    return values
