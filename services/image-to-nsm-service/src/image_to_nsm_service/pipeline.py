import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .job_manager import JobManager
from .llm_client import ImagePayload, LlmClient, LlmClientError, LlmRequest, MockLlmClient
from .models.api import (
    ExtractionIssue,
    JobStatus,
    NormalizationNote as ApiNormalizationNote,
    UnknownField,
    ValidationReport,
)
from .normalizer import (
    NORMALIZATION_VERSION,
    NormalizationNote as NormalizationNoteRecord,
    NormalizationResult,
    normalize_nsm_payload,
)
from .prompt_builder import PromptBuilder, PromptRequest, VersionedPromptBuilder
from .extractor.raw_response_parser import RawResponseParser
from .validator import ValidationResult, validate_nsm_payload
from .validator.schema_loader import load_schema_version
from .validator.quality_warnings import PROVENANCE_CONFIDENCE_THRESHOLD


@dataclass(frozen=True)
class ImageToNsmSubmission:
    filename: str
    content_type: str
    size_bytes: int
    data: bytes
    context: Optional[str]
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass(frozen=True)
class PipelineContext:
    job_id: str
    request_id: str
    correlation_id: Optional[str] = None


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
        log_job_messages_to_console: bool = True,
    ) -> None:
        self._job_manager = job_manager
        self._prompt_builder = prompt_builder or VersionedPromptBuilder()
        self._llm_client = llm_client or MockLlmClient()
        self._raw_parser = raw_parser or RawResponseParser(strip_code_fences=False)
        self._normalizer = normalizer
        self._validator = validator
        self._log_job_messages_to_console = log_job_messages_to_console
        self._logger = logging.getLogger("image_to_nsm_service.pipeline")

    def submit(self, submission: ImageToNsmSubmission):
        job = self._job_manager.create_job(input_filename=submission.filename)
        request_id = submission.request_id or job.job_id
        correlation_id = submission.correlation_id
        self._job_manager.update_job(
            job.job_id,
            input_content_type=submission.content_type,
            input_size_bytes=submission.size_bytes,
            input_context=submission.context,
            input_image_bytes=submission.data,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        self._job_manager.set_status(job.job_id, JobStatus.pending)
        context = PipelineContext(
            job_id=job.job_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        self._log(context, "info", "Job accepted for processing.", stage="accept")
        try:
            self._run_pipeline(context, submission)
        except Exception as exc:
            self._job_manager.update_job(
                job.job_id,
                status=JobStatus.failed,
                processing_completed_at=datetime.now(timezone.utc),
                errors=[_issue("PIPELINE_ERROR", f"Pipeline failure: {exc}", severity="error")],
            )
            self._log(context, "error", f"Pipeline failure: {exc}", stage="pipeline")
        return self._job_manager.get_job(job.job_id) or job

    def _run_pipeline(self, context: PipelineContext, submission: ImageToNsmSubmission) -> None:
        job_id = context.job_id
        self._job_manager.set_status(job_id, JobStatus.running)
        self._job_manager.update_job(job_id, processing_started_at=datetime.now(timezone.utc))
        self._log(context, "info", "Pipeline started.", stage="pipeline")

        prompt_spec = self._prompt_builder.build(PromptRequest(context=submission.context))
        schema_version = load_schema_version()
        self._job_manager.update_job(
            job_id,
            prompt_version=prompt_spec.version,
            schema_version=schema_version,
        )
        self._log(
            context,
            "info",
            f"Prompt built (version {prompt_spec.version}, schema {schema_version}).",
            stage="prompt_build",
        )
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
        self._logger.debug(
            "LLM request prepared prompt_version=%s prompt_chars=%s context_chars=%s "
            "image_filename=%s image_content_type=%s image_bytes=%s",
            prompt_spec.version,
            len(prompt_spec.text),
            len(submission.context) if submission.context else 0,
            submission.filename,
            submission.content_type,
            len(submission.data) if submission.data else 0,
        )
        self._logger.debug("LLM prompt text: %s", prompt_spec.text)
        try:
            self._logger.debug("LLM request dispatching.")
            self._log(context, "info", "LLM request started.", stage="llm_request")
            llm_response = self._llm_client.generate(llm_request)
        except LlmClientError as exc:
            self._job_manager.update_job(
                job_id,
                status=JobStatus.failed,
                llm_provider=exc.metadata.get("provider"),
                llm_model=exc.metadata.get("model"),
                llm_request_id=exc.metadata.get("request_id"),
                llm_response_id=exc.metadata.get("response_id"),
                processing_completed_at=datetime.now(timezone.utc),
                errors=[_issue(exc.code, str(exc), severity="error")],
            )
            self._log(context, "error", f"LLM request failed: {exc}", stage="llm_request")
            return
        except Exception as exc:
            self._job_manager.update_job(
                job_id,
                status=JobStatus.failed,
                processing_completed_at=datetime.now(timezone.utc),
                errors=[_issue("LLM_REQUEST_FAILED", f"LLM request failed: {exc}", severity="error")],
            )
            self._log(context, "error", f"LLM request failed: {exc}", stage="llm_request")
            return

        self._job_manager.update_job(
            job_id,
            llm_provider=llm_response.metadata.get("provider"),
            llm_model=llm_response.model,
            llm_request_id=llm_response.metadata.get("request_id"),
            llm_response_id=llm_response.metadata.get("response_id"),
        )
        if llm_response.metadata:
            self._logger.debug("LLM response metadata: %s", llm_response.metadata)
        usage = llm_response.metadata.get("usage")
        if usage is not None:
            self._logger.debug("LLM token usage: %s", usage)
        self._log(
            context,
            "info",
            f"LLM response received (model {llm_response.model}).",
            stage="llm_request",
        )
        raw_output = llm_response.raw_output
        self._logger.debug("LLM raw output: %s", raw_output)
        self._job_manager.update_job(job_id, raw_output=raw_output)
        self._log(context, "info", "Raw LLM output stored.", stage="raw_output_store")

        parse_result = self._raw_parser.parse(raw_output)
        issues: List[ExtractionIssue] = list(parse_result.errors)
        if parse_result.payload is None:
            report = ValidationReport(valid=False)
            self._job_manager.update_job(
                job_id,
                status=JobStatus.failed,
                processing_completed_at=datetime.now(timezone.utc),
                validation_report=report.model_dump(),
                errors=issues,
            )
            self._log(context, "warning", "LLM output parsing failed.", stage="parse")
            return

        normalization_result: NormalizationResult = self._normalizer(parse_result.payload)
        normalized_payload = normalization_result.payload
        self._job_manager.update_job(job_id, normalization_version=NORMALIZATION_VERSION)
        self._log(
            context,
            "info",
            f"Normalization completed (version {NORMALIZATION_VERSION}).",
            stage="normalize",
        )

        validation_result: ValidationResult = self._validator(normalized_payload)
        validation_report = _to_validation_report(validation_result, normalization_result.notes)
        self._log(
            context,
            "info",
            f"Validation completed (warnings={len(validation_result.warnings)}).",
            stage="validate",
        )

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
            processing_completed_at=datetime.now(timezone.utc),
            normalized_output=normalized_payload,
            nsm=final_nsm,
            validation_report=validation_report.model_dump(),
            errors=issues,
            unknowns=[unknown.model_dump() for unknown in unknowns],
            confidence=confidence,
            provenance=provenance,
        )
        self._log(
            context,
            "info",
            f"Pipeline completed with status {status.value}.",
            stage="pipeline",
        )

    def _log(
        self,
        context: PipelineContext,
        level: str,
        message: str,
        *,
        stage: Optional[str] = None,
    ) -> None:
        parts = [f"job_id={context.job_id}", f"request_id={context.request_id}"]
        if context.correlation_id:
            parts.append(f"correlation_id={context.correlation_id}")
        if stage:
            parts.append(f"stage={stage}")
        formatted = f"{' '.join(parts)} {message}"
        try:
            self._job_manager.append_log(context.job_id, level, formatted)
        except AttributeError:
            return
        if self._log_job_messages_to_console:
            log_level = getattr(logging, level.upper(), logging.INFO)
            self._logger.log(log_level, formatted)


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
