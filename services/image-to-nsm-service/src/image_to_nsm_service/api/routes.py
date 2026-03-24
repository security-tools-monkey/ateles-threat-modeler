from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from image_to_nsm_service.job_manager import InMemoryJobManager
from image_to_nsm_service.models.api import (
    ErrorsResponse,
    ImageToNsmJobAcceptedResponse,
    JobState,
    JobStatusResponse,
    NsmResultResponse,
    RawOutputResponse,
)

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    config = request.app.state.config
    return {"status": "ok", "service": config.service_name}


def _get_job_manager(request: Request) -> InMemoryJobManager:
    return request.app.state.job_manager


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
)
async def submit_image_to_nsm(
    request: Request,
    image: UploadFile = File(...),
) -> ImageToNsmJobAcceptedResponse:
    job_manager = _get_job_manager(request)
    job = job_manager.create_job(input_filename=image.filename)
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
