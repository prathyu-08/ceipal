"""Structured request logging middleware."""

from __future__ import annotations

import json
import logging
import time
import traceback
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(payload, default=str)


def configure_json_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if str(key).lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _latency_bucket(duration_ms: float) -> str:
    if duration_ms > 5000:
        return "gt_5s"
    if duration_ms > 1000:
        return "gt_1s"
    if duration_ms > 500:
        return "gt_500ms"
    return "ok"


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        logger = logging.getLogger("app.request")

        request_payload: Any = None
        if request.method in {"POST", "PUT", "PATCH"}:
            MAX_LOG_BODY_BYTES = 16_384
            body = await request.body()
            if body and len(body) <= MAX_LOG_BODY_BYTES:
                try:
                    request_payload = _redact(json.loads(body))
                except json.JSONDecodeError:
                    request_payload = "<non-json body>"
            elif body and len(body) > MAX_LOG_BODY_BYTES:
                request_payload = "<body too large to log>"


        response = None
        try:
            response = await call_next(request)
            return response
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.url.query),
                    "request_payload": request_payload,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            status_code = response.status_code if response else 500
            if response:
                response.headers["x-request-id"] = request_id

            logger.info(
                "request_complete",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.url.query),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "latency_bucket": _latency_bucket(duration_ms),
                    "slow_request": duration_ms > 500,
                    "database_query_ms": getattr(request.state, "database_query_ms", None),
                    "user_id": getattr(request.state, "user_id", None),
                    "request_payload": request_payload,
                },
            )
