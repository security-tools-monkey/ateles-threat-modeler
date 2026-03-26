import logging

from fastapi import FastAPI

from .api.routes import router as api_router
from .api.errors import register_error_handlers
from .config import AppConfig, load_config
from .job_manager import InMemoryJobManager, PersistentJobManager
from .logging import configure_logging
from .llm_client import LlmProviderConfig, create_llm_client
from .pipeline import ImageToNsmPipeline
from .storage import LocalArtifactStorage, SqliteJobStore

logger = logging.getLogger("image_to_nsm_service")


def create_app() -> FastAPI:
    config = load_config()
    configure_logging(config.log_level)

    app = FastAPI(title="Image to NSM Service", version="0.1.0")
    app.state.config = config
    job_manager = _create_job_manager(config)
    app.state.job_manager = job_manager
    llm_client = create_llm_client(
        LlmProviderConfig(
            provider=config.llm_provider,
            model=config.llm_model,
            timeout_seconds=config.llm_timeout_seconds,
            openai_api_key=config.openai_api_key,
            openai_base_url=config.openai_base_url,
            openai_organization=config.openai_organization,
            openai_project=config.openai_project,
        )
    )
    app.state.pipeline = ImageToNsmPipeline(
        job_manager,
        llm_client=llm_client,
        log_job_messages_to_console=config.job_log_to_console,
    )
    register_error_handlers(app)
    app.include_router(api_router)

    @app.on_event("startup")
    def on_startup() -> None:
        logger.info(
            "startup service=%s host=%s port=%s",
            config.service_name,
            config.host,
            config.port,
        )

    return app


def _create_job_manager(config: AppConfig):
    if config.job_storage_mode == "memory":
        return InMemoryJobManager()
    artifacts = LocalArtifactStorage(config.data_dir)
    store = SqliteJobStore(config.db_path)
    return PersistentJobManager(store, artifacts)


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    uvicorn.run(
        "image_to_nsm_service.app:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )
