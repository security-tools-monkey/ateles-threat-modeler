from dataclasses import dataclass
from typing import Optional

from .job_manager import InMemoryJobManager


@dataclass(frozen=True)
class ImageToNsmSubmission:
    filename: str
    content_type: str
    size_bytes: int
    context: Optional[str]


class ImageToNsmPipeline:
    def __init__(self, job_manager: InMemoryJobManager) -> None:
        self._job_manager = job_manager

    def submit(self, submission: ImageToNsmSubmission):
        return self._job_manager.create_job(input_filename=submission.filename)
