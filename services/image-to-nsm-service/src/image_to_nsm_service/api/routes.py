from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from ..job_manager import InMemoryJobManager
from ..models.api import (
    ErrorsResponse,
    ImageToNsmJobAcceptedResponse,
    InputErrorResponse,
    JobState,
    JobStatusResponse,
    NsmResultResponse,
    RawOutputResponse,
)
from ..pipeline import ImageToNsmPipeline, ImageToNsmSubmission
from ..validation.uploads import validate_image_upload

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    config = request.app.state.config
    return {"status": "ok", "service": config.service_name}


def _get_job_manager(request: Request) -> InMemoryJobManager:
    return request.app.state.job_manager


def _get_pipeline(request: Request) -> ImageToNsmPipeline:
    return request.app.state.pipeline


def _to_job_state(job) -> JobState:
    return JobState(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    "/image-to-nsm",
    response_model=ImageToNsmJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": InputErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": InputErrorResponse},
    },
)
async def submit_image_to_nsm(
    request: Request,
    image: UploadFile | None = File(None),
    context: str | None = Form(None),
) -> ImageToNsmJobAcceptedResponse:
    config = request.app.state.config
    validated = await validate_image_upload(image, max_size_bytes=config.max_upload_size_bytes)
    pipeline = _get_pipeline(request)
    submission = ImageToNsmSubmission(
        filename=validated.filename,
        content_type=validated.content_type,
        size_bytes=validated.size_bytes,
        context=context,
    )
    job = pipeline.submit(submission)
    return ImageToNsmJobAcceptedResponse(job_id=job.job_id, status=job.status)


@router.get(
    "/image-to-nsm/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_image_to_nsm_status(
    request: Request,
    job_id: str,
) -> JobStatusResponse:
    job_manager = _get_job_manager(request)
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(job=_to_job_state(job))


@router.get(
    "/image-to-nsm/{job_id}/nsm",
    response_model=NsmResultResponse,
    status_code=status.HTTP_200_OK,
)
async def get_image_to_nsm_result(
    request: Request,
    job_id: str,
) -> NsmResultResponse:
    job_manager = _get_job_manager(request)
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return NsmResultResponse(
        job=_to_job_state(job),
        nsm=job.nsm,
        unknowns=job.unknowns,
        confidence=job.confidence,
        provenance=job.provenance,
    )


@router.get(
    "/image-to-nsm/{job_id}/raw",
    response_model=RawOutputResponse,
    status_code=status.HTTP_200_OK,
)
async def get_image_to_nsm_raw(
    request: Request,
    job_id: str,
) -> RawOutputResponse:
    job_manager = _get_job_manager(request)
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return RawOutputResponse(job=_to_job_state(job), raw_output=job.raw_output)


@router.get(
    "/image-to-nsm/{job_id}/errors",
    response_model=ErrorsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_image_to_nsm_errors(
    request: Request,
    job_id: str,
) -> ErrorsResponse:
    job_manager = _get_job_manager(request)
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return ErrorsResponse(job=_to_job_state(job), errors=job.errors)
