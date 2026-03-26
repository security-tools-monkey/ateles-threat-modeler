from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    service_name: str
    host: str
    port: int
    log_level: str
    max_upload_size_bytes: int
    data_dir: str
    db_path: str
    job_storage_mode: str


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config() -> AppConfig:
    base_dir = Path(__file__).resolve().parents[2]
    default_data_dir = str(base_dir / "data")
    data_dir = os.getenv("IMAGE_TO_NSM_DATA_DIR", default_data_dir)
    db_path = os.getenv("IMAGE_TO_NSM_DB_PATH", str(Path(data_dir) / "image_to_nsm.db"))
    job_storage_mode = os.getenv("JOB_STORAGE_MODE", "local").lower()
    return AppConfig(
        service_name=os.getenv("SERVICE_NAME", "image-to-nsm-service"),
        host=os.getenv("SERVICE_HOST", "0.0.0.0"),
        port=_get_env_int("SERVICE_PORT", 8080),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_upload_size_bytes=_get_env_int("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024),
        data_dir=data_dir,
        db_path=db_path,
        job_storage_mode=job_storage_mode,
    )
