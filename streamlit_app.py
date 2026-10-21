"""Streamlit entry point for browser-based Engineering Drawing Intelligence review."""
# ruff: noqa: E501 -- embedded CSS mirrors the original frontend design tokens.

from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import time
from html import escape
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
    initial_sidebar_state="collapsed",
)


def _inject_original_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #18211e; --muted: #77817c; --line: #d9ded9;
            --line-strong: #c8cec8; --surface: #ffffff; --dark: #111917;
            --accent: #b8ed42; --accent-deep: #729c13; --blueprint: #2f6558;
        }
        *, *::before, *::after { box-sizing: border-box; }
        html, body, [class*="css"] { font-family: Inter, "Segoe UI", Helvetica, Arial, sans-serif; }
        body { background: #eef1ed; }
        [data-testid="stAppViewContainer"], .stApp { background: #eef1ed; color: var(--ink); }
        html, body, .stApp { overflow-x: hidden; }
        [data-testid="stHeader"], [data-testid="stSidebar"], #MainMenu,
        [data-testid="stToolbar"], footer { display: none !important; }
        [data-testid="stAppViewBlockContainer"], .block-container {
            max-width: none !important; padding: 0 !important;
        }
        .original-topbar {
            min-height: 88px; padding: 0 clamp(20px, 4vw, 72px); display: flex;
            align-items: center; justify-content: space-between; gap: 28px;
            color: #edf2ee; background: var(--dark); border-bottom: 1px solid #2a3531;
        }
        .original-brand { display: inline-flex; align-items: center; gap: 16px; white-space: nowrap; }
        .original-brand__mark {
            width: 50px; height: 50px; display: grid; place-items: center;
            color: var(--dark); background: var(--accent);
            font: 800 16px/1 "SFMono-Regular", Consolas, monospace; letter-spacing: .06em;
            clip-path: polygon(0 0, 76% 0, 100% 24%, 100% 100%, 0 100%);
        }
        .original-brand__name { font-size: 20px; font-weight: 750; letter-spacing: -.02em; }
        .original-topbar__status {
            display: flex; align-items: center; gap: 10px; color: #aab4af;
            font: 700 13px/1.5 "SFMono-Regular", Consolas, monospace;
            letter-spacing: .12em; text-transform: uppercase; text-align: right;
        }
        .original-topbar__status::before {
            content: ""; width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%;
            background: var(--accent); box-shadow: 0 0 0 5px rgba(184, 237, 66, .1);
        }
        .st-key-upload_shell {
            max-width: 1560px; margin: 0 auto;
            padding: clamp(52px, 8vw, 130px) clamp(24px, 8vw, 145px) 52px;
        }
        .st-key-upload_shell > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
            align-items: center; gap: clamp(54px, 8vw, 125px);
        }
        .original-kicker {
            display: inline-flex; align-items: center; gap: 13px; color: #57615c;
            font: 700 12px/1 "SFMono-Regular", Consolas, monospace;
            letter-spacing: .12em; text-transform: uppercase;
        }
        .original-kicker::before { content: ""; width: 34px; height: 2px; background: var(--accent-deep); }
        .original-hero h1 {
            margin: 42px 0 34px; color: #121a17;
            font-size: clamp(58px, 6.7vw, 100px); font-weight: 680;
            letter-spacing: -.065em; line-height: .94;
        }
        .original-hero h1 em { color: var(--blueprint); font-style: normal; font-weight: 470; }
        .original-hero__mobile-break { display: none; }
        .original-hero p { max-width: 760px; margin: 0; color: #66716b; font-size: 20px; line-height: 1.72; }
        .original-principles { margin-top: 40px; display: flex; gap: 12px; flex-wrap: wrap; }
        .original-principles span {
            padding: 12px 15px; color: #4f5b55; background: rgba(255,255,255,.58);
            border: 1px solid var(--line);
            font: 650 11px/1 "SFMono-Regular", Consolas, monospace;
            letter-spacing: .04em; text-transform: uppercase;
        }
        .st-key-upload_card {
            padding: 26px !important; background: var(--surface) !important;
            border: 1px solid var(--line-strong) !important; border-radius: 0 !important;
            box-shadow: 0 26px 70px rgba(24, 33, 30, .11);
        }
        .original-card-header { margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center; }
        .original-card-header > div { display: flex; align-items: center; gap: 14px; }
        .original-card-header h2 { margin: 0; color: #121a17; font-size: 21px; letter-spacing: -.025em; }
        .original-step { color: var(--accent-deep); font: 700 11px "SFMono-Regular", Consolas, monospace; }
        .original-chip { color: #7a837e; font: 650 10px "SFMono-Regular", Consolas, monospace; letter-spacing: .07em; }
        .st-key-upload_card [data-testid="stFileUploader"] { margin: 0; }
        .st-key-upload_card [data-testid="stFileUploaderDropzone"] {
            min-height: 300px; padding: 38px 24px; justify-content: center;
            background: #f7f9f6; border: 1px dashed #b8c0ba; border-radius: 0;
        }
        .st-key-upload_card [data-testid="stFileUploaderDropzone"] > div { align-items: center; text-align: center; }
        .st-key-upload_card [data-testid="stFileUploaderDropzone"] svg { color: var(--blueprint); }
        .st-key-upload_card [data-testid="stFileUploaderDropzone"] button {
            color: var(--blueprint); background: transparent; border: 1px solid #8fa199; border-radius: 0;
        }
        .st-key-analyze_button button {
            width: 100%; min-height: 66px; margin-top: 10px; border-radius: 0;
            border: 1px solid var(--dark); color: #f1f5f2; background: var(--dark);
            font-size: 17px; font-weight: 750;
        }
        .st-key-analyze_button button:hover:not(:disabled) { color: white; background: #26312d; border-color: #26312d; }
        .original-privacy { margin: 15px 0 0; color: #89918d; font-size: 11px; text-align: center; }
        .original-workflow {
            max-width: 1560px; margin: 0 auto 58px; padding: 0 clamp(24px, 8vw, 145px);
            display: grid; grid-template-columns: repeat(3, 1fr);
        }
        .original-workflow > div {
            padding: 24px 0; display: grid; grid-template-columns: 44px 1fr; gap: 4px 13px;
            border-top: 1px solid var(--line-strong); border-bottom: 1px solid var(--line-strong);
        }
        .original-workflow > div + div { padding-left: 28px; border-left: 1px solid var(--line-strong); }
        .original-workflow span { grid-row: span 2; color: #86908a; font: 700 11px "SFMono-Regular", Consolas, monospace; }
        .original-workflow strong { font-size: 13px; }
        .original-workflow small { color: var(--muted); font-size: 11px; }
        .original-footer {
            min-height: 72px; padding: 0 clamp(20px, 4vw, 72px); display: flex;
            align-items: center; justify-content: space-between; gap: 24px;
            color: #7e8882; font: 600 10px/1.5 "SFMono-Regular", Consolas, monospace;
            letter-spacing: .08em; text-transform: uppercase;
        }
        .analysis-shell { padding: 28px clamp(18px, 3vw, 48px) 0; }
        .analysis-title-row { display: flex; justify-content: space-between; align-items: end; gap: 20px; }
        .analysis-title-row small { color: var(--blueprint); font: 700 10px "SFMono-Regular", Consolas, monospace; text-transform: uppercase; }
        .analysis-title-row h1 { margin: 8px 0 4px; color: #121a17; font-size: clamp(28px, 3vw, 42px); letter-spacing: -.045em; }
        .analysis-title-row p { margin: 0; color: #6d7772; }
        div[data-testid="stTabs"] button[role="tab"] { font-weight: 720; }
        div[data-testid="stMetric"] { background: #f5f7f4; border: 1px solid var(--line); padding: 12px; }
        .stButton button, .stDownloadButton button { border-radius: 0; }
        @media (max-width: 1000px) {
            .original-topbar { align-items: flex-start; flex-direction: column; padding-top: 18px; padding-bottom: 18px; }
            .original-topbar__status { text-align: left; font-size: 10px; }
            .st-key-upload_shell { padding-top: 54px; }
            .st-key-upload_shell > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] { flex-direction: column; }
            .st-key-upload_shell [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
        }
        @media (max-width: 620px) {
            .original-brand__name { font-size: 15px; }
            .original-brand__mark { width: 40px; height: 40px; }
            .original-topbar__status { display: none; }
            .original-hero h1 { font-size: 48px; }
            .original-hero__mobile-break { display: block; }
            .original-hero p { font-size: 16px; }
            .st-key-upload_shell { max-width: 100vw; padding: 42px 18px 28px; overflow: hidden; }
            .st-key-upload_shell [data-testid="stHorizontalBlock"],
            .st-key-upload_shell [data-testid="column"] { min-width: 0 !important; }
            .st-key-upload_card {
                width: 100% !important; max-width: 100% !important;
                margin: 0 !important; padding: 20px !important;
            }
            .st-key-upload_card > div,
            .st-key-upload_card [data-testid="stFileUploader"],
            .st-key-upload_card [data-testid="stFileUploaderDropzone"] {
                width: 100% !important; min-width: 0 !important; max-width: 100% !important;
            }
            .original-principles span { padding: 10px 11px; font-size: 9px; }
            .original-card-header { gap: 12px; }
            .original-chip { display: none; }
            .original-workflow { padding: 0 18px; grid-template-columns: 1fr; }
            .original-workflow > div + div { padding-left: 0; border-left: 0; border-top: 0; }
            .original-footer { align-items: flex-start; flex-direction: column; justify-content: center; padding-top: 18px; padding-bottom: 18px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _topbar() -> None:
    st.markdown(
        """
        <header class="original-topbar">
          <div class="original-brand">
            <span class="original-brand__mark">DI</span>
            <span class="original-brand__name">Engineering Drawing Intelligence</span>
          </div>
          <div class="original-topbar__status">
            Level 1 extraction &nbsp;·&nbsp; Level 2 validation &nbsp;·&nbsp;
            Level 3 visual intelligence &nbsp;·&nbsp; Level 4 relationship intelligence
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _footer() -> None:
    st.markdown(
        """
        <div class="original-footer">
          <span>Level-1 extraction · Level-2 checklist validation · Level-3 visual intelligence · Level-4 relationship intelligence</span>
          <span>Review assistance only · Final engineering approval remains human.</span>
        </div>
        """,
        unsafe_allow_html=True,
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


_inject_original_theme()
_topbar()

analysis = st.session_state.get("analysis")
if analysis is not None and not {"pdf_bytes", "uploaded_filename"}.issubset(st.session_state):
    st.session_state.pop("analysis", None)
    analysis = None
if analysis is None:
    with st.container(key="upload_shell"):
        hero_column, card_column = st.columns([1.08, 0.92], gap="large")
        with hero_column:
            st.markdown(
                """
                <section class="original-hero">
                  <span class="original-kicker">Level 1 – PDF Extraction</span>
                  <h1>Engineering<span class="original-hero__mobile-break"></span> drawings,<br><em>made legible.</em></h1>
                  <p>
                    Convert drawing PDFs into traceable structured data. Every extracted value
                    remains connected to its page, source region, method, and confidence.
                  </p>
                  <div class="original-principles">
                    <span>Native text first</span><span>Spatial evidence</span><span>No inferred values</span>
                  </div>
                </section>
                """,
                unsafe_allow_html=True,
            )
        with card_column:
            with st.container(border=True, key="upload_card"):
                st.markdown(
                    """
                    <div class="original-card-header">
                      <div><span class="original-step">01</span><h2>Upload drawing</h2></div>
                      <span class="original-chip">PDF · MAX 50 MB</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                uploaded = st.file_uploader(
                    "Drop a drawing PDF here",
                    type=["pdf"],
                    label_visibility="collapsed",
                )
                upload_error: str | None = None
                pdf_bytes = b""
                if uploaded is not None:
                    pdf_bytes = uploaded.getvalue()
                    try:
                        _validate_pdf(uploaded.name, pdf_bytes)
                    except (ValueError, fitz.FileDataError) as error:
                        upload_error = str(error)
                        st.error(upload_error)

                if st.button(
                    "↗  Analyze drawing",
                    type="primary",
                    width="stretch",
                    disabled=uploaded is None or upload_error is not None,
                    key="analyze_button",
                ):
                    try:
                        digest = hashlib.sha256(pdf_bytes).hexdigest()
                        st.session_state["file_digest"] = digest
                        st.session_state["pdf_bytes"] = pdf_bytes
                        st.session_state["uploaded_filename"] = uploaded.name
                        st.session_state["analysis"] = _run_complete_analysis(
                            uploaded.name, pdf_bytes
                        )
                        st.rerun()
                    except (
                        Exception
                    ) as error:  # keep the interactive session available for diagnosis
                        st.exception(error)
                st.markdown(
                    '<p class="original-privacy">Your file is processed under an opaque drawing ID for this PoC.</p>',
                    unsafe_allow_html=True,
                )

    st.markdown(
        """
        <section class="original-workflow" aria-label="Extraction pipeline">
          <div><span>01</span><strong>Inspect</strong><small>PDF structure</small></div>
          <div><span>02</span><strong>Extract</strong><small>Text + coordinates</small></div>
          <div><span>03</span><strong>Structure</strong><small>Level-1 JSON</small></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    _footer()
    st.stop()

pdf_bytes = st.session_state["pdf_bytes"]
uploaded_filename = st.session_state["uploaded_filename"]
page_count = _pdf_page_count(pdf_bytes)

with st.container(key="analysis_header"):
    st.markdown(
        f"""
        <div class="analysis-shell">
          <div class="analysis-title-row">
            <div>
              <small>Automated review workspace · Drawing {analysis["drawing_id"]}</small>
              <h1>{escape(uploaded_filename)}</h1>
              <p>Evidence remains linked to page, confidence, and extraction method.</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("← Analyze another drawing", key="new_drawing"):
        for key in ("analysis", "file_digest", "pdf_bytes", "uploaded_filename"):
            st.session_state.pop(key, None)
        st.rerun()

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
        file_name=f"{Path(uploaded_filename).stem}-complete-analysis.json",
        mime="application/json",
        width="stretch",
    )
    export_columns[1].download_button(
        "Download review CSV",
        data=_report_csv(analysis),
        file_name=f"{Path(uploaded_filename).stem}-review.csv",
        mime="text/csv",
        width="stretch",
    )
