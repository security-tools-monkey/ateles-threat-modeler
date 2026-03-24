from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    service_name: str
    host: str
    port: int
    log_level: str


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
    )
