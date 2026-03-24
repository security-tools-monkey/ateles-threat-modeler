# Image to NSM Service (Step 1 PoC)

Minimal API-first service for the Image to NSM Step 1 PoC. This service currently exposes only a health endpoint and provides the internal module structure for future implementation.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn image_to_nsm_service.app:app --host 0.0.0.0 --port 8080
```

Health check:

```bash
curl http://localhost:8080/health
```
