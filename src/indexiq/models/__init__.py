"""
models package — pure business logic, no Streamlit dependencies.

Sub-modules:
  models.indicators   — technical analysis computations (MAs, RSI, Fibonacci, gaps, patterns)
  models.signals      — buy/sell signal scoring and classification
  models.ai_forecast  — AI forecast context building and API call
"""
from indexiq.models.indicators import (
    compute_daily_gaps,
    compute_fibonacci,
    compute_mas,
    compute_rsi,
    compute_weekly_ma200,
    detect_reversal_patterns,
    patch_today_gap,
)
from indexiq.models.signals import find_crosses, overall_signal, signal_score

__all__ = [
    "compute_daily_gaps",
    "compute_fibonacci",
    "compute_mas",
    "compute_rsi",
    "compute_weekly_ma200",
    "detect_reversal_patterns",
    "patch_today_gap",
    "find_crosses",
    "overall_signal",
    "signal_score",
]
