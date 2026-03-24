from fastapi import FastAPI
from fastapi.responses import JSONResponse

from image_to_nsm_service.models.api import InputErrorResponse
from image_to_nsm_service.validation.uploads import UploadValidationError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(UploadValidationError)
    async def handle_upload_validation_error(_, exc: UploadValidationError) -> JSONResponse:
        payload = InputErrorResponse(errors=exc.errors)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())
