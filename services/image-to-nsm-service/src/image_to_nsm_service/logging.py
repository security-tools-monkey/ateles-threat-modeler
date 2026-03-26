import logging
from typing import Any


class _OpenAiImageRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = _redact_payload(record.args)
        if isinstance(record.msg, str) and "data:image" in record.msg:
            record.msg = _redact_image_url_text(record.msg)
        return True


def _redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key == "image_url" and isinstance(item, str) and item.startswith("data:"):
                redacted[key] = "<IMAGE_REDACTED>"
            else:
                redacted[key] = _redact_payload(item)
        return redacted
    if isinstance(value, (list, tuple)):
        redacted_items = [_redact_payload(item) for item in value]
        return type(value)(redacted_items)
    return value


def _redact_image_url_text(message: str) -> str:
    marker = "data:image"
    start = message.find(marker)
    if start == -1:
        return message
    end = message.find("'", start)
    if end == -1:
        end = message.find('"', start)
    if end == -1:
        end = len(message)
    return f"{message[:start]}<IMAGE_REDACTED>{message[end:]}"


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    openai_logger = logging.getLogger("openai")
    openai_base_logger = logging.getLogger("openai._base_client")
    for logger in (openai_logger, openai_base_logger):
        logger.addFilter(_OpenAiImageRedactionFilter())
        logger.setLevel(log_level)
