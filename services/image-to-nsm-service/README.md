# Image to NSM Service (Step 1 PoC)

Minimal API-first service for the Image to NSM Step 1 PoC. It exposes health, image-to-NSM submission, and job/result endpoints, plus the internal module structure for future implementation.

This service is the Step 1 proof-of-concept for the broader threat modeling engine. Its purpose is to accept architecture diagram images and convert them into a strict Normalized System Model (NSM) JSON document, which is the canonical internal representation of a system (nodes, edges, trust boundaries, assets, controls, provenance). That NSM output is the foundation that later stages will use for deterministic analysis and threat modeling.

The pipeline is designed to be API-first and microservice-friendly: an image upload (plus optional context) is sent to a pluggable LLM provider, then the response is parsed, normalized, and validated against the NSM schema. The service surfaces schema errors, semantic warnings, unknown fields, and confidence signals so uncertainty is preserved rather than hidden. It also persists job metadata and artifacts (raw LLM output, normalized NSM, validation reports) to support traceability and debugging.

The goal is repeatable, deterministic post-processing around a probabilistic LLM extraction step. By producing a consistent, validated NSM document and exposing status/result endpoints, this service establishes a clean contract for downstream threat inference, question generation, and prioritization layers without coupling the system to any UI or specific diagram source.

## Pipeline flow and outputs

The pipeline runs these stages in order:
1. Accept image upload and create a job record.
2. Build the prompt and send the image + prompt to the LLM provider.
3. Store the raw LLM response text.
4. Parse and normalize the payload into strict NSM JSON.
5. Validate against the NSM schema and run semantic/quality checks.
6. Persist the final NSM output if validation passes; otherwise mark the job failed and surface errors.

When persistence is enabled (default), artifacts are written under `services/image-to-nsm-service/data/<job_id>/`:
- `raw_llm_output.txt`: the raw text output returned by the LLM.
- `normalized_nsm.json`: the normalized NSM JSON after parsing and cleanup.
- `final_nsm.json`: the final NSM JSON that passed validation (only present on success).

Related artifacts you may also see:
- `validation_report.json`: schema/semantic errors and warnings.

Normalization is the deterministic cleanup and shaping step that turns messy LLM output into your canonical NSM format. It:
- Fills defaults (missing fields, IDs, schema_version).
- Maps aliases/synonyms and enum variants to allowed values.
- Converts simplified forms (like string assets/controls/unknowns) into structured objects.
- Moves/cleans unsupported fields.

Validation checks whether the normalized output conforms to the canonical schema and rules. It:
- Enforces required fields and types.
- Flags schema violations or semantic errors.
- Produces warnings for quality issues.

In the pipeline: LLM output → normalization → validation. Normalization makes the output shape-correct and consistent; validation decides whether it’s acceptable as a final NSM.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn image_to_nsm_service.app:app --host 0.0.0.0 --port 8080
```

## Persistence (PoC)

By default, the service persists jobs and artifacts to local disk using a SQLite metadata store and a local artifact directory.

Defaults:
- Data directory: `services/image-to-nsm-service/data`
- SQLite DB: `services/image-to-nsm-service/data/image_to_nsm.db`

Environment overrides:
- `IMAGE_TO_NSM_DATA_DIR` to change the artifact directory
- `IMAGE_TO_NSM_DB_PATH` to change the SQLite file location
- `JOB_STORAGE_MODE=memory` to disable persistence and use in-memory storage (tests only)
- `JOB_LOG_TO_CONSOLE=false` to disable console output for job processing logs (default: true)

## LLM provider configuration

This service supports a mock provider (default) and a real OpenAI multimodal provider for image-to-NSM extraction.

Environment variables:
- `LLM_PROVIDER` = `mock` (default) or `openai`
- `LLM_MODEL` = OpenAI model ID (default: `gpt-5.4`)
- `LLM_TIMEOUT_SECONDS` = request timeout in seconds (default: `120`)
- `OPENAI_API_KEY` = required when `LLM_PROVIDER=openai`
- `OPENAI_BASE_URL` = optional override for OpenAI API base URL
- `OPENAI_ORGANIZATION` = optional OpenAI org header
- `OPENAI_PROJECT` = optional OpenAI project header

Example (real provider):

```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-5.4
export OPENAI_API_KEY=...
uvicorn image_to_nsm_service.app:app --host 0.0.0.0 --port 8080
```

The schema is created automatically on startup.

Health check:

```bash
curl http://localhost:8080/health
```
