import os
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.app import create_app


PNG_BYTES = b"\x89PNG\r\n\x1a\n"
JPEG_BYTES = b"\xff\xd8\x00\x00\xff\xd9"
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP"


def create_client(max_upload_size_bytes: int = 10 * 1024 * 1024) -> TestClient:
    os.environ["MAX_UPLOAD_SIZE_BYTES"] = str(max_upload_size_bytes)
    app = create_app()
    return TestClient(app)


def assert_error(response, status_code: int, code: str) -> None:
    if response.status_code != status_code:
        raise AssertionError(f"Expected {status_code}, got {response.status_code}")
    payload = response.json()
    if payload["errors"][0]["code"] != code:
        raise AssertionError(f"Expected error code {code}, got {payload['errors'][0]['code']}")


class TestUploadValidation(unittest.TestCase):
    def test_accepts_png_upload(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.png", PNG_BYTES, "image/png")},
        )
        self.assertEqual(response.status_code, 202)

    def test_accepts_jpeg_upload(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.jpg", JPEG_BYTES, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 202)

    def test_accepts_webp_upload(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.webp", WEBP_BYTES, "image/webp")},
        )
        self.assertEqual(response.status_code, 202)

    def test_rejects_unsupported_media_type(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.gif", b"GIF89a", "image/gif")},
        )
        assert_error(response, 415, "UNSUPPORTED_MEDIA_TYPE")

    def test_rejects_missing_file(self):
        client = create_client()
        response = client.post("/image-to-nsm")
        assert_error(response, 400, "INVALID_INPUT_FILE")

    def test_rejects_empty_file(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.png", b"", "image/png")},
        )
        assert_error(response, 400, "INVALID_INPUT_FILE")

    def test_rejects_corrupted_file(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.png", b"not-a-png", "image/png")},
        )
        assert_error(response, 400, "INVALID_INPUT_FILE")

    def test_rejects_over_max_size(self):
        client = create_client(max_upload_size_bytes=5)
        response = client.post(
            "/image-to-nsm",
            files={"image": ("diagram.jpg", JPEG_BYTES, "image/jpeg")},
        )
        assert_error(response, 400, "INVALID_INPUT_FILE")

    def test_accepts_optional_context(self):
        client = create_client()
        response = client.post(
            "/image-to-nsm",
            data={"context": "sample context"},
            files={"image": ("diagram.png", PNG_BYTES, "image/png")},
        )
        self.assertEqual(response.status_code, 202)
