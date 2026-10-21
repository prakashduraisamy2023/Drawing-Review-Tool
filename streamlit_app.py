"""Streamlit entry point for browser-based Engineering Drawing Intelligence review."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import pymupdf as fitz
import streamlit as st

from backend.app.extraction import DrawingParser
from backend.app.relationships import RelationshipEngine
from backend.app.validation import ValidationEngine
from backend.app.vision import VisionEngine

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


st.set_page_config(
    page_title="Engineering Drawing Intelligence",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _field_value(document: dict[str, Any], field: str) -> Any:
    candidate = document.get(field)
    if isinstance(candidate, dict) and "value" in candidate:
        return candidate.get("value")
    return candidate


def _flatten_evidence(value: Any, path: str = "drawing") -> list[dict[str, Any]]:
    if isinstance(value, dict) and {"value", "confidence", "extraction_method"}.issubset(value):
        if value.get("value") is None:
            return []
        return [
            {
                "field": path,
                "value": str(value.get("value")),
                "page": value.get("page_number"),
                "confidence": value.get("confidence"),
                "method": value.get("extraction_method"),
            }
        ]
    if isinstance(value, dict):
        rows: list[dict[str, Any]] = []
        for key, child in value.items():
            rows.extend(_flatten_evidence(child, f"{path}.{key}"))
        return rows
    if isinstance(value, list):
        rows = []
        for index, child in enumerate(value):
            rows.extend(_flatten_evidence(child, f"{path}[{index}]"))
        return rows
    return []


def _table_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        row: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, dict) and "value" in value:
                row[key] = value.get("value")
            elif not isinstance(value, (dict, list)):
                row[key] = value
        rows.append(row)
    return rows


@st.cache_data(show_spinner=False)
def _pdf_page_count(pdf_bytes: bytes) -> int:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        return document.page_count


@st.cache_data(show_spinner=False)
def _render_pdf_page(pdf_bytes: bytes, page_index: int) -> bytes:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        page = document.load_page(page_index)
        matrix = fitz.Matrix(1.5, 1.5)
        return page.get_pixmap(matrix=matrix, alpha=False).tobytes("png")


def _validate_pdf(filename: str, payload: bytes) -> None:
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Select a PDF engineering drawing.")
    if not payload.startswith(b"%PDF"):
        raise ValueError("The uploaded file does not have a valid PDF signature.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("The PDF exceeds the 50 MB upload limit.")
    with fitz.open(stream=payload, filetype="pdf") as document:
        if document.page_count < 1:
            raise ValueError("The PDF contains no readable pages.")


def _run_complete_analysis(filename: str, payload: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    progress = st.progress(0, text="Preparing PDF")
    with tempfile.TemporaryDirectory(prefix="drawing-intelligence-") as temporary:
        source = Path(temporary) / Path(filename).name
        source.write_bytes(payload)

        level1_started = time.perf_counter()
        progress.progress(10, text="Level 1 — extracting drawing evidence")
        drawing = DrawingParser().parse(source)
        level1_ms = (time.perf_counter() - level1_started) * 1000

        progress.progress(32, text="Level 2 — running baseline checklist validation")
        validation_engine = ValidationEngine()
        baseline_validation = validation_engine.validate(drawing, drawing_id=digest[:12])

        progress.progress(48, text="Level 3 — detecting visual evidence")
        vision = VisionEngine().analyze(source, drawing, drawing_id=digest[:12])

        progress.progress(70, text="Level 2 — applying visual evidence")
        validation = validation_engine.validate(
            drawing,
            drawing_id=digest[:12],
            vision_report=vision,
        )

        progress.progress(84, text="Level 4 — evaluating engineering relationships")
        relationships = RelationshipEngine().analyze(
            drawing,
            drawing_id=digest[:12],
            validation_report=validation,
            vision_report=vision,
        )

    progress.progress(100, text="Automated review complete")
    return {
        "drawing_id": digest[:12],
        "source_filename": filename,
        "level1": drawing.model_dump(mode="json"),
        "level2_baseline": baseline_validation.model_dump(mode="json"),
        "level2": validation.model_dump(mode="json"),
        "level3": vision.model_dump(mode="json"),
        "level4": relationships.model_dump(mode="json"),
        "timing_ms": {
            "level1": round(level1_ms, 3),
            "level2": round(validation.timing.level2_validation_ms, 3),
            "level3": round(vision.timing.total_time_ms, 3),
            "level4": round(relationships.timing.level4_relationship_ms, 3),
        },
        "disclaimer": (
            "Automated engineering drawing review assistance only. Final approval remains "
            "with the authorized engineer."
        ),
    }


def _report_csv(analysis: dict[str, Any]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "level",
            "id",
            "name",
            "status",
            "severity",
            "priority",
            "confidence",
            "actual",
            "recommendation",
        ],
    )
    writer.writeheader()
    for result in analysis["level2"].get("results", []):
        writer.writerow(
            {
                "level": "LEVEL_2",
                "id": result.get("rule_id"),
                "name": result.get("rule_name"),
                "status": result.get("status"),
                "severity": result.get("severity"),
                "actual": result.get("actual_condition"),
                "recommendation": result.get("recommendation"),
            }
        )
    for result in analysis["level4"].get("findings", []):
        writer.writerow(
            {
                "level": "LEVEL_4",
                "id": result.get("relationship_rule_id"),
                "name": result.get("name"),
                "status": result.get("status"),
                "severity": result.get("severity"),
                "priority": result.get("priority"),
                "confidence": result.get("confidence"),
                "actual": result.get("actual_relationship"),
                "recommendation": result.get("recommendation"),
            }
        )
    return output.getvalue().encode("utf-8")


def _status_metrics(summary: dict[str, Any], labels: list[tuple[str, str]]) -> None:
    columns = st.columns(len(labels))
    for column, (key, label) in zip(columns, labels, strict=True):
        column.metric(label, summary.get(key, 0))


st.title("Engineering Drawing Intelligence")
st.caption("Levels 1–4 · Evidence extraction, validation, visual review, and relationships")

with st.sidebar:
    st.header("Review boundary")
    st.info(
        "Results are automated review assistance. Missing evidence is not inferred, and "
        "final engineering approval remains human-controlled."
    )
    st.markdown("**Multi-device access**")
    st.code("streamlit run streamlit_app.py --server.address 0.0.0.0", language="text")
    st.caption("Open the displayed Network URL from another device on the same network.")

uploaded = st.file_uploader("Upload an engineering drawing", type=["pdf"])
if uploaded is None:
    st.markdown("Upload a PDF to preview it and run the complete evidence-only review pipeline.")
    st.stop()

pdf_bytes = uploaded.getvalue()
try:
    _validate_pdf(uploaded.name, pdf_bytes)
except (ValueError, fitz.FileDataError) as error:
    st.error(str(error))
    st.stop()

digest = hashlib.sha256(pdf_bytes).hexdigest()
if st.session_state.get("file_digest") != digest:
    st.session_state["file_digest"] = digest
    st.session_state.pop("analysis", None)

preview_column, action_column = st.columns([1.25, 0.75], gap="large")
with preview_column:
    st.subheader("Drawing preview")
    page_count = _pdf_page_count(pdf_bytes)
    page_number = st.number_input(
        "Page",
        min_value=1,
        max_value=page_count,
        value=1,
        step=1,
    )
    st.image(
        _render_pdf_page(pdf_bytes, int(page_number) - 1),
        caption=f"{uploaded.name} · page {page_number} of {page_count}",
        width="stretch",
    )

with action_column:
    st.subheader("Complete analysis")
    st.write(f"**File:** {uploaded.name}")
    st.write(f"**Size:** {len(pdf_bytes) / 1024 / 1024:.2f} MB")
    st.write(f"**Pages:** {page_count}")
    if st.button("Run complete analysis", type="primary", width="stretch"):
        try:
            st.session_state["analysis"] = _run_complete_analysis(uploaded.name, pdf_bytes)
        except Exception as error:  # keep the interactive session available for diagnosis
            st.exception(error)
    st.download_button(
        "Download original PDF",
        data=pdf_bytes,
        file_name=uploaded.name,
        mime="application/pdf",
        width="stretch",
    )

analysis = st.session_state.get("analysis")
if analysis is None:
    st.stop()

drawing = analysis["level1"]
validation = analysis["level2"]
vision = analysis["level3"]
relationships = analysis["level4"]

st.divider()
st.subheader("Automated review summary")
summary_columns = st.columns(4)
summary_columns[0].metric("Level 1", "COMPLETE")
summary_columns[1].metric("Level 2", validation["summary"]["overall_status"])
summary_columns[2].metric("Level 3 objects", vision["summary"]["objects_detected"])
summary_columns[3].metric("Level 4", relationships["summary"]["overall_status"])

drawing_tab, validation_tab, visual_tab, relationship_tab, report_tab = st.tabs(
    ["Drawing", "Validation", "Visual", "Relationships", "Report"]
)

with drawing_tab:
    identity = {
        "Drawing number": _field_value(drawing, "drawing_number"),
        "Revision": _field_value(drawing, "revision"),
        "Part name": _field_value(drawing, "part_name"),
        "Document type": _field_value(drawing, "document_type"),
        "Units": _field_value(drawing, "units"),
        "Scale": _field_value(drawing, "scale"),
        "Pages": _field_value(drawing, "page_count"),
    }
    st.dataframe([identity], width="stretch", hide_index=True)
    for key, title in (
        ("revision_records", "Revision records"),
        ("notes", "Notes"),
        ("bom_items", "BOM items"),
        ("part_list_items", "Part-list items"),
        ("service_parts", "Service parts"),
        ("standard_references", "Standards"),
    ):
        items = drawing.get(key, [])
        if items:
            st.markdown(f"### {title}")
            st.dataframe(_table_rows(items), width="stretch", hide_index=True)
    with st.expander("Extraction evidence and provenance"):
        st.dataframe(
            _flatten_evidence(drawing),
            width="stretch",
            hide_index=True,
        )

with validation_tab:
    _status_metrics(
        validation["summary"],
        [
            ("passed", "Passed"),
            ("failed", "Failed"),
            ("warnings", "Warnings"),
            ("manual_review", "Manual review"),
            ("not_evaluated", "Not evaluated"),
        ],
    )
    validation_rows = [
        {
            "Rule": item.get("rule_id"),
            "Requirement": item.get("rule_name"),
            "Status": item.get("status"),
            "Severity": item.get("severity"),
            "Actual": item.get("actual_condition"),
            "Recommendation": item.get("recommendation"),
        }
        for item in validation.get("results", [])
    ]
    st.dataframe(validation_rows, width="stretch", hide_index=True)

with visual_tab:
    _status_metrics(
        vision["summary"],
        [
            ("pages_processed", "Pages"),
            ("objects_detected", "Objects"),
            ("low_confidence_count", "Low confidence"),
        ],
    )
    visual_rows = [
        {
            "Type": item.get("object_type"),
            "Page": item.get("page_number"),
            "Text": item.get("normalized_text") or item.get("raw_text"),
            "Confidence": item.get("confidence"),
            "Detector": item.get("detector"),
        }
        for item in vision.get("objects", [])
    ]
    if visual_rows:
        st.dataframe(visual_rows, width="stretch", hide_index=True)
    else:
        st.info("No visual objects were detected with the configured detectors.")

with relationship_tab:
    _status_metrics(
        relationships["summary"],
        [
            ("relationships_checked", "Checked"),
            ("passed", "Passed"),
            ("warnings", "Warnings"),
            ("manual_review", "Manual review"),
            ("not_evaluated", "Not evaluated"),
        ],
    )
    relationship_rows = [
        {
            "Priority": item.get("priority"),
            "Rule": item.get("relationship_rule_id"),
            "Finding": item.get("name"),
            "Status": item.get("status"),
            "Confidence": item.get("confidence"),
            "Actual": item.get("actual_relationship"),
            "Recommendation": item.get("recommendation"),
        }
        for item in relationships.get("findings", [])
    ]
    st.dataframe(relationship_rows, width="stretch", hide_index=True)
    graph = relationships.get("graph", {})
    st.caption(
        f"Relationship graph: {len(graph.get('nodes', []))} nodes · "
        f"{len(graph.get('edges', []))} edges"
    )
    with st.expander("Correlations"):
        st.json(relationships.get("correlations", []), expanded=False)

with report_tab:
    st.warning(analysis["disclaimer"])
    st.markdown("### Processing time")
    timing_columns = st.columns(4)
    for column, level in zip(timing_columns, ("level1", "level2", "level3", "level4"), strict=True):
        column.metric(level.replace("level", "Level "), f"{analysis['timing_ms'][level]:,.1f} ms")
    findings = [
        item
        for item in relationships.get("findings", [])
        if item.get("status") not in {"PASS", "NOT_APPLICABLE"}
    ]
    if findings:
        st.markdown("### Top findings")
        for item in findings[:10]:
            st.markdown(
                f"**{item.get('priority')} · {item.get('name')} — {item.get('status')}**  \n"
                f"{item.get('explanation')}"
            )
    export_columns = st.columns(2)
    export_columns[0].download_button(
        "Download complete JSON",
        data=json.dumps(analysis, indent=2, default=str).encode("utf-8"),
        file_name=f"{Path(uploaded.name).stem}-complete-analysis.json",
        mime="application/json",
        width="stretch",
    )
    export_columns[1].download_button(
        "Download review CSV",
        data=_report_csv(analysis),
        file_name=f"{Path(uploaded.name).stem}-review.csv",
        mime="text/csv",
        width="stretch",
    )
