from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .job_manager import JobManager
from .llm_client import ImagePayload, LlmClient, LlmRequest, MockLlmClient
from .models.api import (
    ExtractionIssue,
    JobStatus,
    NormalizationNote as ApiNormalizationNote,
    UnknownField,
    ValidationReport,
)
from .normalizer import NormalizationNote as NormalizationNoteRecord, NormalizationResult, normalize_nsm_payload
from .prompt_builder import PromptBuilder, PromptRequest, VersionedPromptBuilder
from .extractor.raw_response_parser import RawResponseParser
from .validator import ValidationResult, validate_nsm_payload
from .validator.quality_warnings import PROVENANCE_CONFIDENCE_THRESHOLD


@dataclass(frozen=True)
class ImageToNsmSubmission:
    filename: str
    content_type: str
    size_bytes: int
    data: bytes
    context: Optional[str]


class ImageToNsmPipeline:
    def __init__(
        self,
        job_manager: JobManager,
        *,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_client: Optional[LlmClient] = None,
        raw_parser: Optional[RawResponseParser] = None,
        normalizer=normalize_nsm_payload,
        validator=validate_nsm_payload,
    ) -> None:
        self._job_manager = job_manager
        self._prompt_builder = prompt_builder or VersionedPromptBuilder()
        self._llm_client = llm_client or MockLlmClient()
        self._raw_parser = raw_parser or RawResponseParser(strip_code_fences=False)
        self._normalizer = normalizer
        self._validator = validator

    def submit(self, submission: ImageToNsmSubmission):
        job = self._job_manager.create_job(input_filename=submission.filename)
        self._job_manager.update_job(
            job.job_id,
            input_content_type=submission.content_type,
            input_size_bytes=submission.size_bytes,
            input_context=submission.context,
            input_image_bytes=submission.data,
        )
        self._job_manager.set_status(job.job_id, JobStatus.pending)
        self._log(job.job_id, "info", "Job accepted for processing.")
        try:
            self._run_pipeline(job.job_id, submission)
        except Exception as exc:
            self._job_manager.update_job(
                job.job_id,
                status=JobStatus.failed,
                errors=[_issue("PIPELINE_ERROR", f"Pipeline failure: {exc}", severity="error")],
            )
            self._log(job.job_id, "error", f"Pipeline failure: {exc}")
        return self._job_manager.get_job(job.job_id) or job

    def _run_pipeline(self, job_id: str, submission: ImageToNsmSubmission) -> None:
        self._job_manager.set_status(job_id, JobStatus.running)
        self._log(job_id, "info", "Pipeline started.")

        prompt_spec = self._prompt_builder.build(PromptRequest(context=submission.context))
        self._log(job_id, "info", f"Prompt built (version {prompt_spec.version}).")
        llm_request = LlmRequest(
            image=ImagePayload(
                filename=submission.filename,
                content_type=submission.content_type,
                data=submission.data,
            ),
            prompt=prompt_spec.text,
            prompt_version=prompt_spec.version,
            context=submission.context,
        )
        llm_response = self._llm_client.generate(llm_request)
        raw_output = llm_response.raw_output
        self._job_manager.update_job(job_id, raw_output=raw_output)
        self._log(job_id, "info", "Raw LLM output stored.")

        parse_result = self._raw_parser.parse(raw_output)
        issues: List[ExtractionIssue] = list(parse_result.errors)
        if parse_result.payload is None:
            report = ValidationReport(valid=False)
            self._job_manager.update_job(
                job_id,
                status=JobStatus.failed,
                validation_report=report.model_dump(),
                errors=issues,
            )
            self._log(job_id, "warning", "LLM output parsing failed.")
            return

        normalization_result: NormalizationResult = self._normalizer(parse_result.payload)
        normalized_payload = normalization_result.payload
        self._log(job_id, "info", "Normalization completed.")

        validation_result: ValidationResult = self._validator(normalized_payload)
        validation_report = _to_validation_report(validation_result, normalization_result.notes)
        self._log(job_id, "info", "Validation completed.")

        issues.extend(_issues_from_validation(validation_result))

        unknowns = _collect_unknowns(normalized_payload)
        issues.extend(_issues_from_unknowns(unknowns))

        low_confidence = _collect_low_confidence(normalized_payload, PROVENANCE_CONFIDENCE_THRESHOLD)
        issues.extend(_issues_from_low_confidence(low_confidence))

        confidence = _aggregate_confidence(normalized_payload)
        provenance = _aggregate_provenance(normalized_payload, confidence)

        status = JobStatus.succeeded if validation_result.valid else JobStatus.failed
        final_nsm = normalized_payload if validation_result.valid else None

        self._job_manager.update_job(
            job_id,
            status=status,
            normalized_output=normalized_payload,
            nsm=final_nsm,
            validation_report=validation_report.model_dump(),
            errors=issues,
            unknowns=[unknown.model_dump() for unknown in unknowns],
            confidence=confidence,
            provenance=provenance,
        )
        self._log(job_id, "info", f"Pipeline completed with status {status.value}.")

    def _log(self, job_id: str, level: str, message: str) -> None:
        try:
            self._job_manager.append_log(job_id, level, message)
        except AttributeError:
            return


def _to_validation_report(
    validation_result: ValidationResult,
    normalization_notes: Iterable[NormalizationNoteRecord],
) -> ValidationReport:
    notes = [
        ApiNormalizationNote(
            path=note.path,
            message=note.message,
            original_value=note.original_value,
            normalized_value=note.normalized_value,
        )
        for note in normalization_notes
    ]
    return ValidationReport(
        valid=validation_result.valid,
        schema_errors=validation_result.schema_errors,
        semantic_errors=validation_result.semantic_errors,
        warnings=validation_result.warnings,
        normalization_notes=notes,
    )


def _collect_unknowns(payload: Dict[str, Any]) -> List[UnknownField]:
    unknowns: List[UnknownField] = []
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    edges = payload.get("edges") if isinstance(payload, dict) else None

    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            unknowns.extend(_unknowns_from_container(node, f"nodes[{index}]"))
    if isinstance(edges, list):
        for index, edge in enumerate(edges):
            unknowns.extend(_unknowns_from_container(edge, f"edges[{index}]"))

    return unknowns


def _unknowns_from_container(container: Any, location: str) -> List[UnknownField]:
    if not isinstance(container, dict):
        return []
    raw_unknowns = container.get("unknowns")
    if not isinstance(raw_unknowns, list):
        return []
    result: List[UnknownField] = []
    for item in raw_unknowns:
        if isinstance(item, dict):
            field = item.get("field") if isinstance(item.get("field"), str) else "unknown"
            reason = item.get("reason") if isinstance(item.get("reason"), str) else "unknown"
            question_hint = (
                item.get("question_hint") if isinstance(item.get("question_hint"), str) else ""
            )
            result.append(
                UnknownField(
                    field=field,
                    reason=reason,
                    question_hint=question_hint,
                    location=location,
                )
            )
        elif isinstance(item, str) and item.strip():
            result.append(
                UnknownField(
                    field="unknown",
                    reason=item.strip(),
                    question_hint="",
                    location=location,
                )
            )
    return result


@dataclass(frozen=True)
class LowConfidenceSignal:
    location: str
    confidence: float


def _collect_low_confidence(payload: Dict[str, Any], threshold: float) -> List[LowConfidenceSignal]:
    signals: List[LowConfidenceSignal] = []
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    edges = payload.get("edges") if isinstance(payload, dict) else None

    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            confidence = _confidence_from_provenance(node)
            if confidence is not None and confidence < threshold:
                signals.append(
                    LowConfidenceSignal(
                        location=f"nodes[{index}].provenance.confidence",
                        confidence=confidence,
                    )
                )
    if isinstance(edges, list):
        for index, edge in enumerate(edges):
            confidence = _confidence_from_provenance(edge)
            if confidence is not None and confidence < threshold:
                signals.append(
                    LowConfidenceSignal(
                        location=f"edges[{index}].provenance.confidence",
                        confidence=confidence,
                    )
                )
    return signals


def _confidence_from_provenance(item: Any) -> Optional[float]:
    if not isinstance(item, dict):
        return None
    provenance = item.get("provenance")
    if not isinstance(provenance, dict):
        return None
    confidence = provenance.get("confidence")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        return float(confidence)
    return None


def _aggregate_confidence(payload: Dict[str, Any]) -> Optional[float]:
    confidences: List[float] = []
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    edges = payload.get("edges") if isinstance(payload, dict) else None
    if isinstance(nodes, list):
        for node in nodes:
            value = _confidence_from_provenance(node)
            if value is not None:
                confidences.append(value)
    if isinstance(edges, list):
        for edge in edges:
            value = _confidence_from_provenance(edge)
            if value is not None:
                confidences.append(value)
    if not confidences:
        return None
    return round(sum(confidences) / len(confidences), 4)


def _aggregate_provenance(payload: Dict[str, Any], confidence: Optional[float]) -> Optional[Dict[str, Any]]:
    sources = _collect_provenance_values(payload, "source")
    methods = _collect_provenance_values(payload, "method")
    source = _unique_value(sources)
    method = _unique_value(methods)
    if source is None and method is None and confidence is None:
        return None
    provenance: Dict[str, Any] = {}
    if source is not None:
        provenance["source"] = source
    if method is not None:
        provenance["method"] = method
    if confidence is not None:
        provenance["confidence"] = confidence
    return provenance or None


def _collect_provenance_values(payload: Dict[str, Any], key: str) -> List[str]:
    values: List[str] = []
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    edges = payload.get("edges") if isinstance(payload, dict) else None
    for items in (nodes, edges):
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                provenance = item.get("provenance")
                if not isinstance(provenance, dict):
                    continue
                value = provenance.get(key)
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
    return values


def _unique_value(values: Iterable[str]) -> Optional[str]:
    unique = {value for value in values if isinstance(value, str) and value.strip()}
    if len(unique) == 1:
        return unique.pop()
    return None


def _issues_from_validation(result: ValidationResult) -> List[ExtractionIssue]:
    issues: List[ExtractionIssue] = []
    for message in result.schema_errors:
        issues.append(_issue("NSM_SCHEMA_ERROR", message, severity="error"))
    for message in result.semantic_errors:
        issues.append(_issue("NSM_SEMANTIC_ERROR", message, severity="error"))
    for message in result.warnings:
        issues.append(_issue("NSM_WARNING", message, severity="warning"))
    return issues


def _issues_from_unknowns(unknowns: Iterable[UnknownField]) -> List[ExtractionIssue]:
    issues: List[ExtractionIssue] = []
    for unknown in unknowns:
        location = f"{unknown.location}: " if unknown.location else ""
        message = f"{location}{unknown.reason}"
        issues.append(
            _issue(
                "UNKNOWN_FIELD",
                message,
                field=unknown.field,
                severity="warning",
            )
        )
    return issues


def _issues_from_low_confidence(signals: Iterable[LowConfidenceSignal]) -> List[ExtractionIssue]:
    issues: List[ExtractionIssue] = []
    for signal in signals:
        message = f"Low provenance confidence ({signal.confidence:.4f}) at {signal.location}."
        issues.append(
            _issue(
                "LOW_CONFIDENCE",
                message,
                field=signal.location,
                severity="warning",
            )
        )
    return issues


def _issue(code: str, message: str, *, field: Optional[str] = None, severity: str = "info") -> ExtractionIssue:
    return ExtractionIssue(code=code, message=message, field=field, severity=severity)
