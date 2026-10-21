"""Reusable deterministic evaluators for the controlled Level-2 rule catalog."""

# ruff: noqa: E501 - result explanations intentionally remain complete sentences.

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.models.drawing import BOMItem, ExtractedField
from backend.app.validation.context import ValidationContext
from backend.app.validation.models import RuleMetadata, ValidationEvidence
from backend.app.validation.rules.base import RuleOutcome, ValidationRule, outcome
from backend.app.validation.severity import ValidationStatus


class DeclarativeRule(ValidationRule):
    def __init__(
        self, metadata: RuleMetadata, evaluator: str, parameters: dict[str, Any] | None = None
    ) -> None:
        super().__init__(metadata)
        self.evaluator = evaluator
        self.parameters = parameters or {}

    def validate(self, context: ValidationContext) -> RuleOutcome:
        evaluator = getattr(self, f"_evaluate_{self.evaluator}")
        return evaluator(context)

    def _field_evidence(
        self, context: ValidationContext, path: str, field: ExtractedField[Any]
    ) -> list[ValidationEvidence]:
        return [context.evidence(path, field)] if field.value is not None else []

    def _evaluate_presence(self, context: ValidationContext) -> RuleOutcome:
        field_name = self.parameters["field"]
        field = context.document_field(field_name)
        label = self.parameters.get("label", field_name.replace("_", " "))
        evidence = self._field_evidence(context, field_name, field)
        if field.value is None:
            return outcome(
                ValidationStatus.FAIL,
                f"{label} is present in the applicable title block.",
                f"No {label} value was extracted.",
                f"{self.metadata.rule_id}: required {label} is missing from reliable Level-1 evidence.",
                f"Verify the title block and provide the {label} if required.",
                related_fields=[field_name],
            )
        if not context.has_reliable_value(field):
            return outcome(
                ValidationStatus.MANUAL_REVIEW,
                f"{label} is confidently extracted.",
                f"Extracted {field.value!r} at confidence {field.confidence:.2f}.",
                f"{self.metadata.rule_id}: {label} evidence is below the validation confidence threshold.",
                "Confirm the value against the highlighted title-block source.",
                evidence,
                [field_name],
            )
        return outcome(
            ValidationStatus.PASS,
            f"{label} is present in the applicable title block.",
            f"Extracted {field.value!r}.",
            f"{self.metadata.rule_id}: {label} is present with reliable evidence.",
            "No action required.",
            evidence,
            [field_name],
        )

    def _evaluate_consistency(self, context: ValidationContext) -> RuleOutcome:
        field_name = self.parameters["field"]
        label = self.parameters.get("label", field_name.replace("_", " "))
        fields = context.page_fields(field_name)
        if not fields:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                f"Reliable page-level {label} evidence exists on every relevant sheet.",
                "No page-level title-block evidence is available.",
                f"{self.metadata.rule_id}: page-level evidence dependency is unavailable.",
                "Review Level-1 title-block extraction before applying this consistency rule.",
                related_fields=[f"pages[].title_block.{field_name}"],
            )
        missing = [
            page
            for page, field in fields
            if field.value is None or not context.has_reliable_value(field)
        ]
        evidence = [
            context.evidence(f"pages[{page}].title_block.{field_name}", field)
            for page, field in fields
            if field.value is not None
        ]
        if missing:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                f"Reliable page-level {label} evidence exists on every relevant sheet.",
                f"Missing or low-confidence evidence on page(s): {', '.join(map(str, missing))}.",
                f"{self.metadata.rule_id}: extraction uncertainty prevents a deterministic consistency decision.",
                "Confirm the unresolved page title blocks, then rerun validation.",
                evidence,
                [f"pages[].title_block.{field_name}"],
            )
        normalized = [str(field.value).strip().casefold() for _, field in fields]
        if len(set(normalized)) == 1:
            return outcome(
                ValidationStatus.PASS,
                f"{label} is consistent across all relevant sheets.",
                f"All {len(fields)} sheet(s) contain {fields[0][1].value!r}.",
                f"{self.metadata.rule_id}: page-level {label} values are consistent.",
                "No action required.",
                evidence,
                [f"pages[].title_block.{field_name}"],
            )
        conflict_status = ValidationStatus(self.parameters.get("conflict_status", "FAIL"))
        actual = "; ".join(f"page {page}: {field.value!r}" for page, field in fields)
        return outcome(
            conflict_status,
            f"{label} is consistent across all relevant sheets.",
            actual,
            f"{self.metadata.rule_id}: conflicting {label} values were detected across sheets.",
            f"Verify whether the page-specific {label} difference is intentional and update inconsistent sheets if not.",
            evidence,
            [f"pages[].title_block.{field_name}"],
        )

    def _evaluate_sheet_bounds(self, context: ValidationContext) -> RuleOutcome:
        fields = context.page_fields("sheet_number")
        totals = context.page_fields("sheet_count")
        if not fields or len(fields) != len(totals):
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Each page declares current and total sheet numbers.",
                "Sheet evidence is incomplete.",
                f"{self.metadata.rule_id}: sheet-number dependencies are incomplete.",
                "Review Level-1 sheet extraction.",
            )
        evidence: list[ValidationEvidence] = []
        invalid: list[str] = []
        unresolved: list[int] = []
        total_map = dict(totals)
        for page, current in fields:
            total = total_map[page]
            if not context.has_reliable_value(current) or not context.has_reliable_value(total):
                unresolved.append(page)
                continue
            evidence.extend(
                [
                    context.evidence(f"pages[{page}].title_block.sheet_number", current),
                    context.evidence(f"pages[{page}].title_block.sheet_count", total),
                ]
            )
            if int(current.value) < 1 or int(total.value) < int(current.value):
                invalid.append(f"page {page}: {current.value}/{total.value}")
        if unresolved:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "1 <= current sheet <= total sheets.",
                f"Unreliable sheet values on page(s) {unresolved}.",
                f"{self.metadata.rule_id}: extraction uncertainty prevents the bounds check.",
                "Confirm sheet values.",
                evidence,
            )
        if invalid:
            return outcome(
                ValidationStatus.FAIL,
                "1 <= current sheet <= total sheets.",
                "; ".join(invalid),
                f"{self.metadata.rule_id}: invalid sheet-number bounds detected.",
                "Correct the declared sheet number or total.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "1 <= current sheet <= total sheets.",
            "All declared sheet values satisfy the bounds.",
            f"{self.metadata.rule_id}: sheet-number bounds are valid.",
            "No action required.",
            evidence,
        )

    def _evaluate_sheet_sequence(self, context: ValidationContext) -> RuleOutcome:
        fields = context.page_fields("sheet_number")
        if not fields:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Sheet numbers form 1..N.",
                "No page-level sheet numbers are available.",
                f"{self.metadata.rule_id}: sheet sequence is not evaluable.",
            )
        if any(not context.has_reliable_value(field) for _, field in fields):
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Sheet numbers form 1..N.",
                "One or more sheet values are missing or low confidence.",
                f"{self.metadata.rule_id}: extraction uncertainty prevents sequence validation.",
            )
        actual_values = [int(field.value) for _, field in fields]
        expected_values = list(range(1, len(fields) + 1))
        evidence = [
            context.evidence(f"pages[{page}].title_block.sheet_number", field)
            for page, field in fields
        ]
        if actual_values == expected_values:
            return outcome(
                ValidationStatus.PASS,
                f"Sequence is {expected_values}.",
                f"Detected {actual_values}.",
                f"{self.metadata.rule_id}: sheet sequence is complete and ordered.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.FAIL,
            f"Sequence is {expected_values}.",
            f"Detected {actual_values}.",
            f"{self.metadata.rule_id}: duplicate, skipped, or out-of-order sheet numbers were detected.",
            "Review sheet numbering across the document.",
            evidence,
        )

    def _evaluate_sheet_count(self, context: ValidationContext) -> RuleOutcome:
        declared = context.document.total_sheets
        page_count = context.document.page_count
        evidence = self._field_evidence(context, "total_sheets", declared) + self._field_evidence(
            context, "page_count", page_count
        )
        if not context.has_reliable_value(declared) or not context.has_reliable_value(page_count):
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Declared total sheets equals PDF page count.",
                "Declared total or PDF page count is unavailable or low confidence.",
                f"{self.metadata.rule_id}: count comparison dependencies are unresolved.",
                "Confirm page and sheet-count evidence.",
                evidence,
            )
        if declared.value == page_count.value:
            return outcome(
                ValidationStatus.PASS,
                "Declared total sheets equals PDF page count.",
                f"Both values are {declared.value}.",
                f"{self.metadata.rule_id}: declared sheet count matches the PDF.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.WARNING,
            "Declared total sheets equals PDF page count when the PDF contains only drawing sheets.",
            f"Declared {declared.value}; PDF contains {page_count.value} page(s).",
            f"{self.metadata.rule_id}: count mismatch detected; wrapper structure may affect applicability.",
            "Verify whether every PDF page is a drawing sheet.",
            evidence,
        )

    def _revision_records(self, context: ValidationContext) -> list[Any]:
        return context.document.revision_records or []

    def _evaluate_revision_field(self, context: ValidationContext) -> RuleOutcome:
        records = self._revision_records(context)
        field_name = self.parameters["field"]
        label = self.parameters.get("label", field_name.replace("_", " "))
        if not records:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                f"Each revision row contains {label}.",
                "No revision records were extracted.",
                f"{self.metadata.rule_id}: no revision rows are available to check.",
            )
        missing: list[int] = []
        low: list[int] = []
        evidence: list[ValidationEvidence] = []
        for index, record in enumerate(records, start=1):
            field = getattr(record, field_name)
            if field.value is None:
                missing.append(index)
            elif not context.has_reliable_value(field):
                low.append(index)
                evidence.append(
                    context.evidence(f"revision_records[{index - 1}].{field_name}", field)
                )
            else:
                evidence.append(
                    context.evidence(f"revision_records[{index - 1}].{field_name}", field)
                )
        if low:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                f"Each revision row contains reliable {label}.",
                f"Low-confidence {label} in row(s) {low}.",
                f"{self.metadata.rule_id}: extraction confidence prevents a deterministic result.",
                "Confirm the cited revision row values.",
                evidence,
            )
        if missing:
            return outcome(
                ValidationStatus.FAIL,
                f"Each revision row contains {label}.",
                f"Missing in row(s) {missing}.",
                f"{self.metadata.rule_id}: required revision-row {label} is missing.",
                f"Complete the {label} for the affected revision row(s).",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            f"Each revision row contains {label}.",
            f"Present in {len(records)} row(s).",
            f"{self.metadata.rule_id}: revision-row {label} is present.",
            "No action required.",
            evidence,
        )

    def _evaluate_revision_phrase(self, context: ValidationContext) -> RuleOutcome:
        phrase = self.parameters["phrase"]
        matches = []
        for index, record in enumerate(self._revision_records(context)):
            field = record.revision_description
            if field.value and phrase.casefold() in str(field.value).casefold():
                matches.append(
                    context.evidence(f"revision_records[{index}].revision_description", field)
                )
        if not matches:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                f"Recognize the phrase {phrase!r} when present.",
                "Phrase not present.",
                f"{self.metadata.rule_id}: release phrase is not present in extracted revision descriptions.",
            )
        return outcome(
            ValidationStatus.PASS,
            f"Recognize the phrase {phrase!r} when present.",
            f"Detected in {len(matches)} revision record(s).",
            f"{self.metadata.rule_id}: release phrase was recognized.",
            "No action required.",
            matches,
        )

    def _evaluate_see_sheet1(self, context: ValidationContext) -> RuleOutcome:
        phrase = "SEE SHEET 1 FOR REVISIONS"
        references: list[ValidationEvidence] = []
        for index, record in enumerate(self._revision_records(context)):
            field = record.revision_description
            if field.value and phrase in str(field.value).upper():
                references.append(
                    context.evidence(f"revision_records[{index}].revision_description", field)
                )
        if not references:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "When later sheets refer to sheet 1, sheet 1 contains an actual revision record.",
                "No see-sheet-1 phrase was detected.",
                f"{self.metadata.rule_id}: referral convention is not used.",
            )
        page_one = [
            record
            for record in self._revision_records(context)
            if record.page_number == 1
            and record.revision_description.value
            and phrase not in str(record.revision_description.value).upper()
        ]
        evidence = references + [
            context.evidence("revision_records[].revision_description", record.revision_description)
            for record in page_one
        ]
        if page_one:
            return outcome(
                ValidationStatus.PASS,
                "Sheet 1 contains actual revision information.",
                "A non-referral revision description exists on sheet 1.",
                f"{self.metadata.rule_id}: sheet-1 revision referral resolves to revision evidence.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.FAIL,
            "Sheet 1 contains actual revision information.",
            "No non-referral revision description was extracted on sheet 1.",
            f"{self.metadata.rule_id}: later-sheet referral has no extracted sheet-1 revision detail.",
            "Verify the sheet-1 revision table.",
            evidence,
        )

    def _evaluate_revision_sequence(self, context: ValidationContext) -> RuleOutcome:
        values = [
            record.revision
            for record in self._revision_records(context)
            if record.revision.value is not None
        ]
        if len(values) < 2:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "Multiple revisions follow the configured ordering convention.",
                "Fewer than two revision identifiers are available.",
                f"{self.metadata.rule_id}: revision ordering does not apply.",
            )
        evidence = [context.evidence("revision_records[].revision", field) for field in values]
        normalized = [str(field.value).strip().upper() for field in values]
        if any(not re.fullmatch(r"[A-Z]", value) for value in normalized):
            return outcome(
                ValidationStatus.MANUAL_REVIEW,
                "Revision identifiers follow a configured sequence.",
                f"Detected {normalized}; no authoritative convention resolves this format.",
                f"{self.metadata.rule_id}: revision sequence interpretation is ambiguous.",
                "Confirm the applicable revision convention.",
                evidence,
            )
        codes = [ord(value) for value in normalized]
        if codes in (sorted(codes), sorted(codes, reverse=True)) and len(codes) == len(set(codes)):
            return outcome(
                ValidationStatus.PASS,
                "Alphabetic revisions are ordered without duplicates.",
                f"Detected {normalized}.",
                f"{self.metadata.rule_id}: revision identifiers are ordered.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.WARNING,
            "Alphabetic revisions are ordered without duplicates.",
            f"Detected {normalized}.",
            f"{self.metadata.rule_id}: revision ordering or duplication requires review.",
            "Confirm the revision-history convention and order.",
            evidence,
        )

    def _evaluate_revision_xref(self, context: ValidationContext) -> RuleOutcome:
        title = context.document.revision
        records = [
            record.revision
            for record in self._revision_records(context)
            if record.revision.value is not None
        ]
        evidence = self._field_evidence(context, "revision", title) + [
            context.evidence("revision_records[].revision", field) for field in records
        ]
        if not context.has_reliable_value(title) or not records:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Title-block revision matches the unambiguous latest revision row.",
                "Title revision or revision history evidence is unavailable.",
                f"{self.metadata.rule_id}: cross-reference dependencies are incomplete.",
                "Confirm Level-1 revision extraction.",
                evidence,
            )
        if any(not context.has_reliable_value(field) for field in records):
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Revision evidence is reliable before comparison.",
                "At least one revision identifier is low confidence.",
                f"{self.metadata.rule_id}: extraction uncertainty prevents comparison.",
                "Confirm revision identifiers.",
                evidence,
            )
        matches = [
            field
            for field in records
            if str(field.value).strip().casefold() == str(title.value).strip().casefold()
        ]
        if len(matches) == 1:
            return outcome(
                ValidationStatus.PASS,
                "Title revision is represented unambiguously in the revision table.",
                f"Title revision {title.value!r} has one matching revision row.",
                f"{self.metadata.rule_id}: title and revision-table evidence agree.",
                "No action required.",
                evidence,
            )
        if not matches:
            return outcome(
                ValidationStatus.FAIL,
                "Title revision is represented in the revision table.",
                f"Title revision {title.value!r}; table revisions {[field.value for field in records]}.",
                f"{self.metadata.rule_id}: title revision was not found in the extracted revision history.",
                "Verify the current title-block revision and revision table.",
                evidence,
            )
        return outcome(
            ValidationStatus.MANUAL_REVIEW,
            "Newest applicable revision row is unambiguous.",
            f"Title revision {title.value!r} matches multiple extracted rows.",
            f"{self.metadata.rule_id}: revision-history interpretation is ambiguous.",
            "Review the complete revision history.",
            evidence,
        )

    def _evaluate_note_detected(self, context: ValidationContext) -> RuleOutcome:
        notes = context.document.notes or []
        if not notes:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "A notes section is present where the template requires notes.",
                "No notes were extracted and no template requirement is configured.",
                f"{self.metadata.rule_id}: notes expectation is not established.",
            )
        evidence = [
            context.evidence(f"notes[{index}].text", note.text)
            for index, note in enumerate(notes)
            if note.text.value is not None
        ]
        return outcome(
            ValidationStatus.PASS,
            "A notes section is detected when notes exist.",
            f"Detected {len(notes)} numbered note(s).",
            f"{self.metadata.rule_id}: notes section evidence is present.",
            "No action required.",
            evidence,
        )

    def _note_numbers(
        self, context: ValidationContext
    ) -> tuple[list[str], list[ValidationEvidence], bool]:
        values: list[str] = []
        evidence: list[ValidationEvidence] = []
        reliable = True
        for index, note in enumerate(context.document.notes or []):
            if note.number.value is None or not context.has_reliable_value(note.number):
                reliable = False
            else:
                values.append(str(note.number.value).strip())
                evidence.append(context.evidence(f"notes[{index}].number", note.number))
        return values, evidence, reliable

    def _evaluate_note_sequence(self, context: ValidationContext) -> RuleOutcome:
        values, evidence, reliable = self._note_numbers(context)
        if not reliable:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Note identifiers can be read reliably before sequencing.",
                "At least one note number is missing or low confidence.",
                f"{self.metadata.rule_id}: note sequence cannot be decided from unreliable extraction.",
                "Confirm note numbering.",
                evidence,
            )
        if not values:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "Numbered notes form the configured sequence.",
                "No numbered notes are available.",
                f"{self.metadata.rule_id}: no notes to sequence.",
            )
        if any(not value.isdigit() for value in values):
            return outcome(
                ValidationStatus.MANUAL_REVIEW,
                "Numeric note sequence or configured deletion convention.",
                f"Detected identifiers {values}.",
                f"{self.metadata.rule_id}: nonnumeric note identifiers require convention review.",
                "Confirm the note numbering convention.",
                evidence,
            )
        actual = [int(value) for value in values]
        expected = list(range(min(actual), max(actual) + 1))
        allowed = set(context.rule_config(self.metadata.rule_id).get("allowed_missing", []))
        missing = [number for number in expected if number not in actual and number not in allowed]
        if not missing:
            return outcome(
                ValidationStatus.PASS,
                "Numbered notes are sequential, allowing configured omissions.",
                f"Detected {actual}.",
                f"{self.metadata.rule_id}: note sequence is valid.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.WARNING,
            "Numbered notes are sequential or omitted numbers are configured.",
            f"Detected {actual}; unexplained gap(s) {missing}.",
            f"{self.metadata.rule_id}: note sequence contains unconfigured gaps.",
            "Verify deleted or missing note numbers.",
            evidence,
        )

    def _evaluate_note_duplicates(self, context: ValidationContext) -> RuleOutcome:
        values, evidence, reliable = self._note_numbers(context)
        if not reliable:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Note numbers are reliable before duplicate checking.",
                "At least one note number is missing or low confidence.",
                f"{self.metadata.rule_id}: duplicate check is blocked by extraction uncertainty.",
                evidence=evidence,
            )
        per_page: dict[int | None, list[str]] = {}
        for note in context.document.notes or []:
            if note.number.value is not None:
                per_page.setdefault(note.page_number, []).append(str(note.number.value).strip())
        duplicates = sorted(
            f"page {page}: {value}"
            for page, page_values in per_page.items()
            for value, count in Counter(page_values).items()
            if count > 1
        )
        if duplicates:
            return outcome(
                ValidationStatus.FAIL,
                "Each note number is unique in the logical notes section.",
                f"Duplicate note number(s): {duplicates}.",
                f"{self.metadata.rule_id}: duplicate note identifiers were detected.",
                "Renumber or confirm explicitly permitted duplication.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "Each note number is unique in the logical notes section.",
            f"No duplicates among {len(values)} note(s).",
            f"{self.metadata.rule_id}: note identifiers are unique.",
            "No action required.",
            evidence,
        )

    def _evaluate_empty_note(self, context: ValidationContext) -> RuleOutcome:
        notes = context.document.notes or []
        empty = [
            index + 1
            for index, note in enumerate(notes)
            if not note.text.value or not str(note.text.value).strip()
        ]
        evidence = [
            context.evidence(f"notes[{index}].text", note.text)
            for index, note in enumerate(notes)
            if note.text.value is not None
        ]
        if empty:
            return outcome(
                ValidationStatus.FAIL,
                "Every numbered note contains text.",
                f"Empty extracted text in note row(s) {empty}.",
                f"{self.metadata.rule_id}: one or more numbered notes are empty.",
                "Complete or remove the empty note entry.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "Every numbered note contains text.",
            f"All {len(notes)} note(s) contain text.",
            f"{self.metadata.rule_id}: no empty notes were detected.",
            "No action required.",
            evidence,
        )

    def _evaluate_required_phrases(self, context: ValidationContext) -> RuleOutcome:
        config = context.rule_config(self.metadata.rule_id)
        required = [str(value) for value in config.get("required_text", [])]
        if not required:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "Configured phrases are present.",
                "No required phrases are configured for this drawing class.",
                f"{self.metadata.rule_id}: no authoritative phrase requirement is active.",
            )
        note_text = "\n".join(str(note.text.value or "") for note in context.document.notes or [])
        missing = [phrase for phrase in required if phrase.casefold() not in note_text.casefold()]
        evidence = [
            context.evidence(f"notes[{index}].text", note.text)
            for index, note in enumerate(context.document.notes or [])
            if note.text.value
        ]
        if missing:
            return outcome(
                ValidationStatus.FAIL,
                f"Required phrases: {required}.",
                f"Missing phrases: {missing}.",
                f"{self.metadata.rule_id}: configured required note text was not detected.",
                "Review the configured note requirement and drawing notes.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            f"Required phrases: {required}.",
            "All configured phrases were detected.",
            f"{self.metadata.rule_id}: required note text is present.",
            "No action required.",
            evidence,
        )

    def _evaluate_token_detected(self, context: ValidationContext) -> RuleOutcome:
        kind = self.parameters["kind"]
        if kind == "pes":
            refs = [
                ref.designation
                for ref in context.document.standard_references or []
                if ref.designation.value and str(ref.designation.value).upper().startswith("PES")
            ]
        else:
            refs = [
                ref.designation
                for ref in context.document.standard_references or []
                if ref.designation.value and str(ref.designation.value).upper().startswith("ASME")
            ]
        evidence = [context.evidence("standard_references[].designation", field) for field in refs]
        if refs:
            return outcome(
                ValidationStatus.PASS,
                f"Recognize {kind.upper()} references when present.",
                f"Detected {[field.value for field in refs]}.",
                f"{self.metadata.rule_id}: reference tokens were recognized.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.NOT_APPLICABLE,
            f"Recognize {kind.upper()} references when present.",
            "No matching reference was extracted.",
            f"{self.metadata.rule_id}: reference type is not present.",
        )

    def _evaluate_standard_syntax(self, context: ValidationContext) -> RuleOutcome:
        pattern = re.compile(
            r"^(?:PES\d{6}|ASME\s+Y\d{2}(?:\.\d+)*(?:-\d{4})?|"
            r"SAE\s+[A-Z]?\d+|ASTM\s+[A-Z]\d+(?:-\d+)?|FMVSS[-\s]?\d+)$",
            re.I,
        )
        refs = [
            ref.designation
            for ref in context.document.standard_references or []
            if ref.designation.value
        ]
        evidence = [context.evidence("standard_references[].designation", field) for field in refs]
        invalid = [
            str(field.value) for field in refs if not pattern.fullmatch(str(field.value).strip())
        ]
        if invalid:
            return outcome(
                ValidationStatus.WARNING,
                "Extracted standard identifiers match configured syntax families.",
                f"Unrecognized syntax: {invalid}.",
                f"{self.metadata.rule_id}: one or more standard tokens have unknown syntax.",
                "Confirm the identifier; syntax uncertainty is not a compliance decision.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "Extracted standard identifiers match configured syntax families.",
            f"Validated syntax for {len(refs)} reference(s).",
            f"{self.metadata.rule_id}: standard identifier syntax is recognized.",
            "No action required.",
            evidence,
        )

    def _evaluate_standard_duplicates(self, context: ValidationContext) -> RuleOutcome:
        refs = [
            ref.designation
            for ref in context.document.standard_references or []
            if ref.designation.value
        ]
        values = [str(field.value).strip().upper() for field in refs]
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        evidence = [context.evidence("standard_references[].designation", field) for field in refs]
        status = ValidationStatus.WARNING if duplicates else ValidationStatus.PASS
        actual = (
            f"Duplicate reference(s): {duplicates}."
            if duplicates
            else "No duplicate references detected."
        )
        return outcome(
            status,
            "Standard references are not duplicated unnecessarily.",
            actual,
            f"{self.metadata.rule_id}: {actual}",
            "Review duplicates for intentional repetition."
            if duplicates
            else "No action required.",
            evidence,
        )

    def _evaluate_standard_master(self, context: ValidationContext) -> RuleOutcome:
        master = context.rule_master_data or {}
        known = {str(value).upper() for value in master.get("standards", [])}
        if not known:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "References are checked against an authoritative standards master.",
                "No authoritative standards master is configured.",
                f"{self.metadata.rule_id}: unknown/obsolete decisions cannot be made without master data.",
                "Provide controlled standards master data before activating this rule.",
            )
        refs = [
            ref.designation
            for ref in context.document.standard_references or []
            if ref.designation.value
        ]
        unknown = [str(field.value) for field in refs if str(field.value).upper() not in known]
        evidence = [context.evidence("standard_references[].designation", field) for field in refs]
        if unknown:
            return outcome(
                ValidationStatus.WARNING,
                "References exist in the authoritative standards master.",
                f"Unknown identifiers: {unknown}.",
                f"{self.metadata.rule_id}: references absent from the configured master were detected.",
                "Confirm master-data currency and reference identity.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "References exist in the authoritative standards master.",
            "All references were found.",
            f"{self.metadata.rule_id}: references match the configured master.",
            "No action required.",
            evidence,
        )

    def _table_items(self, context: ValidationContext) -> list[BOMItem]:
        family = self.parameters["family"]
        return {
            "bom": context.document.bom_items,
            "part_list": context.document.part_list_items,
            "service_parts": context.document.service_part_items,
        }[family] or []

    def _table_groups(self, context: ValidationContext) -> list[list[BOMItem]]:
        groups: list[list[BOMItem]] = []
        current: list[BOMItem] = []
        previous_page: int | None = None
        for item in self._table_items(context):
            starts_group = (previous_page is not None and item.page_number != previous_page) or (
                item.item_no.value is None
                and item.quantity.value is None
                and item.part_number.value is not None
                and bool(current)
            )
            if starts_group and current:
                groups.append(current)
                current = []
            current.append(item)
            previous_page = item.page_number
        if current:
            groups.append(current)
        return groups

    def _evaluate_table_field(self, context: ValidationContext) -> RuleOutcome:
        items = self._table_items(context)
        field_name = self.parameters["field"]
        label = self.parameters.get("label", field_name.replace("_", " "))
        missing: list[int] = []
        low: list[int] = []
        evidence: list[ValidationEvidence] = []
        for index, item in enumerate(items):
            field = getattr(item, field_name)
            is_assembly_header = (
                field_name in {"item_no", "quantity"}
                and item.item_no.value is None
                and item.quantity.value is None
                and item.part_number.value is not None
                and item.description.value is not None
            )
            if is_assembly_header:
                continue
            if field.value is None:
                missing.append(index + 1)
            elif not context.has_reliable_value(field):
                low.append(index + 1)
                evidence.append(
                    context.evidence(f"{self.parameters['family']}[{index}].{field_name}", field)
                )
            else:
                evidence.append(
                    context.evidence(f"{self.parameters['family']}[{index}].{field_name}", field)
                )
        if low:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                f"Every row has reliable {label} evidence.",
                f"Low-confidence row(s): {low}.",
                f"{self.metadata.rule_id}: extraction uncertainty prevents a structural decision.",
                "Confirm the cited table rows.",
                evidence,
            )
        if missing:
            return outcome(
                ValidationStatus.FAIL,
                f"Every row contains {label}.",
                f"Missing in row(s): {missing}.",
                f"{self.metadata.rule_id}: table row {label} is missing.",
                f"Complete the {label} for affected rows.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            f"Every row contains {label}.",
            f"Present in all {len(items)} row(s).",
            f"{self.metadata.rule_id}: table row {label} is present.",
            "No action required.",
            evidence,
        )

    def _evaluate_table_sequence(self, context: ValidationContext) -> RuleOutcome:
        items = self._table_items(context)
        fields = [item.item_no for item in items]
        evidence = [
            context.evidence(f"{self.parameters['family']}[].item_no", field)
            for field in fields
            if field.value is not None
        ]
        if any(field.value is None or not context.has_reliable_value(field) for field in fields):
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Item identifiers are reliable before sequencing.",
                "At least one item identifier is missing or low confidence.",
                f"{self.metadata.rule_id}: sequence dependency is unresolved.",
                "Confirm item numbers.",
                evidence,
            )
        values = [str(field.value).strip() for field in fields]
        if any(not value.isdigit() for value in values):
            return outcome(
                ValidationStatus.MANUAL_REVIEW,
                "Numeric item sequence where applicable.",
                f"Detected {values}.",
                f"{self.metadata.rule_id}: nonnumeric item convention requires review.",
                "Confirm the table item-number convention.",
                evidence,
            )
        numbers = [int(value) for value in values]
        expected = list(range(min(numbers), max(numbers) + 1))
        if numbers == expected:
            return outcome(
                ValidationStatus.PASS,
                "Item numbers form a complete ordered sequence.",
                f"Detected {numbers}.",
                f"{self.metadata.rule_id}: item sequence is complete.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.WARNING,
            "Item numbers form a complete ordered sequence.",
            f"Detected {numbers}; expected {expected}.",
            f"{self.metadata.rule_id}: sequence gaps or ordering differences were detected.",
            "Review table item numbering.",
            evidence,
        )

    def _evaluate_table_duplicates(self, context: ValidationContext) -> RuleOutcome:
        field_name = self.parameters["field"]
        fields = [
            getattr(item, field_name)
            for item in self._table_items(context)
            if getattr(item, field_name).value is not None
        ]
        duplicates: list[str] = []
        for group_index, group in enumerate(self._table_groups(context), start=1):
            group_values = [
                str(getattr(item, field_name).value).strip().upper()
                for item in group
                if getattr(item, field_name).value is not None
            ]
            duplicates.extend(
                f"table {group_index}: {value}"
                for value, count in Counter(group_values).items()
                if count > 1
            )
        evidence = [
            context.evidence(f"{self.parameters['family']}[].{field_name}", field)
            for field in fields
        ]
        if duplicates:
            status = ValidationStatus(self.parameters.get("duplicate_status", "FAIL"))
            return outcome(
                status,
                f"{field_name.replace('_', ' ')} values satisfy the configured uniqueness expectation.",
                f"Duplicate value(s): {duplicates}.",
                f"{self.metadata.rule_id}: duplicate table values were detected.",
                "Review whether repetition is intentional.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            f"{field_name.replace('_', ' ')} values satisfy the configured uniqueness expectation.",
            "No duplicates detected.",
            f"{self.metadata.rule_id}: no duplicate table values were detected.",
            "No action required.",
            evidence,
        )

    def _evaluate_positive_quantity(self, context: ValidationContext) -> RuleOutcome:
        fields = [item.quantity for item in self._table_items(context)]
        evidence = [
            context.evidence(f"{self.parameters['family']}[].quantity", field)
            for field in fields
            if field.value is not None
        ]
        invalid: list[str] = []
        unresolved: list[str] = []
        for field in fields:
            if field.value is None or not context.has_reliable_value(field):
                unresolved.append(str(field.value))
                continue
            try:
                if Decimal(str(field.value).strip()) <= 0:
                    invalid.append(str(field.value))
            except InvalidOperation:
                unresolved.append(str(field.value))
        if unresolved:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Quantities are reliable numeric values before positivity checking.",
                f"Unresolved quantities: {unresolved}.",
                f"{self.metadata.rule_id}: quantity syntax or confidence prevents evaluation.",
                "Confirm the quantity values.",
                evidence,
            )
        if invalid:
            return outcome(
                ValidationStatus.FAIL,
                "Every quantity is greater than zero.",
                f"Non-positive quantities: {invalid}.",
                f"{self.metadata.rule_id}: non-positive table quantity detected.",
                "Correct or explain the affected quantity.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "Every quantity is greater than zero.",
            "All quantities are positive.",
            f"{self.metadata.rule_id}: table quantities are positive.",
            "No action required.",
            evidence,
        )

    def _evaluate_part_pattern(self, context: ValidationContext) -> RuleOutcome:
        config = context.rule_config(self.metadata.rule_id)
        pattern_text = config.get("pattern")
        if not pattern_text:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "Part numbers match a source-authorized pattern.",
                "No part-number pattern is configured for this applicability class.",
                f"{self.metadata.rule_id}: no global part-number format is assumed.",
            )
        if self.parameters.get("family"):
            fields = [
                item.part_number
                for item in self._table_items(context)
                if item.part_number.value is not None
            ]
        else:
            fields = [context.document.part_numbers]
        values: list[tuple[str, ExtractedField[Any]]] = []
        for field in fields:
            raw_values = field.value if isinstance(field.value, list) else [field.value]
            values.extend((str(value), field) for value in raw_values if value is not None)
        evidence = [context.evidence("part_number", field) for _, field in values]
        invalid = [value for value, _ in values if not re.fullmatch(str(pattern_text), value)]
        if invalid:
            return outcome(
                ValidationStatus.WARNING,
                f"Applicable part numbers match {pattern_text!r}.",
                f"Nonmatching value(s): {invalid}.",
                f"{self.metadata.rule_id}: configured part-number format difference detected.",
                "Confirm the configured format applies to these identifiers.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            f"Applicable part numbers match {pattern_text!r}.",
            "All applicable values match.",
            f"{self.metadata.rule_id}: part-number syntax matches the configured pattern.",
            "No action required.",
            evidence,
        )

    def _evaluate_description_length(self, context: ValidationContext) -> RuleOutcome:
        maximum = int(context.rule_config(self.metadata.rule_id).get("maximum", 0))
        if maximum <= 0:
            return outcome(
                ValidationStatus.NOT_APPLICABLE,
                "Descriptions satisfy a configured maximum length.",
                "No authoritative maximum is configured.",
                f"{self.metadata.rule_id}: ambiguous source wording is not converted into a guessed limit.",
            )
        fields = [
            item.description
            for item in self._table_items(context)
            if item.description.value is not None
        ]
        long_values = [str(field.value) for field in fields if len(str(field.value)) > maximum]
        evidence = [
            context.evidence(f"{self.parameters['family']}[].description", field)
            for field in fields
        ]
        if long_values:
            return outcome(
                ValidationStatus.WARNING,
                f"Description length <= {maximum} characters.",
                f"{len(long_values)} description(s) exceed the configured maximum.",
                f"{self.metadata.rule_id}: configured description-length constraint was exceeded.",
                "Review description wording and the governing checklist requirement.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            f"Description length <= {maximum} characters.",
            "All descriptions satisfy the configured maximum.",
            f"{self.metadata.rule_id}: description lengths are within the configured limit.",
            "No action required.",
            evidence,
        )

    def _evaluate_supplier_marker(self, context: ValidationContext) -> RuleOutcome:
        supplier = context.document.supplier_info
        field = supplier.supplier_drawing_marker if supplier else ExtractedField()
        evidence = self._field_evidence(context, "supplier_info.supplier_drawing_marker", field)
        if not context.has_reliable_value(field):
            return outcome(
                ValidationStatus.FAIL if field.value is None else ValidationStatus.MANUAL_REVIEW,
                "Explicit supplier-drawing marker is present.",
                "No reliable supplier marker was extracted."
                if field.value is None
                else f"Marker confidence is {field.confidence:.2f}.",
                f"{self.metadata.rule_id}: supplier classification lacks reliable explicit marker evidence.",
                "Verify the supplier drawing banner.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "Explicit supplier-drawing marker is present.",
            f"Detected {field.value!r}.",
            f"{self.metadata.rule_id}: explicit supplier marker supports classification.",
            "No action required.",
            evidence,
        )

    def _evaluate_supplier_phrase(self, context: ValidationContext) -> RuleOutcome:
        marker = (
            context.document.supplier_info.supplier_drawing_marker
            if context.document.supplier_info
            else ExtractedField()
        )
        phrase = self.parameters["phrase"]
        evidence = self._field_evidence(context, "supplier_info.supplier_drawing_marker", marker)
        if marker.value and phrase.casefold() in str(marker.value).casefold():
            return outcome(
                ValidationStatus.PASS,
                f"Supplier marker contains {phrase!r}.",
                f"Detected {marker.value!r}.",
                f"{self.metadata.rule_id}: required supplier phrase is present.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.FAIL,
            f"Supplier marker contains {phrase!r}.",
            f"Detected {marker.value!r}.",
            f"{self.metadata.rule_id}: required supplier phrase was not detected.",
            "Review the supplier drawing banner.",
            evidence,
        )

    def _evaluate_supplier_identity(self, context: ValidationContext) -> RuleOutcome:
        supplier = context.document.supplier_info
        if not supplier:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Supplier or manufacturer identity is available.",
                "Supplier evidence object is unavailable.",
                f"{self.metadata.rule_id}: dependency is missing.",
            )
        fields = [
            ("supplier_name", supplier.supplier_name),
            ("manufacturer_name", supplier.manufacturer_name),
        ]
        evidence = [
            context.evidence(f"supplier_info.{name}", field)
            for name, field in fields
            if field.value is not None
        ]
        reliable = [(name, field) for name, field in fields if context.has_reliable_value(field)]
        if reliable:
            return outcome(
                ValidationStatus.PASS,
                "Supplier or manufacturer identity is present where required.",
                f"Detected {[(name, field.value) for name, field in reliable]}.",
                f"{self.metadata.rule_id}: supplier/manufacturer identity is present.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.MANUAL_REVIEW,
            "Supplier or manufacturer identity is present where required.",
            "No reliable identity was extracted.",
            f"{self.metadata.rule_id}: supplier identity requires review.",
            "Confirm supplier/manufacturer metadata.",
            evidence,
        )

    def _evaluate_supplier_part(self, context: ValidationContext) -> RuleOutcome:
        supplier = context.document.supplier_info
        if not supplier:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Supplier part identifiers are available.",
                "Supplier evidence object is unavailable.",
                f"{self.metadata.rule_id}: dependency is missing.",
            )
        fields = [supplier.supplier_part_number, supplier.supplier_part_numbers]
        mappings = supplier.manufacturer_part_number_mappings or []
        fields.extend(mapping.manufacturer_part_number for mapping in mappings)
        evidence = [
            context.evidence("supplier_info.part_numbers", field)
            for field in fields
            if field.value is not None
        ]
        reliable = [field for field in fields if context.has_reliable_value(field)]
        if reliable:
            count = sum(
                len(field.value) if isinstance(field.value, list) else 1 for field in reliable
            )
            return outcome(
                ValidationStatus.PASS,
                "At least one explicit supplier/manufacturer part identifier is present.",
                f"Detected {count} identifier value(s); mappings are preserved rather than collapsed.",
                f"{self.metadata.rule_id}: supplier part-number evidence is present.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.MANUAL_REVIEW,
            "At least one explicit supplier/manufacturer part identifier is present.",
            "No reliable part identifier was extracted.",
            f"{self.metadata.rule_id}: supplier part identity requires review.",
            "Confirm supplier/manufacturer part metadata.",
            evidence,
        )

    def _evaluate_supplier_raster(self, context: ValidationContext) -> RuleOutcome:
        regions = context.document.supplier_raster_regions
        if not regions:
            return outcome(
                ValidationStatus.WARNING,
                "Supplier-original raster regions are reported when present.",
                "No supplier raster region was detected.",
                f"{self.metadata.rule_id}: no raster supplier-original region is available.",
                "Confirm whether the supplier original is native vector/text or absent.",
            )
        evidence = [
            ValidationEvidence(
                page_number=region.page_number,
                bounding_box=region.bounding_box,
                source_field="supplier_raster_regions",
                extracted_value="supplier raster region",
                raw_text=region.raw_text,
                extraction_method=region.extraction_method,
                confidence=region.confidence,
            )
            for region in regions
        ]
        return outcome(
            ValidationStatus.PASS,
            "Supplier-original raster regions are reported when present.",
            f"Detected {len(regions)} region(s).",
            f"{self.metadata.rule_id}: supplier raster content is explicitly bounded; internal content remains unparsed.",
            "No action required for Level 2; use human review for internal raster content.",
            evidence,
        )

    def _missing_visual_dependency(self, context: ValidationContext) -> RuleOutcome | None:
        if context.vision_report is not None:
            return None
        return outcome(
            ValidationStatus.NOT_EVALUATED,
            "Reliable Level-3 visual evidence is available.",
            "Level-3 analysis has not been run for this drawing.",
            f"{self.metadata.rule_id}: visual evidence dependency is unavailable.",
            "Run Level-3 visual analysis, then re-run validation.",
        )

    def _visual_evidence(
        self, context: ValidationContext, objects: list[Any]
    ) -> list[ValidationEvidence]:
        return [context.visual_evidence(item) for item in objects]

    @staticmethod
    def _visual_gate_status(
        context: ValidationContext, object_type: str
    ) -> ValidationStatus:
        return (
            ValidationStatus.WARNING
            if context.partial_visual_objects(object_type)
            else ValidationStatus.MANUAL_REVIEW
        )

    def _evaluate_visual_revision(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("REVISION_TRIANGLE")
        reliable = context.reliable_visual_objects("REVISION_TRIANGLE")
        evidence = self._visual_evidence(context, objects)
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Revision-table identifiers correspond to detected revision triangles.",
                "No revision triangle was detected; detector completeness is not established.",
                f"{self.metadata.rule_id}: no visual triangle evidence is available.",
                "Review the drawing area manually.",
            )
        if not reliable:
            return outcome(
                self._visual_gate_status(context, "REVISION_TRIANGLE"),
                "Revision triangles meet the configured automatic confidence threshold.",
                f"Detected {len(objects)} low/medium-confidence candidate(s).",
                f"{self.metadata.rule_id}: visual confidence gating prevents automation.",
                "Confirm or reject the highlighted candidates.",
                evidence,
            )
        expected = {
            str(record.revision.value).strip().upper()
            for record in context.document.revision_records or []
            if record.revision.value
        }
        detected = {
            str(item.attributes.get("candidate_revision_identifier") or "").strip().upper()
            for item in reliable
            if item.attributes.get("candidate_revision_identifier")
        }
        if not detected:
            return outcome(
                ValidationStatus.MANUAL_REVIEW,
                "Reliable revision triangles have recognized identifiers.",
                f"Detected {len(reliable)} reliable triangle(s), but no identifier was recognized.",
                f"{self.metadata.rule_id}: geometry is available but cross-reference text is unresolved.",
                "Confirm triangle labels manually.",
                evidence,
            )
        unexpected = sorted(detected - expected)
        status = ValidationStatus.WARNING if unexpected else ValidationStatus.PASS
        return outcome(
            status,
            "Detected revision-triangle identifiers occur in the extracted revision table.",
            f"Revision table={sorted(expected)}; detected triangles={sorted(detected)}.",
            f"{self.metadata.rule_id}: "
            + (
                f"unmatched identifiers {unexpected} require review."
                if unexpected
                else "visual and table identifiers agree."
            ),
            "Review unmatched identifiers." if unexpected else "No action required.",
            evidence,
        )

    def _evaluate_visual_balloons(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("BOM_BALLOON")
        reliable = context.reliable_visual_objects("BOM_BALLOON")
        evidence = self._visual_evidence(context, objects)
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "BOM item numbers can be compared with detected balloon numbers.",
                "No balloon evidence was detected; detector completeness is not established.",
                f"{self.metadata.rule_id}: no visual balloon evidence is available.",
                "Review balloon annotations manually.",
            )
        if not reliable:
            return outcome(
                self._visual_gate_status(context, "BOM_BALLOON"),
                "Balloon evidence meets its configured automatic threshold.",
                f"Detected {len(objects)} candidate(s), all below the automatic threshold.",
                f"{self.metadata.rule_id}: low-confidence visual evidence cannot drive a failure.",
                "Confirm or reject the highlighted balloons.",
                evidence,
            )
        expected = {
            str(item.item_no.value).strip().upper()
            for item in context.document.bom_items or []
            if item.item_no.value
        }
        detected = {
            str(item.attributes.get("item_number") or item.normalized_text or "").strip().upper()
            for item in reliable
        }
        missing_items = sorted(expected - detected)
        extra_items = sorted(detected - expected)
        status = (
            ValidationStatus.PASS
            if not missing_items and not extra_items
            else ValidationStatus.WARNING
        )
        return outcome(
            status,
            "Reliable BOM item numbers and balloon item numbers agree.",
            f"BOM={sorted(expected)}; balloons={sorted(detected)}; missing={missing_items}; extra={extra_items}.",
            f"{self.metadata.rule_id}: "
            + (
                "reliable visual and BOM identifiers agree."
                if status == ValidationStatus.PASS
                else "a cross-reference difference requires review; it is not treated as an automatic failure."
            ),
            "Review the highlighted cross-reference differences."
            if status == ValidationStatus.WARNING
            else "No action required.",
            evidence,
        )

    def _evaluate_visual_balloon_quantity(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("BOM_BALLOON")
        evidence = self._visual_evidence(context, objects)
        split_objects = [
            item
            for item in objects
            if item.attributes.get("shape") == "split_circle"
            and str(item.attributes.get("lower_compartment_text") or "").isdigit()
        ]
        if objects and len(split_objects) == len(objects):
            totals: dict[str, int] = {}
            for item in split_objects:
                item_number = str(
                    item.attributes.get("item_number") or item.normalized_text or ""
                ).strip()
                totals[item_number] = totals.get(item_number, 0) + int(
                    item.attributes["lower_compartment_text"]
                )
            return outcome(
                ValidationStatus.MANUAL_REVIEW,
                "Split-balloon lower-compartment semantics are confirmed before quantity comparison.",
                f"Detected explicit lower-compartment totals by item: {dict(sorted(totals.items()))}.",
                f"{self.metadata.rule_id}: the visible text is extracted, but its quantity semantics require reviewer confirmation.",
                "Confirm the split-balloon convention and compare the displayed totals with the BOM.",
                evidence,
            )
        return outcome(
            ValidationStatus.MANUAL_REVIEW if objects else ValidationStatus.NOT_EVALUATED,
            "Balloon occurrence semantics are known before quantity comparison.",
            f"Detected {len(objects)} balloon candidate(s); occurrence semantics are not established.",
            f"{self.metadata.rule_id}: geometry alone cannot prove required reference quantity.",
            "Confirm balloon occurrence semantics manually.",
            evidence,
        )

    def _evaluate_visual_note_callouts(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("FLAG_NOTE")
        reliable = context.reliable_visual_objects("FLAG_NOTE")
        evidence = self._visual_evidence(context, objects)
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Flag-note numbers can be compared with extracted note definitions.",
                "No flag-note evidence was detected.",
                f"{self.metadata.rule_id}: no visual note-callout evidence is available.",
            )
        if not reliable:
            return outcome(
                self._visual_gate_status(context, "FLAG_NOTE"),
                "Flag-note evidence meets its automatic threshold.",
                f"Detected {len(objects)} low/medium-confidence candidate(s).",
                f"{self.metadata.rule_id}: confidence gating requires human review.",
                evidence=evidence,
            )
        definitions = {
            str(note.number.value).strip()
            for note in context.document.notes or []
            if note.number.value
        }
        callouts = {str(item.attributes.get("note_number")) for item in reliable}
        undefined = sorted(callouts - definitions)
        status = ValidationStatus.WARNING if undefined else ValidationStatus.PASS
        return outcome(
            status,
            "Reliable flag-note callouts have extracted note definitions.",
            f"Definitions={sorted(definitions)}; callouts={sorted(callouts)}.",
            f"{self.metadata.rule_id}: "
            + (
                f"undefined callouts {undefined} require review."
                if undefined
                else "callouts resolve to definitions."
            ),
            evidence=evidence,
        )

    def _evaluate_visual_scc(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("SCC_SYMBOL")
        evidence = self._visual_evidence(context, objects)
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "SCC symbols are detected from a controlled verified symbol reference.",
                "No controlled SCC template is configured; symbol shape was not guessed.",
                f"{self.metadata.rule_id}: SCC visual evidence remains unavailable.",
                "Supply an approved SCC symbol reference and ground truth before automation.",
            )
        return outcome(
            ValidationStatus.MANUAL_REVIEW,
            "Detected SCC symbols are spatially cross-referenced to their governing context.",
            f"Detected {len(objects)} SCC candidate(s); semantic context requires review.",
            f"{self.metadata.rule_id}: SCC evidence is available but not engineering-approved.",
            evidence=evidence,
        )

    def _evaluate_visual_supplier_ocr(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("SUPPLIER_RASTER_TEXT")
        evidence = self._visual_evidence(context, objects)
        return outcome(
            ValidationStatus.MANUAL_REVIEW if objects else ValidationStatus.NOT_EVALUATED,
            "Supplier-original raster text is available for evidence-based internal checks.",
            f"Recovered targeted OCR evidence from {len(objects)} raster region(s).",
            f"{self.metadata.rule_id}: targeted OCR is preserved separately and does not overwrite wrapper evidence.",
            "Review OCR text before applying supplier-internal checks.",
            evidence,
        )

    def _evaluate_visual_datums(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("DATUM_SYMBOL")
        reliable = context.reliable_visual_objects("DATUM_SYMBOL")
        evidence = self._visual_evidence(context, objects)
        identifiers = [str(item.attributes.get("identifier") or "") for item in reliable]
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Reliable datum symbols are available for syntax checks.",
                "No datum symbols were detected.",
                f"{self.metadata.rule_id}: visual datum evidence is unavailable.",
            )
        if not reliable:
            return outcome(
                self._visual_gate_status(context, "DATUM_SYMBOL"),
                "Datum evidence meets its configured automatic threshold.",
                f"Detected {len(objects)} candidate(s) below the automatic threshold.",
                f"{self.metadata.rule_id}: confidence gating requires human review.",
                evidence=evidence,
            )
        duplicates = sorted(value for value, count in Counter(identifiers).items() if count > 1)
        if self.metadata.rule_id == "GDT-002":
            status = ValidationStatus.WARNING if duplicates else ValidationStatus.PASS
            actual = (
                f"Duplicate identifiers={duplicates}." if duplicates else "No duplicates detected."
            )
        elif self.metadata.rule_id == "GDT-003":
            status = ValidationStatus.WARNING if duplicates else ValidationStatus.PASS
            actual = f"Detected datum sequence={identifiers}; syntax-only review."
        else:
            status = ValidationStatus.PASS
            actual = f"Detected identifiers={identifiers}."
        return outcome(
            status,
            "Datum identifiers are recognized for syntax-only checks.",
            actual,
            f"{self.metadata.rule_id}: datum syntax evidence is available; functional selection is not evaluated.",
            evidence=evidence,
        )

    def _evaluate_visual_gdt(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        objects = context.visual_objects("GDT_FRAME")
        reliable = context.reliable_visual_objects("GDT_FRAME")
        evidence = self._visual_evidence(context, objects)
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Feature-control frames are detected for syntax-only token checks.",
                "No GD&T frame was detected.",
                f"{self.metadata.rule_id}: visual frame evidence is unavailable.",
            )
        if not reliable:
            return outcome(
                self._visual_gate_status(context, "GDT_FRAME"),
                "GD&T frame evidence meets its automatic threshold.",
                f"Detected {len(objects)} candidate(s) below the automatic threshold.",
                f"{self.metadata.rule_id}: confidence gating requires human review.",
                evidence=evidence,
            )
        tokenized = [item for item in reliable if item.attributes.get("recognized_tokens")]
        if self.metadata.rule_id == "GDT-005":
            positioned = [
                item
                for item in tokenized
                if str(item.attributes.get("characteristic") or "").upper()
                in {"POSITION", "⌖", "TRUE POSITION"}
            ]
            status = ValidationStatus.PASS if positioned else ValidationStatus.NOT_EVALUATED
            actual = f"Recognized position frames={len(positioned)}."
        else:
            status = ValidationStatus.PASS if tokenized else ValidationStatus.MANUAL_REVIEW
            actual = f"Tokenized {len(tokenized)} of {len(reliable)} reliable frame(s)."
        return outcome(
            status,
            "Detected GD&T frames contain reliably recognized syntax tokens.",
            actual,
            f"{self.metadata.rule_id}: syntax-only visual evidence is available; functional correctness is not evaluated.",
            evidence=evidence,
        )

    def _evaluate_visual_views(self, context: ValidationContext) -> RuleOutcome:
        missing = self._missing_visual_dependency(context)
        if missing:
            return missing
        kinds = {
            "VIEW-003": "SECTION_ARROW",
            "VIEW-004": "DETAIL_CALLOUT",
        }
        object_type = kinds.get(self.metadata.rule_id, "VIEW_ARROW")
        objects = context.visual_objects(object_type)
        reliable = context.reliable_visual_objects(object_type)
        evidence = self._visual_evidence(context, objects)
        labels = [item.normalized_text for item in reliable if item.normalized_text]
        if self.metadata.rule_id == "VIEW-005":
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Local view-scale labels are reliably associated with view objects.",
                "The current detector does not classify local scale labels.",
                f"{self.metadata.rule_id}: local-scale semantics remain unavailable.",
                evidence=evidence,
            )
        if not objects:
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "View annotation objects are available for syntax checks.",
                f"No {object_type} evidence was detected.",
                f"{self.metadata.rule_id}: view annotation evidence is unavailable.",
            )
        if not reliable:
            return outcome(
                self._visual_gate_status(context, object_type),
                "View annotation evidence meets its automatic threshold.",
                f"Detected {len(objects)} lower-confidence candidate(s).",
                f"{self.metadata.rule_id}: confidence gating requires review.",
                evidence=evidence,
            )
        duplicates = sorted(value for value, count in Counter(labels).items() if count > 1)
        status = (
            ValidationStatus.WARNING
            if self.metadata.rule_id == "VIEW-002" and duplicates
            else ValidationStatus.PASS
        )
        return outcome(
            status,
            "Recognized view annotation labels satisfy syntax-only checks.",
            f"Detected labels={labels}; duplicates={duplicates}.",
            f"{self.metadata.rule_id}: view-label syntax evidence is available; view completeness is not evaluated.",
            evidence=evidence,
        )

    def _evaluate_framework(self, context: ValidationContext) -> RuleOutcome:
        del context
        status = ValidationStatus(self.parameters.get("status", "NOT_EVALUATED"))
        reason = self.parameters.get(
            "reason", "Required Level-1 evidence or engineering authority is unavailable."
        )
        return outcome(
            status,
            self.parameters.get(
                "expected",
                "The requirement is evaluated only when reliable supporting evidence exists.",
            ),
            reason,
            f"{self.metadata.rule_id}: {reason}",
            self.parameters.get(
                "recommendation", "Route this check to an authorized engineering reviewer."
            ),
        )

    def _evaluate_xref_supplier(self, context: ValidationContext) -> RuleOutcome:
        classification = context.document.document_type
        marker = (
            context.document.supplier_info.supplier_drawing_marker
            if context.document.supplier_info
            else ExtractedField()
        )
        evidence = self._field_evidence(
            context, "document_type", classification
        ) + self._field_evidence(context, "supplier_info.supplier_drawing_marker", marker)
        if not context.has_reliable_value(classification) or not context.has_reliable_value(marker):
            return outcome(
                ValidationStatus.NOT_EVALUATED,
                "Supplier classification and explicit marker are both reliable.",
                "One or both evidence sources are missing or low confidence.",
                f"{self.metadata.rule_id}: cross-reference dependencies are unresolved.",
                "Confirm classification and marker extraction.",
                evidence,
            )
        is_supplier = classification.value == "SUPPLIER_DRAWING"
        marker_present = "SUPPLIER DRAWING" in str(marker.value).upper()
        if is_supplier == marker_present:
            return outcome(
                ValidationStatus.PASS,
                "Supplier classification agrees with explicit supplier marker evidence.",
                f"Classification {classification.value!r}; marker {marker.value!r}.",
                f"{self.metadata.rule_id}: classification and marker agree.",
                "No action required.",
                evidence,
            )
        return outcome(
            ValidationStatus.FAIL,
            "Supplier classification agrees with explicit supplier marker evidence.",
            f"Classification {classification.value!r}; marker {marker.value!r}.",
            f"{self.metadata.rule_id}: supplier classification conflicts with explicit marker evidence.",
            "Review document classification evidence.",
            evidence,
        )

    def _evaluate_xref_standards_notes(self, context: ValidationContext) -> RuleOutcome:
        refs = [
            str(ref.designation.value)
            for ref in context.document.standard_references or []
            if ref.designation.value
        ]
        note_text = "\n".join(str(note.text.value or "") for note in context.document.notes or [])
        missing = [ref for ref in refs if ref.casefold() not in note_text.casefold()]
        evidence = [
            context.evidence("standard_references[].designation", ref.designation)
            for ref in context.document.standard_references or []
            if ref.designation.value
        ]
        evidence.extend(
            context.evidence(f"notes[{index}].text", note.text)
            for index, note in enumerate(context.document.notes or [])
            if note.text.value
        )
        if missing:
            return outcome(
                ValidationStatus.WARNING,
                "Extracted standard references can be located in extracted note wording.",
                f"References not found in notes: {missing}.",
                f"{self.metadata.rule_id}: standard-to-note relationship is incomplete.",
                "Verify whether references originate outside the notes section.",
                evidence,
            )
        return outcome(
            ValidationStatus.PASS,
            "Extracted standard references can be located in extracted note wording.",
            "All extracted references occur in note text.",
            f"{self.metadata.rule_id}: standards and notes evidence agree.",
            "No action required.",
            evidence,
        )
