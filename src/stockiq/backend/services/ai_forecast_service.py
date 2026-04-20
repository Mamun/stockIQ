"""AI forecast service — assembles context and delegates to the LLM layer."""

import pandas as pd

from stockiq.backend.llm import PROVIDERS, fetch_ai_prediction, get_secret
from stockiq.backend.models.spy_context import (
    build_forecast_context,
    is_market_open,
    next_market_open_str,
)
from stockiq.backend.services.market_service import get_put_call_ratio, get_vix_chart_df
from stockiq.backend.services.spy_service import get_spy_chart_df, get_spy_quote


def get_providers() -> dict[str, dict]:
    """Return provider metadata (label, model, env_var, free flag)."""
    return PROVIDERS


def has_app_key(provider: str) -> bool:
    """Return True if the app-level API key for this provider is configured."""
    env_var = PROVIDERS[provider]["env_var"]
    return bool(get_secret(env_var))


def get_app_key(provider: str) -> str:
    """Return the app-level API key for the given provider (empty string if absent)."""
    return get_secret(PROVIDERS[provider]["env_var"])


def get_market_status() -> dict:
    """Return market open/closed status and next-open string."""
    open_ = is_market_open()
    return {
        "is_open":        open_,
        "next_open_str":  next_market_open_str() if not open_ else "",
    }


def get_ai_forecast(
    gaps_df: pd.DataFrame,
    provider: str = "groq",
    user_key: str = "",
    cache_key: str = "",
) -> list[dict]:
    """
    Assemble all context data and return a 10-day SPY forecast from the AI model.

    Returns a list of 10 prediction dicts (date, direction, est_close, …).
    Raises on provider errors so the caller can handle UX.
    """
    quote    = get_spy_quote()
    daily_df = get_spy_chart_df("1y", "1d")
    vix_df   = get_vix_chart_df("1y")
    pc_data  = get_put_call_ratio()

    context_json = build_forecast_context(
        gaps_df, quote,
        daily_df=daily_df,
        vix_df=vix_df,
        pc_data=pc_data,
    )

    return fetch_ai_prediction(
        cache_key,
        context_json,
        provider=provider,
        _user_key=user_key,
    )
