# Image to NSM Service (Step 1 PoC)

Minimal API-first service for the Image to NSM Step 1 PoC. This service currently exposes only a health endpoint and provides the internal module structure for future implementation.

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
