from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

import pdfplumber

from backend.app.schemas import BomItem

logger = logging.getLogger(__name__)

HEADER_ALIASES = {
    "item": {"item", "item no", "item number", "sl no", "s no", "s.no"},
    "quantity": {"qty", "quantity"},
    "part_number": {"part no", "part number", "part no.", "dwg no", "service part no"},
    "description": {"description", "name", "part description"},
    "material": {"material"},
    "remarks": {"remark", "remarks"},
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _canonical_header(value: object) -> str | None:
    normalized = re.sub(r"[^a-z0-9.]+", " ", _clean(value).lower()).strip()
    for canonical, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def _rows_from_table(table: list[list[object]]) -> list[BomItem]:
    if len(table) < 2:
        return []
    for header_index, row in enumerate(table[:5]):
        mapped = [_canonical_header(cell) for cell in row]
        recognized = {item for item in mapped if item}
        if "part_number" not in recognized or not ({"description", "quantity"} & recognized):
            continue
        columns = {name: index for index, name in enumerate(mapped) if name}
        items: list[BomItem] = []
        for raw_row in table[header_index + 1 :]:
            values = {
                name: _clean(raw_row[index]) if index < len(raw_row) else ""
                for name, index in columns.items()
            }
            if not values.get("part_number") and not values.get("description"):
                continue
            items.append(
                BomItem(
                    item=values.get("item") or None,
                    quantity=values.get("quantity") or None,
                    part_number=values.get("part_number") or None,
                    description=values.get("description") or None,
                    material=values.get("material") or None,
                    remarks=values.get("remarks") or None,
                )
            )
        if items:
            return items
    return []


def extract_bom_tables(
    path: Path, candidate_pages: Iterable[int]
) -> tuple[list[BomItem], int | None]:
    candidate_set = set(candidate_pages)
    if not candidate_set:
        return [], None
    try:
        with pdfplumber.open(path) as document:
            for page_number in sorted(candidate_set):
                page = document.pages[page_number - 1]
                for table in page.extract_tables() or []:
                    items = _rows_from_table(table)
                    if items:
                        return items, page_number
    except Exception:
        logger.exception("pdfplumber table extraction failed for %s", path.name)
    return [], None
