from __future__ import annotations

import logging
import re


_RUNTIME_LOGGER_ROOT = "uvicorn.error.math_im_book"


def get_runtime_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{_RUNTIME_LOGGER_ROOT}.{component}")


def safe_log_value(value: object, *, max_length: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return "-"
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."
