import { useEffect, useRef, useState } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentProxy,
  type RenderTask,
} from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import type {
  DrawingPage,
  EvidenceSelection,
  ValidationOverlay,
  VisualObject,
  VisualObjectType,
} from "./types";

GlobalWorkerOptions.workerSrc = workerUrl;

type PdfPreviewProps = {
  file: File;
  pages: DrawingPage[];
  currentPage: number;
  selection: EvidenceSelection | null;
  validationSelection: ValidationOverlay[];
  visualObjects: VisualObject[];
  visualSelection: VisualObject | null;
  visibleVisualTypes: Set<VisualObjectType>;
  extractedRegions: EvidenceSelection[];
  showExtractedRegions: boolean;
  onShowExtractedRegions: (show: boolean) => void;
  onPageChange: (page: number) => void;
  onClearSelection: () => void;
};

export default function PdfPreview({
  file,
  pages,
  currentPage,
  selection,
  validationSelection,
  visualObjects,
  visualSelection,
  visibleVisualTypes,
  extractedRegions,
  showExtractedRegions,
  onShowExtractedRegions,
  onPageChange,
  onClearSelection,
}: PdfPreviewProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [hostWidth, setHostWidth] = useState(720);
  const [renderSize, setRenderSize] = useState({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(([entry]) => {
      setHostWidth(Math.max(320, entry.contentRect.width - 48));
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let disposed = false;
    const url = URL.createObjectURL(file);
    const task = getDocument({ url });
    task.promise
      .then((loaded) => {
        if (!disposed) setDocument(loaded);
      })
      .catch(() => {
        if (!disposed) setError("The PDF preview could not be rendered.");
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
      void task.destroy();
      URL.revokeObjectURL(url);
    };
  }, [file]);

  useEffect(() => {
    if (!document || !canvasRef.current) return;
    let disposed = false;
    let renderTask: RenderTask | null = null;
    document
      .getPage(currentPage)
      .then((page) => {
        if (disposed || !canvasRef.current) return;
        const natural = page.getViewport({ scale: 1 });
        const fitScale = hostWidth / natural.width;
        const viewport = page.getViewport({ scale: fitScale * zoom });
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
        const canvas = canvasRef.current;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Canvas is unavailable");
        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        setRenderSize({ width: viewport.width, height: viewport.height });
        renderTask = page.render({
          canvas,
          canvasContext: context,
          viewport,
          transform: pixelRatio === 1 ? undefined : [pixelRatio, 0, 0, pixelRatio, 0, 0],
        });
        return renderTask.promise;
      })
      .catch((caught) => {
        if (!disposed && caught instanceof Error && caught.name !== "RenderingCancelledException") {
          setError("The selected page could not be rendered.");
        }
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
      renderTask?.cancel();
    };
  }, [currentPage, document, hostWidth, zoom]);

  const pageMetadata = pages.find((page) => page.page_number === currentPage);
  const highlight =
    selection &&
    selection.pageNumber === currentPage &&
    pageMetadata?.width &&
    pageMetadata.height
      ? {
          left: `${(selection.boundingBox[0] / pageMetadata.width) * 100}%`,
          top: `${(selection.boundingBox[1] / pageMetadata.height) * 100}%`,
          width: `${
            ((selection.boundingBox[2] - selection.boundingBox[0]) / pageMetadata.width) * 100
          }%`,
          height: `${
            ((selection.boundingBox[3] - selection.boundingBox[1]) / pageMetadata.height) * 100
          }%`,
        }
      : null;

  const visibleRegions = showExtractedRegions && pageMetadata?.width && pageMetadata.height
    ? extractedRegions
        .filter((region) => region.pageNumber === currentPage)
        .map((region) => ({
          region,
          style: {
            left: `${(region.boundingBox[0] / pageMetadata.width!) * 100}%`,
            top: `${(region.boundingBox[1] / pageMetadata.height!) * 100}%`,
            width: `${((region.boundingBox[2] - region.boundingBox[0]) / pageMetadata.width!) * 100}%`,
            height: `${((region.boundingBox[3] - region.boundingBox[1]) / pageMetadata.height!) * 100}%`,
          },
        }))
    : [];

  const validationRegions = pageMetadata?.width && pageMetadata.height
    ? validationSelection
        .filter((region) => region.pageNumber === currentPage)
        .map((region) => ({
          region,
          style: {
            left: `${(region.boundingBox[0] / pageMetadata.width!) * 100}%`,
            top: `${(region.boundingBox[1] / pageMetadata.height!) * 100}%`,
            width: `${((region.boundingBox[2] - region.boundingBox[0]) / pageMetadata.width!) * 100}%`,
            height: `${((region.boundingBox[3] - region.boundingBox[1]) / pageMetadata.height!) * 100}%`,
          },
        }))
    : [];

  const visualRegions = pageMetadata?.width && pageMetadata.height
    ? visualObjects
        .filter(
          (region) =>
            region.page_number === currentPage && visibleVisualTypes.has(region.object_type),
        )
        .map((region) => ({
          region,
          style: {
            left: `${(region.bounding_box[0] / pageMetadata.width!) * 100}%`,
            top: `${(region.bounding_box[1] / pageMetadata.height!) * 100}%`,
            width: `${((region.bounding_box[2] - region.bounding_box[0]) / pageMetadata.width!) * 100}%`,
            height: `${((region.bounding_box[3] - region.bounding_box[1]) / pageMetadata.height!) * 100}%`,
          },
        }))
    : [];

  const totalPages = document?.numPages ?? pages.length ?? 1;

  return (
    <section className="preview" aria-label="PDF drawing preview">
      <div className="preview__toolbar">
        <div className="page-controls" aria-label="Page controls">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            aria-label="Previous page"
          >
            ←
          </button>
          <span>
            Sheet <strong>{currentPage}</strong> / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage >= totalPages}
            aria-label="Next page"
          >
            →
          </button>
        </div>
        <div className="zoom-controls" aria-label="Zoom controls">
          <button
            type="button"
            onClick={() => setZoom((value) => Math.max(0.6, value - 0.2))}
            aria-label="Zoom out"
          >
            −
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            onClick={() => setZoom((value) => Math.min(2.4, value + 0.2))}
            aria-label="Zoom in"
          >
            +
          </button>
        </div>
      </div>

      {visualSelection ? (
        <div className="evidence-banner evidence-banner--visual">
          <span className="evidence-banner__pulse" />
          <span className="evidence-banner__copy">
            Showing visual object <strong>{visualSelection.object_type.replaceAll("_", " ")}</strong>
            <small>
              {Math.round(visualSelection.confidence * 100)}% · {visualSelection.detector.replaceAll("_", " ")}
              {visualSelection.raw_text ? ` · Detected: ${visualSelection.raw_text}` : ""}
            </small>
          </span>
          <button type="button" onClick={onClearSelection}>Clear</button>
        </div>
      ) : validationSelection.length ? (
        <div className="evidence-banner evidence-banner--validation">
          <span className="evidence-banner__pulse" />
          <span className="evidence-banner__copy">
            Showing {validationSelection.length} evidence region{validationSelection.length === 1 ? "" : "s"} for <strong>{validationSelection[0].label}</strong>
            <small>
              {validationSelection[0].status.replaceAll("_", " ")} · {Math.round(validationSelection[0].confidence * 100)}% evidence confidence
              {validationSelection[0].method ? ` · ${validationSelection[0].method.replaceAll("_", " ")}` : ""}
              {validationSelection[0].rawText ? ` · Raw: ${validationSelection[0].rawText}` : ""}
            </small>
          </span>
          <button type="button" onClick={onClearSelection}>Clear</button>
        </div>
      ) : selection ? (
        <div className="evidence-banner">
          <span className="evidence-banner__pulse" />
          <span className="evidence-banner__copy">
            Showing source for <strong>{selection.label}</strong>
            <small>
              {selection.field.confidence_category} · {Math.round(selection.field.confidence * 100)}% · {selection.field.extraction_method?.replaceAll("_", " ")}
              {selection.field.evidence_anchor ? ` · ${selection.field.evidence_anchor}` : ""}
              {selection.field.raw_text ? ` · Raw: ${selection.field.raw_text}` : ""}
            </small>
          </span>
          <button type="button" onClick={onClearSelection}>Clear</button>
        </div>
      ) : (
        <div className="evidence-hint">Select an evidenced field to locate it on the drawing.</div>
      )}

      <div className="preview__viewport" ref={hostRef}>
        {error && <div className="preview-state preview-state--error">{error}</div>}
        {loading && !error && <div className="preview-state"><span className="loader" />Rendering sheet</div>}
        <div
          className="pdf-page"
          style={{ width: renderSize.width, height: renderSize.height }}
        >
          <canvas ref={canvasRef} />
          {visibleRegions.map(({ region, style }, index) => (
            <div
              className="extracted-region"
              style={style}
              key={`${region.pageNumber}-${region.boundingBox.join("-")}-${index}`}
              aria-hidden="true"
            />
          ))}
          {validationRegions.map(({ region, style }, index) => (
            <div
              className={`validation-highlight validation-highlight--${region.status.toLowerCase()}`}
              style={style}
              key={`validation-${region.pageNumber}-${region.boundingBox.join("-")}-${index}`}
              role="img"
              aria-label={`${region.status.replaceAll("_", " ")} evidence: ${region.label}`}
            >
              <span>{region.status.replaceAll("_", " ")} · {region.label}</span>
            </div>
          ))}
          {visualRegions.map(({ region, style }) => (
            <div
              className={`visual-highlight visual-highlight--${region.object_type.toLowerCase()} ${visualSelection?.object_id === region.object_id ? "visual-highlight--selected" : ""}`}
              style={style}
              key={`visual-${region.object_id}`}
              role="img"
              aria-label={`${region.object_type.replaceAll("_", " ")} visual evidence`}
            >
              <span>{region.object_type.replaceAll("_", " ")} · {Math.round(region.confidence * 100)}%</span>
            </div>
          ))}
          {highlight && (
            <div className="source-highlight" style={highlight} aria-label={selection?.label}>
              <span>{selection?.label}</span>
            </div>
          )}
        </div>
      </div>
      <div className="preview__status">
        <span className={pageMetadata?.native_text_available ? "status-dot" : "status-dot status-dot--muted"} />
        {pageMetadata?.native_text_available ? "Native text available" : "No native text detected"}
        <span className="preview__status-separator" />
        <label className="region-toggle">
          <input
            type="checkbox"
            checked={showExtractedRegions}
            onChange={(event) => onShowExtractedRegions(event.target.checked)}
          />
          Show Extracted Regions
        </label>
        <span className="preview__status-separator" />
        {pageMetadata?.word_count ?? 0} words · {pageMetadata?.text_block_count ?? 0} blocks
      </div>
    </section>
  );
}
