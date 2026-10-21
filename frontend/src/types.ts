export type BoundingBox = [number, number, number, number];

export type ExtractionMethod =
  | "file_metadata"
  | "pdf_metadata"
  | "native_text"
  | "coordinate_text"
  | "pdfplumber_table"
  | "ocr"
  | "targeted_ocr"
  | "image_region"
  | null;

export type ConfidenceCategory = "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type TableType = "BOM" | "PART_LIST" | "SERVICE_PARTS" | "UNKNOWN";

export type ExtractedField<T = unknown> = {
  value: T | null;
  page_number: number | null;
  confidence: number;
  extraction_method: ExtractionMethod;
  bounding_box: BoundingBox | null;
  raw_text: string | null;
  evidence_anchor: string | null;
  confidence_category: ConfidenceCategory;
};

export type TitleBlock = {
  drawing_number: ExtractedField<string>;
  revision: ExtractedField<string>;
  drawing_size: ExtractedField<string>;
  part_name: ExtractedField<string>;
  part_numbers: ExtractedField<string[]>;
  units: ExtractedField<string>;
  scale: ExtractedField<string>;
  weight: ExtractedField<string>;
  sheet_number: ExtractedField<number>;
  sheet_count: ExtractedField<number>;
  critical_component: ExtractedField<boolean>;
  drawing_date: ExtractedField<string>;
  release_date: ExtractedField<string>;
  drawn_by: ExtractedField<string>;
  modeled_by: ExtractedField<string>;
  approved_by: ExtractedField<string>;
};

export type RevisionRecord = {
  revision: ExtractedField<string>;
  ecn: ExtractedField<string>;
  revision_description: ExtractedField<string>;
  revision_date: ExtractedField<string>;
  changed_by: ExtractedField<string>;
  approved_by: ExtractedField<string>;
  page_number: number | null;
  bounding_box: BoundingBox | null;
};

export type StandardReference = {
  designation: ExtractedField<string>;
  description: ExtractedField<string>;
};

export type DrawingNote = {
  number: ExtractedField<string>;
  text: ExtractedField<string>;
  page_number: number | null;
  bounding_box: BoundingBox | null;
  standards: StandardReference[] | null;
};

export type BOMItem = {
  table_type: TableType;
  item_no: ExtractedField<string>;
  quantity: ExtractedField<string>;
  part_number: ExtractedField<string>;
  description: ExtractedField<string>;
  material: ExtractedField<string>;
  remarks: ExtractedField<string>;
  page_number: number | null;
  bounding_box: BoundingBox | null;
};

export type ManufacturerPartMapping = {
  source_part_number: ExtractedField<string>;
  manufacturer_part_number: ExtractedField<string>;
};

export type SupplierInfo = {
  supplier_drawing: ExtractedField<boolean>;
  supplier_name: ExtractedField<string>;
  supplier_part_number: ExtractedField<string>;
  supplier_part_numbers: ExtractedField<string[]>;
  supplier_drawing_marker: ExtractedField<string>;
  imported_cad_data_statement: ExtractedField<string>;
  manufacturer_name: ExtractedField<string>;
  manufacturer_part_number_mappings: ManufacturerPartMapping[] | null;
};

export type SupplierRasterRegion = {
  page_number: number;
  bounding_box: BoundingBox;
  normalized_bounding_box: BoundingBox;
  confidence: number;
  extraction_method: "image_region" | "pdf_metadata";
  raw_text: string | null;
  evidence_anchor: string | null;
};

export type DrawingPage = {
  page_number: number;
  width: number | null;
  height: number | null;
  template: string | null;
  native_text_available: boolean | null;
  word_count: number | null;
  text_block_count: number | null;
  title_block: TitleBlock | null;
  revisions: RevisionRecord[] | null;
  notes: DrawingNote[] | null;
  bom: BOMItem[] | null;
  supplier: SupplierInfo | null;
  standards: StandardReference[] | null;
  supplier_raster_regions: SupplierRasterRegion[] | null;
};

export type ExtractionWarning = {
  stage: string;
  message: string;
  page_number: number | null;
  exception_type: string | null;
  code: string | null;
  severity: "INFO" | "WARNING" | "ERROR";
  field_name: string | null;
};

export type Level1Summary = {
  source_filename: string;
  drawing_number: string | null;
  revision: string | null;
  part_name: string | null;
  document_type: string | null;
  extracted_field_count: number;
  high_confidence_count: number;
  medium_confidence_count: number;
  low_confidence_count: number;
  warning_count: number;
  supplier_raster_region_count: number;
  processing_state: "SUCCESS" | "SUCCESS_WITH_WARNINGS" | "FAILED";
};

export type DrawingDocument = {
  source_filename: ExtractedField<string>;
  page_count: ExtractedField<number>;
  document_type: ExtractedField<string>;
  drawing_number: ExtractedField<string>;
  revision: ExtractedField<string>;
  drawing_size: ExtractedField<string>;
  part_name: ExtractedField<string>;
  part_numbers: ExtractedField<string[]>;
  units: ExtractedField<string>;
  scale: ExtractedField<string>;
  weight: ExtractedField<string>;
  sheet_number: ExtractedField<number>;
  total_sheets: ExtractedField<number>;
  critical_component: ExtractedField<boolean>;
  release_date: ExtractedField<string>;
  drawing_date: ExtractedField<string>;
  drawn_by: ExtractedField<string>;
  modeled_by: ExtractedField<string>;
  approved_by: ExtractedField<string>;
  revision_records: RevisionRecord[] | null;
  notes: DrawingNote[] | null;
  bom_items: BOMItem[] | null;
  part_list_items: BOMItem[] | null;
  service_part_items: BOMItem[] | null;
  supplier_info: SupplierInfo | null;
  standard_references: StandardReference[] | null;
  pages: DrawingPage[] | null;
  supplier_raster_regions: SupplierRasterRegion[];
  extraction_warnings: ExtractionWarning[];
  level1_summary: Level1Summary | null;
};

export type DrawingUploadResponse = {
  id: string;
  drawing: DrawingDocument;
};

export type EvidenceSelection = {
  label: string;
  pageNumber: number;
  boundingBox: BoundingBox;
  field: ExtractedField;
};

export type ValidationStatus =
  | "PASS"
  | "FAIL"
  | "WARNING"
  | "MANUAL_REVIEW"
  | "NOT_APPLICABLE"
  | "NOT_EVALUATED";

export type ValidationSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ValidationEvidence = {
  page_number: number | null;
  bounding_box: BoundingBox | null;
  source_field: string;
  extracted_value: unknown;
  raw_text: string | null;
  extraction_method: string | null;
  confidence: number;
};

export type ValidationResult = {
  rule_id: string;
  rule_name: string;
  rule_category: string;
  rule_description: string;
  source_requirement: string;
  status: ValidationStatus;
  severity: ValidationSeverity;
  automation_type: string;
  expected_condition: string;
  actual_condition: string;
  message: string;
  recommendation: string;
  evidence: ValidationEvidence[];
  related_fields: string[];
  rule_version: string;
  execution_time_ms: number;
};

export type ValidationSummary = {
  total_rules: number;
  passed: number;
  failed: number;
  warnings: number;
  manual_review: number;
  not_applicable: number;
  not_evaluated: number;
  critical_failures: number;
  high_failures: number;
  overall_status: "PASS" | "PASS_WITH_WARNINGS" | "REVIEW_REQUIRED" | "FAIL";
};

export type ValidationReport = {
  drawing_id: string | null;
  source_filename: string;
  rule_set_version: string;
  summary: ValidationSummary;
  results: ValidationResult[];
  timing: {
    level1_processing_ms: number | null;
    level2_validation_ms: number;
    total_processing_ms: number | null;
  };
  disclaimer: string;
};

export type ValidationOverlay = {
  label: string;
  pageNumber: number;
  boundingBox: BoundingBox;
  status: ValidationStatus;
  confidence: number;
  rawText: string | null;
  method: string | null;
};

export type ValidationRuleMetadata = {
  rule_id: string;
  name: string;
  category: string;
  description: string;
  source_requirement: string;
  automation_type: string;
  severity: ValidationSeverity;
  applicability: string;
  version: string;
  automation_status: "AUTOMATED" | "PARTIALLY_AUTOMATED" | "MANUAL" | "NOT_IMPLEMENTED";
  dependencies: string[];
};

export type VisualObjectType =
  | "REVISION_TRIANGLE"
  | "BOM_BALLOON"
  | "SCC_SYMBOL"
  | "CRITICAL_SYMBOL"
  | "DATUM_SYMBOL"
  | "GDT_FRAME"
  | "VIEW_ARROW"
  | "SECTION_ARROW"
  | "DETAIL_CALLOUT"
  | "FLAG_NOTE"
  | "SUPPLIER_RASTER_TEXT"
  | "UNKNOWN";

export type VisualObject = {
  object_id: string;
  object_type: VisualObjectType;
  page_number: number;
  bounding_box: BoundingBox;
  polygon: [number, number][] | null;
  confidence: number;
  detector: string;
  extraction_method: string;
  raw_text: string | null;
  normalized_text: string | null;
  linked_text: string | null;
  attributes: Record<string, unknown>;
  source_image_region: {
    page_number: number;
    bounding_box: BoundingBox;
    dpi: number;
  } | null;
};

export type VisionReport = {
  drawing_id: string | null;
  source_filename: string;
  level3_version: string;
  enabled: boolean;
  created_at: string;
  page_dimensions: Record<string, [number, number]>;
  detector_results: {
    detector_name: string;
    objects: VisualObject[];
    warnings: string[];
    execution_time_ms: number;
    ocr_time_ms: number;
  }[];
  objects: VisualObject[];
  summary: {
    pages_processed: number;
    objects_detected: number;
    objects_by_type: Partial<Record<VisualObjectType, number>>;
    low_confidence_count: number;
    warnings: string[];
  };
  timing: {
    render_time_ms: number;
    detector_time_ms: Record<string, number>;
    ocr_time_ms: number;
    total_time_ms: number;
  };
  confidence_thresholds: Partial<Record<VisualObjectType, number>>;
  partial_confidence_floor: number;
  disclaimer: string;
};

export type VisualReviewAction = "CONFIRM" | "REJECT" | "CORRECT_LABEL";

export type RelationshipStatus = ValidationStatus;
export type RelationshipPriority = "P1" | "P2" | "P3" | "P4";

export type RelationshipEvidence = {
  page_number: number | null;
  bounding_box: BoundingBox | null;
  source_level: "LEVEL_1" | "LEVEL_2" | "LEVEL_3";
  source_reference: string;
  value: unknown;
  confidence: number;
  extraction_method: string | null;
};

export type EngineeringEntity = {
  entity_id: string;
  entity_type: string;
  value: unknown;
  page_number: number | null;
  bounding_box: BoundingBox | null;
  source_level: "LEVEL_1" | "LEVEL_2" | "LEVEL_3";
  confidence: number;
  source_reference: string;
  attributes: Record<string, unknown>;
};

export type EngineeringRelationship = {
  relationship_id: string;
  relationship_type: string;
  source_entity_id: string;
  target_entity_id: string | null;
  status: RelationshipStatus;
  confidence: number;
  evidence: RelationshipEvidence[];
  explanation: string;
};

export type RelationshipResult = {
  finding_id: string;
  relationship_rule_id: string;
  name: string;
  description: string;
  status: RelationshipStatus;
  severity: ValidationSeverity;
  priority: RelationshipPriority;
  confidence: number;
  expected_relationship: string;
  actual_relationship: string;
  source_entities: string[];
  target_entities: string[];
  evidence: RelationshipEvidence[];
  explanation: string;
  recommendation: string;
  related_validation_rule_ids: string[];
};

export type RelationshipSummary = {
  relationships_checked: number;
  passed: number;
  broken: number;
  warnings: number;
  manual_review: number;
  not_applicable: number;
  not_evaluated: number;
  high_priority_findings: number;
  overall_status: "PASS" | "PASS_WITH_WARNINGS" | "REVIEW_REQUIRED" | "FAIL";
};

export type RelationshipReport = {
  drawing_id: string | null;
  source_filename: string;
  level4_version: string;
  created_at: string;
  graph: {
    nodes: EngineeringEntity[];
    edges: EngineeringRelationship[];
  };
  findings: RelationshipResult[];
  correlations: {
    correlation_id: string;
    category: string;
    title: string;
    priority: RelationshipPriority;
    finding_ids: string[];
    related_validation_rule_ids: string[];
    explanation: string;
    qualifier: string;
  }[];
  summary: RelationshipSummary;
  timing: { level4_relationship_ms: number };
  disclaimer: string;
};

export type CompleteAnalysisReport = {
  drawing_id: string;
  level1_status: string;
  level2_status: string;
  level3_status: string;
  level4_status: string;
  validation_summary: ValidationSummary;
  vision_summary: VisionReport["summary"];
  relationship_summary: RelationshipSummary;
  level1_summary: Record<string, unknown>;
  top_findings: RelationshipResult[];
  timing_ms: Record<string, number | null>;
  final_system_status: "PASS" | "PASS_WITH_WARNINGS" | "REVIEW_REQUIRED" | "FAIL";
  disclaimer: string;
};
