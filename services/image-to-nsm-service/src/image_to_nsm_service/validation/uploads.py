from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import UploadFile, status

from ..models.api import ExtractionIssue

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"
_WEBP_RIFF = b"RIFF"
_WEBP_MARKER = b"WEBP"

_READ_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ValidatedImageUpload:
    filename: str
    content_type: str
    size_bytes: int
    data: bytes


class UploadValidationError(Exception):
    def __init__(self, *, status_code: int, errors: Iterable[ExtractionIssue]) -> None:
        self.status_code = status_code
        self.errors = list(errors)
        super().__init__("Upload validation failed")


async def validate_image_upload(
    image: Optional[UploadFile],
    *,
    max_size_bytes: int,
) -> ValidatedImageUpload:
    if image is None:
        raise UploadValidationError(
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=[_issue("INVALID_INPUT_FILE", "Image file is required.", field="image")],
        )

    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UploadValidationError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            errors=[
                _issue(
                    "UNSUPPORTED_MEDIA_TYPE",
                    "Unsupported content type for image upload.",
                    field="image",
                )
            ],
        )

    data = await _read_upload_data(image, max_size_bytes=max_size_bytes)
    if not data:
        raise UploadValidationError(
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=[_issue("INVALID_INPUT_FILE", "Uploaded image is empty.", field="image")],
        )

    if not _matches_signature(data, content_type):
        raise UploadValidationError(
            status_code=status.HTTP_400_BAD_REQUEST,
            errors=[
                _issue(
                    "INVALID_INPUT_FILE",
                    "Uploaded image content does not match the declared content type.",
                    field="image",
                )
            ],
        )

    filename = image.filename or "upload"
    return ValidatedImageUpload(
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        data=data,
    )


def _issue(code: str, message: str, *, field: Optional[str] = None) -> ExtractionIssue:
    return ExtractionIssue(code=code, message=message, field=field, severity="error")


async def _read_upload_data(image: UploadFile, *, max_size_bytes: int) -> bytes:
    total = 0
    buffer = bytearray()
    while True:
        chunk = await image.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            raise UploadValidationError(
                status_code=status.HTTP_400_BAD_REQUEST,
                errors=[
                    _issue(
                        "INVALID_INPUT_FILE",
                        "Uploaded image exceeds maximum allowed size.",
                        field="image",
                    )
                ],
            )
        buffer.extend(chunk)
    return bytes(buffer)


def _matches_signature(data: bytes, content_type: str) -> bool:
    if content_type == "image/png":
        return len(data) >= len(_PNG_SIGNATURE) and data.startswith(_PNG_SIGNATURE)
    if content_type in {"image/jpeg", "image/jpg"}:
        return len(data) >= 4 and data.startswith(_JPEG_SOI) and data.endswith(_JPEG_EOI)
    if content_type == "image/webp":
        return (
            len(data) >= 12
            and data.startswith(_WEBP_RIFF)
            and data[8:12] == _WEBP_MARKER
        )
    return False
