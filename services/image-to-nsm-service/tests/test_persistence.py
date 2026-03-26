from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.job_manager import PersistentJobManager
from image_to_nsm_service.models.api import JobStatus
from image_to_nsm_service.storage import LocalArtifactStorage, SqliteJobStore


def test_persistent_job_manager_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = LocalArtifactStorage(root / "artifacts")
        store = SqliteJobStore(root / "jobs.db")
        manager = PersistentJobManager(store, artifacts)

        job = manager.create_job(input_filename="diagram.png")
        manager.update_job(
            job.job_id,
            input_content_type="image/png",
            input_size_bytes=4,
            input_context="sample context",
            input_image_bytes=b"fake",
        )
        manager.update_job(
            job.job_id,
            raw_output="{\"schema_version\":\"0.1\"}",
            normalized_output={"schema_version": "0.1", "nodes": [], "edges": []},
            validation_report={"valid": True},
            nsm={"schema_version": "0.1", "nodes": [], "edges": []},
        )
        manager.set_status(job.job_id, JobStatus.succeeded)
        manager.append_log(job.job_id, "info", "Completed.")

        manager2 = PersistentJobManager(SqliteJobStore(root / "jobs.db"), LocalArtifactStorage(root / "artifacts"))
        loaded = manager2.get_job(job.job_id)
        assert loaded is not None
        assert loaded.status == JobStatus.succeeded
        assert loaded.raw_output == "{\"schema_version\":\"0.1\"}"
        assert loaded.nsm["schema_version"] == "0.1"
        assert loaded.validation_report["valid"] is True
        assert loaded.input_filename == "diagram.png"
        assert loaded.input_context == "sample context"
        assert loaded.input_image_path
