from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    config = request.app.state.config
    return {"status": "ok", "service": config.service_name}
