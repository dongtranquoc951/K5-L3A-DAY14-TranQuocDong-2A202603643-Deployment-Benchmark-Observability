"""Redis-backed LLM cost guard enforcing daily and monthly USD budgets."""
import logging
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

logger = logging.getLogger("agent.cost_guard")

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_fallback_daily_cost: dict[str, float] = {}
_fallback_monthly_cost: dict[str, float] = {}


def _period_keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")


def _read_spend(day_key: str, month_key: str) -> tuple[float, float]:
    if r is not None:
        try:
            vals = r.mget([f"cost:daily:{day_key}", f"cost:monthly:{month_key}"])
            return float(vals[0] or 0.0), float(vals[1] or 0.0)
        except (redis.RedisError, OSError, ValueError) as exc:
            logger.warning(f"cost_guard_read_error: {exc}")
    return _fallback_daily_cost.get(day_key, 0.0), _fallback_monthly_cost.get(month_key, 0.0)


def check_budget() -> None:
    """Raise HTTP 402 if cumulative daily or monthly spend reached configured budget."""
    day_key, month_key = _period_keys()
    daily_spent, monthly_spent = _read_spend(day_key, month_key)

    if daily_spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": round(daily_spent, 6),
                "budget_usd": settings.daily_budget_usd,
            },
        )
    if monthly_spent >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(monthly_spent, 6),
                "budget_usd": settings.monthly_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Compute request cost from token counts, persist in Redis, and return cost."""
    cost = round(
        (input_tokens / 1000.0) * PRICE_INPUT_PER_1K
        + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K,
        8,
    )
    day_key, month_key = _period_keys()

    if r is not None:
        try:
            pipe = r.pipeline()
            daily_redis_key = f"cost:daily:{day_key}"
            monthly_redis_key = f"cost:monthly:{month_key}"
            pipe.incrbyfloat(daily_redis_key, cost)
            pipe.expire(daily_redis_key, 2 * 86400)
            pipe.incrbyfloat(monthly_redis_key, cost)
            pipe.expire(monthly_redis_key, 35 * 86400)
            pipe.execute()
            return cost
        except (redis.RedisError, OSError) as exc:
            logger.warning(f"cost_guard_write_error: {exc}")

    _fallback_daily_cost[day_key] = _fallback_daily_cost.get(day_key, 0.0) + cost
    _fallback_monthly_cost[month_key] = _fallback_monthly_cost.get(month_key, 0.0) + cost
    return cost
