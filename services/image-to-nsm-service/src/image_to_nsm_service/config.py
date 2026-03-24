from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    service_name: str
    host: str
    port: int
    log_level: str
    max_upload_size_bytes: int


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config() -> AppConfig:
    return AppConfig(
        service_name=os.getenv("SERVICE_NAME", "image-to-nsm-service"),
        host=os.getenv("SERVICE_HOST", "0.0.0.0"),
        port=_get_env_int("SERVICE_PORT", 8080),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_upload_size_bytes=_get_env_int("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024),
    )
