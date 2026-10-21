"""Interactive Streamlit review workspace with provenance-linked PDF navigation."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pymupdf as fitz
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

STATUS_COLORS = {
    "FAIL": "#b83f37",
    "WARNING": "#c27b12",
    "MANUAL_REVIEW": "#6b58a3",
    "PASS": "#5c8c25",
    "NOT_EVALUATED": "#65747c",
    "NOT_APPLICABLE": "#8c9691",
}
KIND_COLORS = {
    "field": "#76a118",
    "validation": "#6b58a3",
    "visual": "#247a99",
    "relationship": "#a14878",
    "entity": "#3b7d55",
}


def _value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _display(value: Any) -> str:
    value = _value(value)
    if value is None or value == "":
        return "—"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _arrow_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{key: _display(value) for key, value in row.items()} for row in rows]


def _field_region(label: str, field: Any) -> dict[str, Any] | None:
    if not isinstance(field, dict):
        return None
    page = field.get("page_number")
    box = field.get("bounding_box")
    if not page or not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    return {
        "label": label,
        "page_number": int(page),
        "bounding_box": [float(value) for value in box],
        "confidence": float(field.get("confidence") or 0),
        "method": field.get("extraction_method"),
        "raw_text": field.get("raw_text"),
        "kind": "field",
        "status": None,
    }


def _evidence_regions(
    evidence: list[dict[str, Any]] | None,
    *,
    label: str,
    kind: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for item in evidence or []:
        page = item.get("page_number")
        box = item.get("bounding_box")
        if not page or not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        regions.append(
            {
                "label": label,
                "page_number": int(page),
                "bounding_box": [float(value) for value in box],
                "confidence": float(item.get("confidence") or 0),
                "method": item.get("extraction_method") or item.get("source_level"),
                "raw_text": item.get("raw_text") or _display(item.get("value")),
                "kind": kind,
                "status": status,
            }
        )
    return regions


def _all_extracted_regions(value: Any, path: str = "drawing") -> list[dict[str, Any]]:
    direct = _field_region(path, value)
    if direct is not None:
        return [direct]
    regions: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            regions.extend(_all_extracted_regions(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            regions.extend(_all_extracted_regions(child, f"{path}[{index}]"))
    return regions


def _visual_region(item: dict[str, Any]) -> dict[str, Any] | None:
    page = item.get("page_number")
    box = item.get("bounding_box")
    if not page or not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    return {
        "label": str(item.get("object_type") or "Visual object").replace("_", " "),
        "page_number": int(page),
        "bounding_box": [float(value) for value in box],
        "confidence": float(item.get("confidence") or 0),
        "method": item.get("detector") or item.get("extraction_method"),
        "raw_text": item.get("normalized_text") or item.get("raw_text"),
        "kind": "visual",
        "status": None,
    }


def _selection_signature(label: str, regions: list[dict[str, Any]]) -> str:
    anchors = [
        f"{item['page_number']}:{','.join(f'{value:.3f}' for value in item['bounding_box'])}"
        for item in regions
    ]
    return f"{label}|{'|'.join(anchors)}"


def _activate_selection(label: str, regions: list[dict[str, Any]], detail: Any) -> None:
    signature = _selection_signature(label, regions)
    if st.session_state.get("workspace_selection_signature") == signature:
        st.session_state["workspace_detail"] = detail
        return
    st.session_state["workspace_selection_signature"] = signature
    st.session_state["workspace_selection"] = regions
    st.session_state["workspace_detail"] = detail
    if regions:
        st.session_state["workspace_page"] = regions[0]["page_number"]
    st.rerun()


def _clear_selection() -> None:
    for key in (
        "workspace_selection_signature",
        "workspace_selection",
        "workspace_detail",
    ):
        st.session_state.pop(key, None)


@st.cache_data(show_spinner=False)
def _render_page(pdf_bytes: bytes, page_number: int, scale: float) -> tuple[bytes, float, float]:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png"), float(page.rect.width), float(page.rect.height)


def _region_color(region: dict[str, Any], selected: bool) -> str:
    if selected:
        return "#b8ed42"
    status = region.get("status")
    if status:
        return STATUS_COLORS.get(str(status), "#65747c")
    return KIND_COLORS.get(str(region.get("kind")), "#247a99")


def _annotated_page(
    pdf_bytes: bytes,
    page_number: int,
    regions: list[tuple[dict[str, Any], bool]],
    zoom: int,
) -> bytes:
    scale = max(1.25, min(3.0, zoom / 65))
    payload, page_width, page_height = _render_page(pdf_bytes, page_number, scale)
    image = Image.open(io.BytesIO(payload)).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    scale_x = image.width / page_width
    scale_y = image.height / page_height
    for region, selected in regions:
        x0, y0, x1, y1 = region["bounding_box"]
        rectangle = (
            max(0, round(x0 * scale_x)),
            max(0, round(y0 * scale_y)),
            min(image.width - 1, round(x1 * scale_x)),
            min(image.height - 1, round(y1 * scale_y)),
        )
        color = _region_color(region, selected)
        width = 5 if selected else 2
        draw.rectangle(rectangle, outline=color, width=width)
        if selected or region.get("kind") == "visual":
            confidence = region.get("confidence")
            confidence_text = f" · {confidence:.0%}" if isinstance(confidence, float) else ""
            label = f"{str(region.get('label') or 'Evidence')[:34]}{confidence_text}"
            left = rectangle[0]
            top = max(0, rectangle[1] - 18)
            text_box = draw.textbbox((left + 4, top + 2), label, font=font)
            draw.rectangle(
                (
                    left,
                    top,
                    min(image.width - 1, text_box[2] + 5),
                    min(image.height - 1, text_box[3] + 3),
                ),
                fill=color,
            )
            draw.text((left + 4, top + 2), label, fill="#ffffff", font=font)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _evidence_closeup(pdf_bytes: bytes, region: dict[str, Any]) -> bytes:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        page = document.load_page(region["page_number"] - 1)
        x0, y0, x1, y1 = region["bounding_box"]
        margin_x = max(24.0, (x1 - x0) * 1.5)
        margin_y = max(18.0, (y1 - y0) * 2.0)
        clip = fitz.Rect(x0 - margin_x, y0 - margin_y, x1 + margin_x, y1 + margin_y) & page.rect
        pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip, alpha=False)
        image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        draw = ImageDraw.Draw(image)
        sx = image.width / clip.width
        sy = image.height / clip.height
        box = (
            round((x0 - clip.x0) * sx),
            round((y0 - clip.y0) * sy),
            round((x1 - clip.x0) * sx),
            round((y1 - clip.y0) * sy),
        )
        draw.rectangle(box, outline="#76a118", width=6)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def _selected_rows(event: Any) -> list[int]:
    try:
        return list(event.selection.rows)
    except (AttributeError, TypeError):
        return []


def _selectable_table(
    rows: list[dict[str, Any]],
    items: list[Any],
    *,
    key: str,
    label: Callable[[Any], str],
    regions: Callable[[Any], list[dict[str, Any]]],
) -> Any | None:
    if not rows:
        st.info("No evidence-backed records are available in this section.")
        return None
    st.caption(
        "Click any cell in a row to open its details and locate available evidence on the drawing."
    )
    event = st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )
    selected_rows = _selected_rows(event)
    if not selected_rows:
        return None
    index = selected_rows[0]
    if not 0 <= index < len(items):
        return None
    item = items[index]
    _activate_selection(label(item), regions(item), item)
    return item


def _field_rows(
    fields: list[tuple[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[str, Any]]]:
    rows = []
    items = []
    for label, field in fields:
        if not isinstance(field, dict) or "value" not in field:
            continue
        rows.append(
            {
                "Field": label,
                "Value": _display(field),
                "Page": field.get("page_number"),
                "Confidence": field.get("confidence"),
                "Method": field.get("extraction_method"),
                "Located": "YES" if _field_region(label, field) else "NO",
            }
        )
        items.append((label, field))
    return rows, items


def _render_field_table(fields: list[tuple[str, Any]], key: str) -> None:
    rows, items = _field_rows(fields)
    _selectable_table(
        rows,
        items,
        key=key,
        label=lambda item: item[0],
        regions=lambda item: [region] if (region := _field_region(item[0], item[1])) else [],
    )


def _preview_panel(
    pdf_bytes: bytes,
    drawing: dict[str, Any],
    vision: dict[str, Any],
    page_count: int,
) -> None:
    current = int(st.session_state.get("workspace_page", 1))
    current = max(1, min(page_count, current))
    st.session_state["workspace_page"] = current
    controls = st.columns([0.13, 0.42, 0.13, 0.32])
    if controls[0].button("←", disabled=current <= 1, key="preview_previous"):
        st.session_state["workspace_page"] = current - 1
        st.rerun()
    selected_page = controls[1].selectbox(
        "Sheet",
        options=list(range(1, page_count + 1)),
        index=current - 1,
        format_func=lambda value: f"SHEET {value} / {page_count}",
        label_visibility="collapsed",
        key="preview_sheet_picker",
    )
    if selected_page != current:
        st.session_state["workspace_page"] = selected_page
        st.rerun()
    if controls[2].button("→", disabled=current >= page_count, key="preview_next"):
        st.session_state["workspace_page"] = current + 1
        st.rerun()
    zoom = controls[3].select_slider(
        "Zoom",
        options=[75, 100, 125, 150, 200],
        value=100,
        format_func=lambda value: f"{value}%",
        label_visibility="collapsed",
        key="preview_zoom",
    )

    selected = st.session_state.get("workspace_selection", [])
    selected_here = [region for region in selected if region["page_number"] == current]
    if selected:
        pages = sorted({region["page_number"] for region in selected})
        st.info(
            f"Showing {len(selected)} evidence region(s) on sheet(s) "
            f"{', '.join(map(str, pages))}. Current selection: {selected[0]['label']}"
        )
    else:
        st.caption(
            "Select a field, issue, NG result, description, visual object, or relationship finding."
        )

    if selected_here:
        with st.expander("Selected evidence close-up", expanded=True):
            st.image(_evidence_closeup(pdf_bytes, selected_here[0]), width="stretch")
            region = selected_here[0]
            st.caption(
                f"Page {region['page_number']} · confidence {region['confidence']:.0%} · "
                f"method {region.get('method') or 'not available'}"
            )

    toggles = st.columns(2)
    show_extracted = toggles[0].checkbox(
        "Show extracted regions", value=False, key="show_extracted"
    )
    show_visual = toggles[1].checkbox("Show visual detections", value=True, key="show_visual")
    visual_types = sorted({str(item.get("object_type")) for item in vision.get("objects", [])})
    chosen_types = visual_types
    if show_visual and visual_types:
        with st.expander("Visual overlay types", expanded=False):
            chosen_types = st.multiselect(
                "Types",
                visual_types,
                default=visual_types,
                label_visibility="collapsed",
                key="visible_visual_types",
            )

    overlays: list[tuple[dict[str, Any], bool]] = []
    if show_extracted:
        overlays.extend(
            (region, False)
            for region in _all_extracted_regions(drawing)
            if region["page_number"] == current
        )
    if show_visual:
        overlays.extend(
            (region, False)
            for item in vision.get("objects", [])
            if str(item.get("object_type")) in chosen_types
            and (region := _visual_region(item)) is not None
            and region["page_number"] == current
        )
    overlays.extend((region, True) for region in selected if region["page_number"] == current)
    st.image(_annotated_page(pdf_bytes, current, overlays, zoom), width="stretch")

    page = next(
        (item for item in drawing.get("pages", []) if item.get("page_number") == current), {}
    )
    native = "NATIVE TEXT AVAILABLE" if page.get("native_text_available") else "NO NATIVE TEXT"
    st.caption(
        f"● {native} · {page.get('word_count') or 0} WORDS · "
        f"{page.get('text_block_count') or 0} BLOCKS"
    )
    if selected and st.button("Clear drawing highlight", key="clear_workspace_selection"):
        _clear_selection()
        st.rerun()


def _drawing_panel(drawing: dict[str, Any]) -> None:
    identity_tab, revision_tab, notes_tab, bom_tab, supplier_tab, standards_tab, quality_tab = (
        st.tabs(["Identity", "Revisions", "Notes", "BOM", "Supplier", "Standards", "Quality"])
    )
    with identity_tab:
        keys = (
            "drawing_number",
            "revision",
            "drawing_size",
            "part_name",
            "part_numbers",
            "units",
            "scale",
            "weight",
            "sheet_number",
            "total_sheets",
            "critical_component",
            "release_date",
            "drawing_date",
            "drawn_by",
            "modeled_by",
            "approved_by",
        )
        _render_field_table(
            [(key.replace("_", " ").title(), drawing.get(key)) for key in keys], "identity_fields"
        )
    with revision_tab:
        records = drawing.get("revision_records", [])
        rows = [
            {
                "Revision": _display(item.get("revision")),
                "ECN": _display(item.get("ecn")),
                "Description": _display(item.get("revision_description")),
                "Date": _display(item.get("revision_date")),
                "Changed by": _display(item.get("changed_by")),
                "Approved by": _display(item.get("approved_by")),
                "Page": item.get("page_number"),
            }
            for item in records
        ]
        _selectable_table(
            rows,
            records,
            key="revision_rows",
            label=lambda item: f"Revision {_display(item.get('revision'))}",
            regions=lambda item: [
                region for name, field in item.items() if (region := _field_region(name, field))
            ],
        )
    with notes_tab:
        notes = drawing.get("notes", [])
        rows = [
            {
                "Number": _display(item.get("number")),
                "Description": _display(item.get("text")),
                "Page": item.get("page_number"),
            }
            for item in notes
        ]
        _selectable_table(
            rows,
            notes,
            key="note_rows",
            label=lambda item: f"Note {_display(item.get('number'))}",
            regions=lambda item: (
                [region] if (region := _field_region("Note description", item.get("text"))) else []
            ),
        )
    with bom_tab:
        for source, title in (
            ("bom_items", "Bill of materials"),
            ("part_list_items", "Part list"),
            ("service_part_items", "Service parts"),
        ):
            st.markdown(f"#### {title}")
            items = drawing.get(source, [])
            rows = [
                {
                    "Item": _display(item.get("item_no")),
                    "Quantity": _display(item.get("quantity")),
                    "Part number": _display(item.get("part_number")),
                    "Description": _display(item.get("description")),
                    "Material": _display(item.get("material")),
                    "Remarks": _display(item.get("remarks")),
                    "Page": item.get("page_number"),
                }
                for item in items
            ]
            _selectable_table(
                rows,
                items,
                key=f"{source}_rows",
                label=lambda item: f"BOM {_display(item.get('part_number'))}",
                regions=lambda item: [
                    region for name, field in item.items() if (region := _field_region(name, field))
                ],
            )
    with supplier_tab:
        supplier = drawing.get("supplier_info") or {}
        fields = [
            (key.replace("_", " ").title(), value)
            for key, value in supplier.items()
            if isinstance(value, dict) and "value" in value
        ]
        _render_field_table(fields, "supplier_fields")
        mappings = supplier.get("manufacturer_part_number_mappings") or []
        if mappings:
            st.markdown("#### Manufacturer part mappings")
            rows = [
                {
                    "Source part": _display(item.get("source_part_number")),
                    "Manufacturer part": _display(item.get("manufacturer_part_number")),
                }
                for item in mappings
            ]
            _selectable_table(
                rows,
                mappings,
                key="supplier_mapping_rows",
                label=lambda item: "Manufacturer part mapping",
                regions=lambda item: [
                    region for name, field in item.items() if (region := _field_region(name, field))
                ],
            )
    with standards_tab:
        standards = drawing.get("standard_references", [])
        rows = [
            {
                "Designation": _display(item.get("designation")),
                "Description": _display(item.get("description")),
            }
            for item in standards
        ]
        _selectable_table(
            rows,
            standards,
            key="standard_rows",
            label=lambda item: f"Standard {_display(item.get('designation'))}",
            regions=lambda item: [
                region for name, field in item.items() if (region := _field_region(name, field))
            ],
        )
    with quality_tab:
        summary = drawing.get("level1_summary") or {}
        metrics = st.columns(4)
        metrics[0].metric(
            "Pages", _value(drawing.get("page_count")) or len(drawing.get("pages", []))
        )
        metrics[1].metric("Fields extracted", summary.get("extracted_field_count", 0))
        metrics[2].metric("High confidence", summary.get("high_confidence_count", 0))
        metrics[3].metric("Warnings", summary.get("warning_count", 0))
        warnings = drawing.get("extraction_warnings", [])
        if warnings:
            st.dataframe(warnings, width="stretch", hide_index=True)
        with st.expander("Complete extraction evidence and provenance"):
            st.dataframe(_all_extracted_regions(drawing), width="stretch", hide_index=True)


def _validation_panel(validation: dict[str, Any]) -> None:
    summary = validation.get("summary", {})
    metrics = st.columns(6)
    for column, key, label in zip(
        metrics,
        ("total_rules", "passed", "failed", "warnings", "manual_review", "not_evaluated"),
        ("Total", "Passed", "Failed", "Warnings", "Manual review", "Not evaluated"),
        strict=True,
    ):
        column.metric(label, summary.get(key, 0))
    results = validation.get("results", [])
    statuses = ["ALL", *sorted({str(item.get("status")) for item in results})]
    chosen = st.segmented_control("Result filter", statuses, default="ALL", key="validation_filter")
    filtered = (
        results
        if chosen in (None, "ALL")
        else [item for item in results if item.get("status") == chosen]
    )
    rows = [
        {
            "Rule": item.get("rule_id"),
            "Issue / Description": item.get("rule_name"),
            "Status": item.get("status"),
            "Severity": item.get("severity"),
            "Actual": item.get("actual_condition"),
            "Evidence": len(item.get("evidence", [])),
        }
        for item in filtered
    ]
    selected = _selectable_table(
        rows,
        filtered,
        key="validation_rows",
        label=lambda item: f"{item.get('rule_id')} · {item.get('rule_name')}",
        regions=lambda item: _evidence_regions(
            item.get("evidence"),
            label=str(item.get("rule_name")),
            kind="validation",
            status=item.get("status"),
        ),
    )
    selected = selected or (
        st.session_state.get("workspace_detail")
        if isinstance(st.session_state.get("workspace_detail"), dict)
        and "rule_id" in st.session_state.get("workspace_detail", {})
        else None
    )
    if selected:
        with st.expander("Selected checklist result", expanded=True):
            st.markdown(f"**{selected.get('status')} · {selected.get('rule_name')}**")
            st.write(selected.get("message") or selected.get("actual_condition"))
            st.markdown(f"**Expected:** {selected.get('expected_condition')}")
            st.markdown(f"**Recommendation:** {selected.get('recommendation')}")
            st.dataframe(
                _arrow_safe_rows(selected.get("evidence", [])),
                width="stretch",
                hide_index=True,
            )


def _visual_panel(vision: dict[str, Any]) -> None:
    summary = vision.get("summary", {})
    metrics = st.columns(3)
    metrics[0].metric("Pages processed", summary.get("pages_processed", 0))
    metrics[1].metric("Objects detected", summary.get("objects_detected", 0))
    metrics[2].metric("Low confidence", summary.get("low_confidence_count", 0))
    objects = vision.get("objects", [])
    types = ["ALL", *sorted({str(item.get("object_type")) for item in objects})]
    chosen = st.segmented_control("Object filter", types, default="ALL", key="visual_filter")
    filtered = (
        objects
        if chosen in (None, "ALL")
        else [item for item in objects if item.get("object_type") == chosen]
    )
    rows = [
        {
            "Type / Description": str(item.get("object_type")).replace("_", " "),
            "Page": item.get("page_number"),
            "Text": item.get("normalized_text") or item.get("raw_text"),
            "Confidence": item.get("confidence"),
            "Detector": item.get("detector"),
        }
        for item in filtered
    ]
    selected = _selectable_table(
        rows,
        filtered,
        key="visual_rows",
        label=lambda item: str(item.get("object_type")).replace("_", " "),
        regions=lambda item: [region] if (region := _visual_region(item)) else [],
    )
    selected = selected or (
        st.session_state.get("workspace_detail")
        if isinstance(st.session_state.get("workspace_detail"), dict)
        and "object_id" in st.session_state.get("workspace_detail", {})
        else None
    )
    if selected:
        with st.expander("Selected visual evidence", expanded=True):
            st.json(selected, expanded=False)
    with st.expander("Detector diagnostics"):
        st.dataframe(
            [
                {
                    "Detector": item.get("detector_name"),
                    "Objects": len(item.get("objects", [])),
                    "Warnings": len(item.get("warnings", [])),
                    "Execution ms": item.get("execution_time_ms"),
                    "OCR ms": item.get("ocr_time_ms"),
                }
                for item in vision.get("detector_results", [])
            ],
            width="stretch",
            hide_index=True,
        )
    st.caption(vision.get("disclaimer"))


def _relationship_panel(relationships: dict[str, Any]) -> None:
    summary = relationships.get("summary", {})
    metrics = st.columns(6)
    for column, key, label in zip(
        metrics,
        (
            "relationships_checked",
            "passed",
            "broken",
            "warnings",
            "manual_review",
            "high_priority_findings",
        ),
        ("Checked", "Passed", "Broken", "Warnings", "Manual review", "High priority"),
        strict=True,
    ):
        column.metric(label, summary.get(key, 0))
    findings = relationships.get("findings", [])
    rows = [
        {
            "Priority": item.get("priority"),
            "Rule": item.get("relationship_rule_id"),
            "Issue / Description": item.get("name"),
            "Status": item.get("status"),
            "Confidence": item.get("confidence"),
            "Actual": item.get("actual_relationship"),
        }
        for item in findings
    ]
    selected = _selectable_table(
        rows,
        findings,
        key="relationship_rows",
        label=lambda item: f"{item.get('relationship_rule_id')} · {item.get('name')}",
        regions=lambda item: _evidence_regions(
            item.get("evidence"),
            label=str(item.get("name")),
            kind="relationship",
            status=item.get("status"),
        ),
    )
    selected = selected or (
        st.session_state.get("workspace_detail")
        if isinstance(st.session_state.get("workspace_detail"), dict)
        and "finding_id" in st.session_state.get("workspace_detail", {})
        else None
    )
    if selected:
        with st.expander("Selected relationship finding", expanded=True):
            st.markdown(
                f"**{selected.get('priority')} · {selected.get('status')} · "
                f"{selected.get('name')}**"
            )
            st.markdown(f"**Expected:** {selected.get('expected_relationship')}")
            st.markdown(f"**Actual:** {selected.get('actual_relationship')}")
            st.write(selected.get("explanation"))
            st.markdown(f"**Recommendation:** {selected.get('recommendation')}")
            st.dataframe(
                _arrow_safe_rows(selected.get("evidence", [])),
                width="stretch",
                hide_index=True,
            )
    graph = relationships.get("graph", {})
    with st.expander("Relationship graph", expanded=False):
        nodes = graph.get("nodes", [])
        node_rows = [
            {
                "Entity": item.get("entity_type"),
                "Value": _display(item.get("value")),
                "Page": item.get("page_number"),
                "Source": item.get("source_level"),
                "Confidence": item.get("confidence"),
            }
            for item in nodes
        ]
        _selectable_table(
            node_rows,
            nodes,
            key="relationship_nodes",
            label=lambda item: f"{item.get('entity_type')} · {_display(item.get('value'))}",
            regions=lambda item: _evidence_regions(
                [item], label=str(item.get("entity_type")), kind="entity"
            ),
        )
        st.markdown("#### Edges")
        st.dataframe(
            _arrow_safe_rows(graph.get("edges", [])),
            width="stretch",
            hide_index=True,
        )
    with st.expander("Correlations"):
        st.json(relationships.get("correlations", []), expanded=False)
    st.caption(relationships.get("disclaimer"))


def _report_panel(
    analysis: dict[str, Any],
    pdf_bytes: bytes,
    filename: str,
    report_csv: bytes,
) -> None:
    st.warning(analysis["disclaimer"])
    metrics = st.columns(4)
    for column, level in zip(metrics, ("level1", "level2", "level3", "level4"), strict=True):
        column.metric(level.replace("level", "Level "), f"{analysis['timing_ms'][level]:,.1f} ms")
    relationships = analysis["level4"]
    findings = [
        item
        for item in relationships.get("findings", [])
        if item.get("status") not in {"PASS", "NOT_APPLICABLE"}
    ]
    if findings:
        st.markdown("#### Prioritized findings")
        st.dataframe(
            [
                {
                    "Priority": item.get("priority"),
                    "Finding": item.get("name"),
                    "Status": item.get("status"),
                    "Explanation": item.get("explanation"),
                    "Recommendation": item.get("recommendation"),
                }
                for item in findings[:20]
            ],
            width="stretch",
            hide_index=True,
        )
    downloads = st.columns(3)
    stem = Path(filename).stem
    downloads[0].download_button(
        "Export complete JSON",
        json.dumps(analysis, indent=2, default=str).encode("utf-8"),
        file_name=f"{stem}-complete-analysis.json",
        mime="application/json",
        width="stretch",
    )
    downloads[1].download_button(
        "Export review CSV",
        report_csv,
        file_name=f"{stem}-review.csv",
        mime="text/csv",
        width="stretch",
    )
    downloads[2].download_button(
        "Download original PDF",
        pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        width="stretch",
    )


def render_analysis_workspace(
    analysis: dict[str, Any],
    pdf_bytes: bytes,
    filename: str,
    report_csv: bytes,
) -> None:
    """Render the five-level review workspace and synchronized PDF evidence preview."""
    drawing = analysis["level1"]
    validation = analysis["level2"]
    vision = analysis["level3"]
    relationships = analysis["level4"]
    page_count = int(_value(drawing.get("page_count")) or len(drawing.get("pages", [])) or 1)

    title = _display(drawing.get("drawing_number"))
    part_name = _display(drawing.get("part_name"))
    st.markdown(
        f"""
        <div class="analysis-shell">
          <div class="analysis-title-row">
            <div>
              <small>Drawing analysis · {_display(drawing.get("document_type"))}</small>
              <h1>{title}</h1>
              <p>{part_name} · {page_count} sheet(s) · evidence-linked automated review</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    actions = st.columns([0.22, 0.26, 0.13, 0.13, 0.13, 0.13])
    if actions[0].button("← New upload", key="new_drawing", width="stretch"):
        for key in list(st.session_state):
            if key.startswith("workspace_") or key in {
                "analysis",
                "file_digest",
                "pdf_bytes",
                "uploaded_filename",
            }:
                st.session_state.pop(key, None)
        st.rerun()
    if actions[1].button("Run complete analysis", key="rerun_analysis", width="stretch"):
        st.session_state["request_analysis_rerun"] = True
        st.rerun()
    actions[2].metric(
        "Fields",
        (drawing.get("level1_summary") or {}).get("extracted_field_count", 0),
    )
    actions[3].metric("Sheets", page_count)
    actions[4].metric("Issues", validation.get("summary", {}).get("failed", 0))
    actions[5].metric("Visual", vision.get("summary", {}).get("objects_detected", 0))

    levels = st.columns(4)
    levels[0].success("LEVEL 1 · COMPLETE")
    levels[1].success("LEVEL 2 · COMPLETE")
    levels[2].success("LEVEL 3 · COMPLETE")
    levels[3].success("LEVEL 4 · COMPLETE")

    preview_column, results_column = st.columns([1.15, 0.85], gap="small")
    with preview_column:
        with st.container(key="preview_panel"):
            _preview_panel(pdf_bytes, drawing, vision, page_count)
    with results_column:
        with st.container(key="results_panel"):
            drawing_tab, validation_tab, visual_tab, relationship_tab, report_tab = st.tabs(
                ["DRAWING", "VALIDATION", "VISUAL", "RELATIONSHIPS", "REPORT"]
            )
            with drawing_tab:
                _drawing_panel(drawing)
            with validation_tab:
                _validation_panel(validation)
            with visual_tab:
                _visual_panel(vision)
            with relationship_tab:
                _relationship_panel(relationships)
            with report_tab:
                _report_panel(analysis, pdf_bytes, filename, report_csv)

    st.caption(
        "Review assistance only · Missing evidence is not inferred · "
        "Final engineering approval remains human-controlled."
    )
