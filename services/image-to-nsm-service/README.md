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

The schema is created automatically on startup.

Health check:

```bash
curl http://localhost:8080/health
```
