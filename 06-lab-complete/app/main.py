"""Production AI Agent — Part 6 Final Project."""
import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Format every application log record as a single valid JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra_data = getattr(record, "extra_data", None)
        if isinstance(extra_data, dict):
            payload.update(extra_data)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    app_logger = logging.getLogger("agent")
    app_logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    app_logger.propagate = False
    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        app_logger.addHandler(handler)
    return app_logger


logger = _configure_logging()
START_TIME = time.time()
_is_ready = False
_in_flight_requests = 0


def _log_event(level: int, event: str, **fields) -> None:
    logger.log(level, event, extra={"extra_data": {"event": event, **fields}})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    _is_ready = True
    _log_event(
        logging.INFO,
        "startup",
        environment=settings.environment,
        redis_configured=bool(settings.redis_url),
        rate_limit_per_minute=settings.rate_limit_per_minute,
    )
    try:
        yield
    finally:
        _is_ready = False
        _log_event(logging.INFO, "shutdown_start", in_flight=_in_flight_requests)
        deadline = time.time() + 10.0
        while _in_flight_requests > 0 and time.time() < deadline:
            await asyncio.sleep(0.05)
        _log_event(logging.INFO, "shutdown_complete", remaining_in_flight=_in_flight_requests)


app = FastAPI(
    title="Production AI Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
)


@app.middleware("http")
async def track_and_log_requests(request: Request, call_next):
    global _in_flight_requests
    _in_flight_requests += 1
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        _in_flight_requests -= 1
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        _log_event(
            logging.INFO,
            "request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            ms=elapsed_ms,
        )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_error",
        exc_info=exc,
        extra={"extra_data": {"event": "unhandled_error", "path": request.url.path}},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=128)


@app.get("/health")
def health():
    """Liveness probe — always returns 200 while process is alive, even if Redis is down."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    """Readiness probe — returns 200 when ready and Redis responds, 503 otherwise."""
    if not _is_ready or not redis_healthy():
        raise HTTPException(status_code=503, detail="Service not ready")
    return {
        "ready": True,
        "redis": "connected",
        "in_flight_requests": _in_flight_requests,
    }


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Protected agent endpoint enforcing API key auth, Redis rate limiting, and cost guard."""
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    cost_usd = record_cost(input_tokens, output_tokens)

    return {
        "question": body.question,
        "answer": answer,
        "user_id": body.user_id,
        "cost_usd": cost_usd,
    }
