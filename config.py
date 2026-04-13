import os

# ── Constants ─────────────────────────────────────────────────────────────────

MA_PERIODS = [5, 20, 50, 100, 200]

MA_COLORS = {
    5:   "#F59E0B",   # amber
    20:  "#10B981",   # emerald
    50:  "#3B82F6",   # blue
    100: "#8B5CF6",   # violet
    200: "#EF4444",   # red
}

MA200W_COLOR = "#F0ABFC"   # fuchsia — weekly MA200

FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_COLORS = ["#94A3B8", "#F472B6", "#FB923C", "#FACC15", "#34D399", "#60A5FA", "#94A3B8"]

# (df_column, display_label, bullish=True/False/None, marker_symbol, color)
REVERSAL_PATTERNS = [
    ("pat_hammer",       "Hammer",            True,  "triangle-up",   "#4ADE80"),
    ("pat_bull_engulf",  "Bullish Engulfing", True,  "triangle-up",   "#16A34A"),
    ("pat_morning_star", "Morning Star",      True,  "star",          "#86EFAC"),
    ("pat_shoot_star",   "Shooting Star",     False, "triangle-down", "#F97316"),
    ("pat_bear_engulf",  "Bearish Engulfing", False, "triangle-down", "#EF4444"),
    ("pat_evening_star", "Evening Star",      False, "star",          "#DC2626"),
    ("pat_doji",         "Doji",              None,  "diamond",       "#FACC15"),
]

# ── Screener ticker pool ───────────────────────────────────────────────────────
# Full ranked universe — ordered by approximate S&P 500 market-cap weight.
# Set SCREENER_TICKER_COUNT in your environment to control how many are used
# (e.g. export SCREENER_TICKER_COUNT=30).  Defaults to 50.
_SPX_UNIVERSE = [
    # 1-10
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "LLY", "AVGO", "TSLA",
    # 11-20
    "JPM", "V", "UNH", "XOM", "MA", "HD", "PG", "JNJ", "ABBV", "WMT",
    # 21-30
    "COST", "MRK", "ORCL", "CRM", "BAC", "AMD", "KO", "CVX", "MCD", "NFLX",
    # 31-40
    "PFE", "ABT", "TXN", "CSCO", "PM", "LIN", "ACN", "NKE", "DIS", "AXP",
    # 41-50
    "HON", "INTC", "IBM", "AMGN", "GE", "LOW", "SBUX", "BA", "RTX", "CAT",
]

SCREENER_TICKER_COUNT: int = int(os.environ.get("SCREENER_TICKER_COUNT", 50))
SPX_TICKERS: list[str] = _SPX_UNIVERSE[:SCREENER_TICKER_COUNT]

PERIOD_OPTIONS = {
    "1 Week":   7,
    "2 Weeks":  14,
    "1 Month":  30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year":   365,
    "2 Years":  730,
    "5 Years":  1825,
}
