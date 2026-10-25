from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

import pymupdf
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api_models import DrawingUploadResponse
from backend.app.config import Settings, get_settings
from backend.app.drawing_store import DrawingNotFoundError, DrawingStorageError, DrawingStore
from backend.app.extraction import DrawingExtractionPipeline, DrawingParser
from backend.app.extraction.document import ocr_available
from backend.app.models.drawing import (
    BOMItem,
    DrawingDocument,
    DrawingNote,
    DrawingPage,
    RevisionRecord,
    StandardReference,
    SupplierInfo,
)
from backend.app.relationships import RelationshipEngine
from backend.app.relationships.models import (
    CompleteAnalysisReport,
    RelationshipGraph,
    RelationshipReport,
    RelationshipResult,
    RelationshipSummary,
)
from backend.app.schemas import BatchExtractionResponse, DrawingExtraction
from backend.app.validation import ValidationEngine
from backend.app.validation.models import (
    RuleMetadata,
    ValidationReport,
    ValidationResult,
    ValidationSummary,
)
from backend.app.vision import VisionEngine
from backend.app.vision.models import VisionReport, VisionSummary, VisualObject, VisualReview

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


def get_api_settings() -> Settings:
    return settings


SettingsDependency = Annotated[Settings, Depends(get_api_settings)]


def get_drawing_store(current_settings: SettingsDependency) -> Iterator[DrawingStore]:
    if current_settings.storage_backend == "local":
        yield DrawingStore(current_settings.storage_dir)
    else:
        from backend.app.gcs_drawing_store import GCSDrawingStore

        with TemporaryDirectory(prefix="drawing-processing-") as directory:
            store = GCSDrawingStore(current_settings.gcs_bucket, directory)
            try:
                yield store
            finally:
                store.close()


def get_drawing_parser() -> DrawingParser:
    return DrawingParser()


StoreDependency = Annotated[DrawingStore, Depends(get_drawing_store)]
ParserDependency = Annotated[DrawingParser, Depends(get_drawing_parser)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s", settings.app_name)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Level-1 evidence extraction, separate Level-2 validation, local Level-3 "
        "visual evidence, and Level-4 relationship intelligence."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(DrawingStorageError)
async def drawing_storage_error(_: Request, exc: DrawingStorageError) -> JSONResponse:
    logger.error("Drawing storage operation failed", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Drawing storage is unavailable."})


def _discard_failed_upload(store: DrawingStore, drawing_id: str) -> None:
    try:
        store.discard(drawing_id)
    except DrawingStorageError:
        logger.exception("Unable to remove failed drawing %s", drawing_id)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "ocr_enabled": settings.ocr_enabled,
        "ocr_available": ocr_available(),
        "level3_enabled": settings.level3_enabled,
        "level4_enabled": settings.level4_enabled,
        "demo_mode": settings.demo_mode,
        "ocr_provider": settings.ocr_provider,
    }


async def _persist_upload(upload: UploadFile, directory: Path) -> Path:
    filename = Path(upload.filename or "drawing.pdf").name
    if Path(filename).suffix.lower() != ".pdf" or upload.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )
    target = directory / filename
    total = 0
    with target.open("wb") as stream:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"PDF exceeds the {settings.max_upload_bytes}-byte upload limit.",
                )
            stream.write(chunk)
    await upload.close()
    with target.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The uploaded file does not have a valid PDF signature.",
            )
    return target


def _safe_upload_filename(filename: str | None) -> str:
    normalized = (filename or "drawing.pdf").replace("\\", "/")
    return normalized.rsplit("/", maxsplit=1)[-1] or "drawing.pdf"


def _validate_pdf(path: Path) -> None:
    try:
        with pymupdf.open(stream=path.read_bytes(), filetype="pdf") as document:
            if document.needs_pass:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Password-protected PDFs are not supported.",
                )
            if document.page_count < 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The PDF does not contain any pages.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file is not a readable PDF.",
        ) from exc


async def _save_drawing_upload(
    upload: UploadFile,
    store: DrawingStore,
    max_upload_bytes: int,
) -> tuple[str, Path, str]:
    filename = _safe_upload_filename(upload.filename)
    if upload.content_type != "application/pdf":
        await upload.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload MIME type must be application/pdf.",
        )
    if Path(filename).suffix.lower() != ".pdf":
        await upload.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )

    drawing_id, partial_path = store.create_record()
    total = 0
    try:
        with partial_path.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"PDF exceeds the {max_upload_bytes}-byte upload limit.",
                    )
                stream.write(chunk)
        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The uploaded PDF is empty.",
            )
        with partial_path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The uploaded file does not have a valid PDF signature.",
                )
        await run_in_threadpool(_validate_pdf, partial_path)
        source = await run_in_threadpool(store.finalize_source, drawing_id)
        return drawing_id, source, filename
    except Exception:
        await run_in_threadpool(_discard_failed_upload, store, drawing_id)
        raise
    finally:
        await upload.close()


def _stored_document(drawing_id: str, store: DrawingStore) -> DrawingDocument:
    try:
        return store.load_result(drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drawing not found.",
        ) from exc


def _stored_validation(drawing_id: str, store: DrawingStore) -> ValidationReport:
    try:
        return store.load_validation(drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation has not been run for this drawing.",
        ) from exc


def _stored_vision(drawing_id: str, store: DrawingStore) -> VisionReport:
    try:
        return store.load_vision(drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Level-3 visual analysis has not been run for this drawing.",
        ) from exc


def _stored_relationships(drawing_id: str, store: DrawingStore) -> RelationshipReport:
    try:
        return store.load_relationships(drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Level-4 relationship analysis has not been run for this drawing.",
        ) from exc


@app.post(
    "/api/drawings/upload",
    response_model=DrawingUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_drawing(
    file: UploadFile,
    store: StoreDependency,
    parser: ParserDependency,
    current_settings: SettingsDependency,
) -> DrawingUploadResponse:
    drawing_id, source, filename = await _save_drawing_upload(
        file,
        store,
        current_settings.max_upload_bytes,
    )
    try:
        drawing = await run_in_threadpool(partial(parser.parse, source, source_filename=filename))
        await run_in_threadpool(store.save_result, drawing_id, drawing)
    except DrawingStorageError:
        await run_in_threadpool(_discard_failed_upload, store, drawing_id)
        raise
    except Exception as exc:
        await run_in_threadpool(_discard_failed_upload, store, drawing_id)
        logger.exception("Drawing processing failed for %s", drawing_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unable to process this PDF.",
        ) from exc
    return DrawingUploadResponse(id=drawing_id, drawing=drawing)


@app.get("/api/drawings/{drawing_id}", response_model=DrawingDocument)
def get_drawing(drawing_id: str, store: StoreDependency) -> DrawingDocument:
    return _stored_document(drawing_id, store)


@app.get("/api/drawings/{drawing_id}/source")
def get_drawing_source(drawing_id: str, store: StoreDependency) -> FileResponse:
    _stored_document(drawing_id, store)
    try:
        source = store.source_path(drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Drawing source PDF was not found.") from exc
    return FileResponse(
        source,
        media_type="application/pdf",
        filename=f"drawing-{drawing_id}.pdf",
        headers={"Cache-Control": "private, no-store"},
    )


@app.get("/api/drawings/{drawing_id}/vision/evidence/{filename}")
def get_drawing_visual_evidence(
    drawing_id: str, filename: str, store: StoreDependency
) -> FileResponse:
    _stored_document(drawing_id, store)
    try:
        evidence = store.evidence_path(drawing_id, filename)
    except DrawingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Visual evidence was not found.") from exc
    return FileResponse(
        evidence,
        media_type="image/png",
        filename=filename,
        headers={"Cache-Control": "private, no-store"},
    )


@app.get("/api/drawings/{drawing_id}/pages", response_model=list[DrawingPage])
def get_drawing_pages(drawing_id: str, store: StoreDependency) -> list[DrawingPage]:
    return _stored_document(drawing_id, store).pages or []


@app.get("/api/drawings/{drawing_id}/notes", response_model=list[DrawingNote])
def get_drawing_notes(drawing_id: str, store: StoreDependency) -> list[DrawingNote]:
    return _stored_document(drawing_id, store).notes or []


@app.get("/api/drawings/{drawing_id}/bom", response_model=list[BOMItem])
def get_drawing_bom(drawing_id: str, store: StoreDependency) -> list[BOMItem]:
    return _stored_document(drawing_id, store).bom or []


@app.get(
    "/api/drawings/{drawing_id}/revisions",
    response_model=list[RevisionRecord],
)
def get_drawing_revisions(
    drawing_id: str,
    store: StoreDependency,
) -> list[RevisionRecord]:
    return _stored_document(drawing_id, store).revisions or []


@app.get(
    "/api/drawings/{drawing_id}/standards",
    response_model=list[StandardReference],
)
def get_drawing_standards(
    drawing_id: str,
    store: StoreDependency,
) -> list[StandardReference]:
    return _stored_document(drawing_id, store).standard_references or []


@app.get(
    "/api/drawings/{drawing_id}/supplier",
    response_model=SupplierInfo,
)
def get_drawing_supplier(
    drawing_id: str,
    store: StoreDependency,
) -> SupplierInfo:
    return _stored_document(drawing_id, store).supplier_info or SupplierInfo()


@app.get("/api/drawings/{drawing_id}/export/json")
def export_drawing_json(drawing_id: str, store: StoreDependency) -> Response:
    drawing = _stored_document(drawing_id, store)
    return Response(
        content=drawing.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="drawing-{drawing_id}.json"'},
    )


def _flatten_csv_evidence(value: object, path: str = "") -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if isinstance(value, dict):
        if {"value", "confidence", "extraction_method"}.issubset(value):
            rows.append(
                {
                    "path": path,
                    "value": value.get("value"),
                    "page_number": value.get("page_number"),
                    "confidence": value.get("confidence"),
                    "confidence_category": value.get("confidence_category"),
                    "extraction_method": value.get("extraction_method"),
                    "bounding_box": value.get("bounding_box"),
                    "raw_text": value.get("raw_text"),
                    "evidence_anchor": value.get("evidence_anchor"),
                }
            )
        else:
            for key, item in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                rows.extend(_flatten_csv_evidence(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_flatten_csv_evidence(item, f"{path}[{index}]"))
    return rows


@app.get("/api/drawings/{drawing_id}/export/csv")
def export_drawing_csv(drawing_id: str, store: StoreDependency) -> Response:
    drawing = _stored_document(drawing_id, store)
    output = io.StringIO(newline="")
    columns = [
        "path",
        "value",
        "page_number",
        "confidence",
        "confidence_category",
        "extraction_method",
        "bounding_box",
        "raw_text",
        "evidence_anchor",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(_flatten_csv_evidence(drawing.model_dump(mode="json")))
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drawing-{drawing_id}.csv"'},
    )


@app.post("/api/drawings/{drawing_id}/validate", response_model=ValidationReport)
async def validate_drawing(drawing_id: str, store: StoreDependency) -> ValidationReport:
    drawing = await run_in_threadpool(_stored_document, drawing_id, store)
    try:
        vision = await run_in_threadpool(store.load_vision, drawing_id)
    except DrawingNotFoundError:
        vision = None
    engine = ValidationEngine()
    report = await run_in_threadpool(
        partial(engine.validate, drawing, drawing_id=drawing_id, vision_report=vision)
    )
    await run_in_threadpool(store.save_validation, drawing_id, report)
    return report


@app.post("/api/drawings/{drawing_id}/vision/analyze", response_model=VisionReport)
async def analyze_drawing_vision(
    drawing_id: str,
    store: StoreDependency,
    current_settings: SettingsDependency,
) -> VisionReport:
    drawing = await run_in_threadpool(_stored_document, drawing_id, store)
    try:
        source = await run_in_threadpool(store.source_path, drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Drawing source PDF was not found.") from exc
    engine = VisionEngine(settings=current_settings)
    debug_directory = (
        store.debug_directory(drawing_id) if current_settings.vision_debug_overlays else None
    )
    report = await run_in_threadpool(
        partial(
            engine.analyze,
            source,
            drawing,
            drawing_id=drawing_id,
            debug_directory=debug_directory,
        )
    )
    await run_in_threadpool(store.save_vision, drawing_id, report)
    return report


@app.get("/api/drawings/{drawing_id}/vision", response_model=VisionReport)
def get_drawing_vision(drawing_id: str, store: StoreDependency) -> VisionReport:
    return _stored_vision(drawing_id, store)


@app.get("/api/drawings/{drawing_id}/vision/summary", response_model=VisionSummary)
def get_drawing_vision_summary(drawing_id: str, store: StoreDependency) -> VisionSummary:
    return _stored_vision(drawing_id, store).summary


@app.get("/api/drawings/{drawing_id}/vision/objects", response_model=list[VisualObject])
def get_drawing_vision_objects(drawing_id: str, store: StoreDependency) -> list[VisualObject]:
    return _stored_vision(drawing_id, store).objects


@app.get(
    "/api/drawings/{drawing_id}/vision/objects/{object_id}",
    response_model=VisualObject,
)
def get_drawing_vision_object(
    drawing_id: str,
    object_id: str,
    store: StoreDependency,
) -> VisualObject:
    report = _stored_vision(drawing_id, store)
    for item in report.objects:
        if item.object_id == object_id:
            return item
    raise HTTPException(status_code=404, detail="Visual object not found.")


@app.post(
    "/api/drawings/{drawing_id}/vision/objects/{object_id}/review",
    response_model=VisualReview,
)
def review_drawing_vision_object(
    drawing_id: str,
    object_id: str,
    review: VisualReview,
    store: StoreDependency,
) -> VisualReview:
    report = _stored_vision(drawing_id, store)
    if review.object_id != object_id:
        raise HTTPException(status_code=422, detail="Review object ID does not match the route.")
    if not any(item.object_id == object_id for item in report.objects):
        raise HTTPException(status_code=404, detail="Visual object not found.")
    store.append_visual_review(drawing_id, review)
    return review


@app.get("/api/drawings/{drawing_id}/vision/reviews", response_model=list[VisualReview])
def get_drawing_vision_reviews(
    drawing_id: str,
    store: StoreDependency,
) -> list[VisualReview]:
    _stored_document(drawing_id, store)
    return store.load_visual_reviews(drawing_id)


@app.get("/api/drawings/{drawing_id}/vision/export/json")
def export_drawing_vision_json(drawing_id: str, store: StoreDependency) -> Response:
    report = _stored_vision(drawing_id, store)
    return Response(
        content=report.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="drawing-{drawing_id}-vision.json"'},
    )


@app.post(
    "/api/drawings/{drawing_id}/relationships/analyze",
    response_model=RelationshipReport,
)
async def analyze_drawing_relationships(
    drawing_id: str,
    store: StoreDependency,
    current_settings: SettingsDependency,
) -> RelationshipReport:
    if not current_settings.level4_enabled:
        raise HTTPException(status_code=503, detail="Level 4 is disabled by configuration.")
    drawing = await run_in_threadpool(_stored_document, drawing_id, store)
    try:
        validation = await run_in_threadpool(store.load_validation, drawing_id)
    except DrawingNotFoundError:
        validation = None
    try:
        vision = await run_in_threadpool(store.load_vision, drawing_id)
    except DrawingNotFoundError:
        vision = None
    report = await run_in_threadpool(
        partial(
            RelationshipEngine().analyze,
            drawing,
            drawing_id=drawing_id,
            validation_report=validation,
            vision_report=vision,
        )
    )
    await run_in_threadpool(store.save_relationships, drawing_id, report)
    return report


@app.get("/api/drawings/{drawing_id}/relationships", response_model=RelationshipReport)
def get_drawing_relationships(drawing_id: str, store: StoreDependency) -> RelationshipReport:
    return _stored_relationships(drawing_id, store)


@app.get(
    "/api/drawings/{drawing_id}/relationships/summary",
    response_model=RelationshipSummary,
)
def get_drawing_relationship_summary(
    drawing_id: str, store: StoreDependency
) -> RelationshipSummary:
    return _stored_relationships(drawing_id, store).summary


@app.get(
    "/api/drawings/{drawing_id}/relationships/findings",
    response_model=list[RelationshipResult],
)
def get_drawing_relationship_findings(
    drawing_id: str, store: StoreDependency
) -> list[RelationshipResult]:
    return _stored_relationships(drawing_id, store).findings


@app.get(
    "/api/drawings/{drawing_id}/relationships/graph",
    response_model=RelationshipGraph,
)
def get_drawing_relationship_graph(drawing_id: str, store: StoreDependency) -> RelationshipGraph:
    return _stored_relationships(drawing_id, store).graph


@app.get("/api/drawings/{drawing_id}/relationships/export/json")
def export_drawing_relationships_json(drawing_id: str, store: StoreDependency) -> Response:
    report = _stored_relationships(drawing_id, store)
    return Response(
        content=report.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="drawing-{drawing_id}-relationships.json"'
        },
    )


def _build_complete_report(
    drawing_id: str,
    drawing: DrawingDocument,
    validation: ValidationReport,
    vision: VisionReport,
    relationships: RelationshipReport,
) -> CompleteAnalysisReport:
    if (
        validation.summary.overall_status == "FAIL"
        or relationships.summary.overall_status == "FAIL"
    ):
        final_status = "FAIL"
    elif (
        validation.summary.overall_status == "REVIEW_REQUIRED"
        or relationships.summary.overall_status == "REVIEW_REQUIRED"
    ):
        final_status = "REVIEW_REQUIRED"
    elif (
        validation.summary.overall_status == "PASS_WITH_WARNINGS"
        or relationships.summary.overall_status == "PASS_WITH_WARNINGS"
    ):
        final_status = "PASS_WITH_WARNINGS"
    else:
        final_status = "PASS"
    timing = {
        "level1": validation.timing.level1_processing_ms,
        "level2": validation.timing.level2_validation_ms,
        "level3": vision.timing.total_time_ms,
        "level4": relationships.timing.level4_relationship_ms,
    }
    available = [value for value in timing.values() if value is not None]
    timing["total"] = sum(available)
    return CompleteAnalysisReport(
        drawing_id=drawing_id,
        level1_status="COMPLETE",
        level2_status="COMPLETE",
        level3_status="COMPLETE",
        level4_status="COMPLETE",
        validation_summary=validation.summary.model_dump(mode="json"),
        vision_summary=vision.summary.model_dump(mode="json"),
        relationship_summary=relationships.summary,
        level1_summary=(
            drawing.level1_summary.model_dump(mode="json") if drawing.level1_summary else {}
        ),
        top_findings=[
            item for item in relationships.findings if item.status not in {"PASS", "NOT_APPLICABLE"}
        ][:10],
        timing_ms=timing,
        final_system_status=final_status,
    )


@app.post(
    "/api/drawings/{drawing_id}/analysis/complete",
    response_model=CompleteAnalysisReport,
)
async def run_complete_analysis(
    drawing_id: str,
    store: StoreDependency,
    current_settings: SettingsDependency,
) -> CompleteAnalysisReport:
    if not current_settings.level3_enabled or not current_settings.level4_enabled:
        raise HTTPException(
            status_code=503,
            detail="Complete analysis requires Level 3 and Level 4 to be enabled.",
        )
    drawing = await run_in_threadpool(_stored_document, drawing_id, store)
    try:
        source = await run_in_threadpool(store.source_path, drawing_id)
    except DrawingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Drawing source PDF was not found.") from exc

    debug_directory = (
        store.debug_directory(drawing_id) if current_settings.vision_debug_overlays else None
    )

    base_validation = await run_in_threadpool(
        partial(ValidationEngine().validate, drawing, drawing_id=drawing_id)
    )
    vision = await run_in_threadpool(
        partial(
            VisionEngine(settings=current_settings).analyze,
            source,
            drawing,
            drawing_id=drawing_id,
            debug_directory=debug_directory,
        )
    )
    validation = await run_in_threadpool(
        partial(
            ValidationEngine().validate,
            drawing,
            drawing_id=drawing_id,
            vision_report=vision,
        )
    )
    relationships = await run_in_threadpool(
        partial(
            RelationshipEngine().analyze,
            drawing,
            drawing_id=drawing_id,
            validation_report=validation,
            vision_report=vision,
        )
    )
    await run_in_threadpool(store.save_validation, drawing_id, base_validation)
    await run_in_threadpool(store.save_vision, drawing_id, vision)
    await run_in_threadpool(store.save_validation, drawing_id, validation)
    await run_in_threadpool(store.save_relationships, drawing_id, relationships)
    return _build_complete_report(drawing_id, drawing, validation, vision, relationships)


@app.get("/api/drawings/{drawing_id}/report", response_model=CompleteAnalysisReport)
def get_complete_analysis_report(drawing_id: str, store: StoreDependency) -> CompleteAnalysisReport:
    return _build_complete_report(
        drawing_id,
        _stored_document(drawing_id, store),
        _stored_validation(drawing_id, store),
        _stored_vision(drawing_id, store),
        _stored_relationships(drawing_id, store),
    )


@app.get("/api/drawings/{drawing_id}/report/export/json")
def export_complete_analysis_json(drawing_id: str, store: StoreDependency) -> Response:
    drawing = _stored_document(drawing_id, store)
    validation = _stored_validation(drawing_id, store)
    vision = _stored_vision(drawing_id, store)
    relationships = _stored_relationships(drawing_id, store)
    payload = {
        "report": _build_complete_report(
            drawing_id, drawing, validation, vision, relationships
        ).model_dump(mode="json"),
        "level1": drawing.model_dump(mode="json"),
        "level2": validation.model_dump(mode="json"),
        "level3": vision.model_dump(mode="json"),
        "level4": relationships.model_dump(mode="json"),
        "known_limitations": [
            "PDF-only input; no native CAD-model validation.",
            "Functional GD&T, manufacturability, product safety, and final approval remain manual.",
            "Visual and relationship accuracy is not claimed without reviewed ground truth.",
        ],
    }
    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="drawing-{drawing_id}-complete-report.json"'
            )
        },
    )


@app.get("/api/drawings/{drawing_id}/report/export/csv")
def export_complete_analysis_csv(drawing_id: str, store: StoreDependency) -> Response:
    validation = _stored_validation(drawing_id, store)
    relationships = _stored_relationships(drawing_id, store)
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
            "evidence",
        ],
    )
    writer.writeheader()
    for item in validation.results:
        writer.writerow(
            {
                "level": "LEVEL_2",
                "id": item.rule_id,
                "name": item.rule_name,
                "status": item.status,
                "severity": item.severity,
                "actual": item.actual_condition,
                "recommendation": item.recommendation,
                "evidence": json.dumps([e.model_dump(mode="json") for e in item.evidence]),
            }
        )
    for item in relationships.findings:
        writer.writerow(
            {
                "level": "LEVEL_4",
                "id": item.relationship_rule_id,
                "name": item.name,
                "status": item.status,
                "severity": item.severity,
                "priority": item.priority,
                "confidence": item.confidence,
                "actual": item.actual_relationship,
                "recommendation": item.recommendation,
                "evidence": json.dumps([e.model_dump(mode="json") for e in item.evidence]),
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="drawing-{drawing_id}-complete-report.csv"'
            )
        },
    )


@app.get("/api/drawings/{drawing_id}/validation", response_model=ValidationReport)
def get_validation(drawing_id: str, store: StoreDependency) -> ValidationReport:
    return _stored_validation(drawing_id, store)


@app.get(
    "/api/drawings/{drawing_id}/validation/summary",
    response_model=ValidationSummary,
)
def get_validation_summary(
    drawing_id: str,
    store: StoreDependency,
) -> ValidationSummary:
    return _stored_validation(drawing_id, store).summary


@app.get(
    "/api/drawings/{drawing_id}/validation/rules",
    response_model=list[RuleMetadata],
)
def get_validation_rules(
    drawing_id: str,
    store: StoreDependency,
) -> list[RuleMetadata]:
    _stored_document(drawing_id, store)
    return ValidationEngine().registry.metadata()


@app.get(
    "/api/drawings/{drawing_id}/validation/results/{rule_id}",
    response_model=ValidationResult,
)
def get_validation_result(
    drawing_id: str,
    rule_id: str,
    store: StoreDependency,
) -> ValidationResult:
    report = _stored_validation(drawing_id, store)
    for result in report.results:
        if result.rule_id == rule_id:
            return result
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule result not found.")


@app.get("/api/drawings/{drawing_id}/validation/export/json")
def export_validation_json(drawing_id: str, store: StoreDependency) -> Response:
    report = _stored_validation(drawing_id, store)
    return Response(
        content=report.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (f'attachment; filename="drawing-{drawing_id}-validation.json"')
        },
    )


@app.get("/api/drawings/{drawing_id}/validation/export/csv")
def export_validation_csv(drawing_id: str, store: StoreDependency) -> Response:
    report = _stored_validation(drawing_id, store)
    output = io.StringIO(newline="")
    columns = [
        "rule_id",
        "rule_name",
        "category",
        "status",
        "severity",
        "expected",
        "actual",
        "message",
        "recommendation",
        "evidence",
        "rule_version",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for result in report.results:
        writer.writerow(
            {
                "rule_id": result.rule_id,
                "rule_name": result.rule_name,
                "category": result.rule_category,
                "status": result.status,
                "severity": result.severity,
                "expected": result.expected_condition,
                "actual": result.actual_condition,
                "message": result.message,
                "recommendation": result.recommendation,
                "evidence": json.dumps(
                    [item.model_dump(mode="json") for item in result.evidence],
                    separators=(",", ":"),
                ),
                "rule_version": result.rule_version,
            }
        )
    output.write(f"\nDisclaimer,{report.disclaimer}\n")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (f'attachment; filename="drawing-{drawing_id}-validation.csv"')
        },
    )


async def _extract_upload(upload: UploadFile, directory: Path) -> DrawingExtraction:
    path = await _persist_upload(upload, directory)
    pipeline = DrawingExtractionPipeline(settings)
    try:
        return await run_in_threadpool(pipeline.extract, path, filename=path.name)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Extraction failed for %s", path.name)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unable to extract this PDF: {exc}",
        ) from exc


@app.post(f"{settings.api_prefix}/extractions", response_model=DrawingExtraction)
async def extract_drawing(file: UploadFile) -> DrawingExtraction:
    with TemporaryDirectory(prefix="drawing-extraction-") as directory:
        return await _extract_upload(file, Path(directory))


@app.post(f"{settings.api_prefix}/extractions/batch", response_model=BatchExtractionResponse)
async def extract_drawings(files: list[UploadFile]) -> BatchExtractionResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF is required.")
    results: list[DrawingExtraction] = []
    with TemporaryDirectory(prefix="drawing-extraction-batch-") as directory:
        root = Path(directory)
        for index, upload in enumerate(files):
            item_directory = root / str(index)
            item_directory.mkdir()
            results.append(await _extract_upload(upload, item_directory))
    return BatchExtractionResponse(drawings=results)


# Optional single-server client-demo mode. API routes remain registered before
# the SPA mount, while Vite development continues to work independently.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
