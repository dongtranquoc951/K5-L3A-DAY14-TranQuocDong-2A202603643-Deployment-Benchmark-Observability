"""Application configuration loaded from environment variables (12-Factor)."""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:
    pass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    """Runtime settings read from environment variables."""

    port: int = field(default_factory=lambda: _env_int("PORT", 8000))
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development").strip() or "development"
    )
    agent_api_key: str = field(
        default_factory=lambda: os.getenv("AGENT_API_KEY", "").strip()
    )
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "").strip()
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_PER_MINUTE", 10)
    )
    daily_budget_usd: float = field(
        default_factory=lambda: _env_float("DAILY_BUDGET_USD", 1.0)
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: _env_float("MONTHLY_BUDGET_USD", 10.0)
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    )


settings = Settings()
