import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Market Analyzer - Technical Analysis & Trading Signals",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Stock Market Analyzer: Real-time technical analysis with moving averages, Fibonacci retracement, and reversal pattern detection for informed trading decisions."
    }
)

# ── SEO: Open Graph & Schema Markup ───────────────────────────────────────────
st.markdown("""
    <meta property="og:title" content="Stock Market Analyzer - Technical Analysis Tool" />
    <meta property="og:description" content="Free stock technical analysis with moving averages, Fibonacci levels, reversal patterns, and AI-powered buy/sell signals." />
    <meta property="og:type" content="website" />
    <meta name="description" content="Real-time stock market analyzer with technical indicators: MA5/20/50/100/200, Fibonacci retracement, and reversal pattern detection." />
    <meta name="keywords" content="stock analysis, technical analysis, moving averages, Fibonacci retracement, trading signals, stock market" />
    
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "WebApplication",
        "name": "Stock Market Analyzer",
        "description": "Technical analysis tool providing real-time stock market insights with moving averages, Fibonacci levels, and reversal pattern detection",
        "applicationCategory": "FinanceApplication",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD"
        }
    }
    </script>
""", unsafe_allow_html=True)

st.title("📈 Stock Market Analyzer")
st.markdown("Moving Averages · Fibonacci Levels · Buy / Sell Signals · Reversal Patterns")

# ── Session state ─────────────────────────────────────────────────────────────
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "ticker_val" not in st.session_state:
    st.session_state.ticker_val = "MSFT"


def search_companies(query: str) -> list[dict]:
    """Return matching companies from Yahoo Finance search."""
    try:
        quotes = yf.Search(query, max_results=10, news_count=0).quotes
        return [
            {
                "symbol":   r.get("symbol", ""),
                "name":     r.get("shortname") or r.get("longname") or r.get("symbol", ""),
                "exchange": r.get("exchange", ""),
                "type":     r.get("quoteType", ""),
            }
            for r in quotes
            if r.get("symbol") and r.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND", "INDEX")
        ]
    except Exception:
        return []


# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    # ── Company search ────────────────────────────────────────────────────
    st.markdown("**Search by company name**")
    col_q, col_btn = st.columns([3, 1])
    search_query = col_q.text_input(
        "company_search", placeholder="e.g. Microsoft",
        label_visibility="collapsed",
    )
    if col_btn.button("Go", use_container_width=True):
        if search_query.strip():
            with st.spinner("Searching…"):
                st.session_state.search_results = search_companies(search_query.strip())
        else:
            st.session_state.search_results = []

    if st.session_state.search_results:
        labels = [
            f"{r['symbol']}  —  {r['name']}  ({r['exchange']})"
            for r in st.session_state.search_results
        ]
        choice_idx = st.selectbox(
            "Select a company", range(len(labels)),
            format_func=lambda i: labels[i],
        )
        st.session_state.ticker_val = st.session_state.search_results[choice_idx]["symbol"]
    elif search_query and not st.session_state.search_results:
        st.caption("No matches found — try a different name.")

    st.markdown("---")

    # ── Direct ticker entry (pre-filled from search selection) ───────────
    ticker = st.text_input(
        "Ticker Symbol", value=st.session_state.ticker_val, max_chars=10,
    ).upper().strip()

    period_options = {
        "1 Week":   7,
        "2 Weeks":  14,
        "1 Month":  30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year":   365,
        "2 Years":  730,
        "5 Years":  1825,
    }
    period_label = st.selectbox("Historical Period", list(period_options.keys()), index=2)
    period_days = period_options[period_label]
    show_volume = st.checkbox("Show Volume", value=True)
    show_fibonacci = st.checkbox("Show Fibonacci Levels", value=True)
    show_patterns = st.checkbox("Show Reversal Patterns", value=True)
    analyze_btn = st.button("Analyze", use_container_width=True, type="primary")
# ── Feature Overview (SEO Content) ────────────────────────────────────────────
with st.expander("📊 About This Stock Analyzer", expanded=False):
    st.markdown("""
    **Stock Market Analyzer** is a free technical analysis tool designed to help traders and investors make informed decisions with real-time data.
    
    **Key Features:**
    - **Moving Averages**: Track price trends with 5, 20, 50, 100, and 200-day moving averages
    - **Fibonacci Retracement**: Identify potential support and resistance levels based on the Fibonacci sequence
    - **Reversal Pattern Detection**: Automatic detection of 7 candlestick reversal patterns including Hammer, Morning Star, Engulfing, and Doji
    - **Golden/Death Cross Signals**: Major trend reversal indicators based on MA50 and MA200 crossovers
    - **Buy/Sell Signal Score**: AI-powered scoring system combining multiple technical indicators
    - **Weekly Trend Analysis**: 200-week moving average for long-term secular trend confirmation
    
    **How It Works:**
    1. Search for a company by name or enter a stock ticker symbol
    2. Select your preferred historical period
    3. Choose which indicators to display
    4. Click **Analyze** to generate real-time technical analysis
    
    All data is sourced from Yahoo Finance and updated in real-time.
    """)
# ── Signal engine ─────────────────────────────────────────────────────────────

# ── Reversal pattern registry ─────────────────────────────────────────────────
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


def detect_reversal_patterns(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    max_oc = pd.concat([o, c], axis=1).max(axis=1)
    min_oc = pd.concat([o, c], axis=1).min(axis=1)
    body        = max_oc - min_oc
    upper_wick  = h - max_oc
    lower_wick  = min_oc - l
    full_range  = h - l
    bullish_c   = c > o
    bearish_c   = c < o

    # ── Hammer ────────────────────────────────────────────────────────────
    # Small body near top, lower wick ≥ 2× body, tiny upper wick
    df["pat_hammer"] = (
        (body > 0) &
        (lower_wick >= 2 * body) &
        (upper_wick <= 0.25 * body)
    )

    # ── Shooting Star ─────────────────────────────────────────────────────
    # Small body near bottom, upper wick ≥ 2× body, tiny lower wick
    df["pat_shoot_star"] = (
        (body > 0) &
        (upper_wick >= 2 * body) &
        (lower_wick <= 0.25 * body)
    )

    # ── Bullish Engulfing ─────────────────────────────────────────────────
    prev_max = max_oc.shift(1)
    prev_min = min_oc.shift(1)
    df["pat_bull_engulf"] = (
        bullish_c &
        bearish_c.shift(1) &
        (o < prev_min) &
        (c > prev_max)
    )

    # ── Bearish Engulfing ─────────────────────────────────────────────────
    df["pat_bear_engulf"] = (
        bearish_c &
        bullish_c.shift(1) &
        (o > prev_max) &
        (c < prev_min)
    )

    # ── Morning Star (3-candle bullish) ───────────────────────────────────
    # Day-1: large bearish; Day-2: small body (indecision); Day-3: bullish > Day-1 midpoint
    d1_mid = (o.shift(2) + c.shift(2)) / 2
    df["pat_morning_star"] = (
        bearish_c.shift(2) &
        (body.shift(1) <= 0.35 * body.shift(2)) &
        bullish_c &
        (c > d1_mid)
    )

    # ── Evening Star (3-candle bearish) ───────────────────────────────────
    d1_mid_e = (o.shift(2) + c.shift(2)) / 2
    df["pat_evening_star"] = (
        bullish_c.shift(2) &
        (body.shift(1) <= 0.35 * body.shift(2)) &
        bearish_c &
        (c < d1_mid_e)
    )

    # ── Doji ──────────────────────────────────────────────────────────────
    # Body ≤ 5 % of full range; some range must exist
    df["pat_doji"] = (
        (full_range > 0) &
        (body <= 0.05 * full_range)
    )

    return df


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


def compute_mas(df: pd.DataFrame) -> pd.DataFrame:
    for p in MA_PERIODS:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    return df


def compute_weekly_ma200(daily_df: pd.DataFrame) -> pd.Series:
    """
    Resample daily Close to weekly (Friday close), compute 200-week rolling mean,
    then forward-fill back onto the daily index.
    Returns a daily-indexed Series named 'MA200W'.
    """
    weekly_close = daily_df["Close"].resample("W").last()
    weekly_ma200 = weekly_close.rolling(200).mean()
    # Reindex to daily and forward-fill so every trading day has a value
    daily_ma200w = weekly_ma200.reindex(daily_df.index, method="ffill")
    daily_ma200w.name = "MA200W"
    return daily_ma200w


def compute_fibonacci(df: pd.DataFrame) -> dict[str, float]:
    """Fibonacci retracement on the 200-session range visible in the data."""
    window = df.tail(200)
    high = window["Close"].max()
    low  = window["Close"].min()
    diff = high - low
    return {f"{int(lvl * 100)}%": high - diff * lvl for lvl in FIB_LEVELS}


def signal_score(row: pd.Series, prev_row: pd.Series) -> tuple[int, list[str]]:
    """
    Returns (score, reasons).
    score:  +2 strong buy · +1 buy · 0 neutral · -1 sell · -2 strong sell
    """
    reasons: list[str] = []
    score = 0
    price = row["Close"]

    # ── 1. Price vs each MA ────────────────────────────────────────────────
    above_count = sum(1 for p in MA_PERIODS if price > row.get(f"MA{p}", np.nan))
    below_count = len(MA_PERIODS) - above_count

    if above_count == 5:
        score += 2
        reasons.append("Price above ALL moving averages (5/20/50/100/200) — bullish alignment")
    elif above_count >= 3:
        score += 1
        reasons.append(f"Price above {above_count}/5 moving averages")
    elif below_count == 5:
        score -= 2
        reasons.append("Price below ALL moving averages (5/20/50/100/200) — bearish alignment")
    elif below_count >= 3:
        score -= 1
        reasons.append(f"Price below {below_count}/5 moving averages")

    # ── 2. Golden / Death Cross (MA50 vs MA200) ───────────────────────────
    ma50_now  = row.get("MA50",  np.nan)
    ma200_now = row.get("MA200", np.nan)
    ma50_prev  = prev_row.get("MA50",  np.nan)
    ma200_prev = prev_row.get("MA200", np.nan)

    if all(not np.isnan(v) for v in [ma50_now, ma200_now, ma50_prev, ma200_prev]):
        if ma50_prev <= ma200_prev and ma50_now > ma200_now:
            score += 2
            reasons.append("Golden Cross detected (MA50 crossed above MA200) — strong bullish signal")
        elif ma50_prev >= ma200_prev and ma50_now < ma200_now:
            score -= 2
            reasons.append("Death Cross detected (MA50 crossed below MA200) — strong bearish signal")
        elif ma50_now > ma200_now:
            score += 1
            reasons.append("MA50 above MA200 — bullish trend")
        else:
            score -= 1
            reasons.append("MA50 below MA200 — bearish trend")

    # ── 3. Short-term momentum: MA5 vs MA20 ───────────────────────────────
    ma5_now  = row.get("MA5",  np.nan)
    ma20_now = row.get("MA20", np.nan)
    if not np.isnan(ma5_now) and not np.isnan(ma20_now):
        if ma5_now > ma20_now:
            score += 1
            reasons.append("MA5 above MA20 — short-term momentum positive")
        else:
            score -= 1
            reasons.append("MA5 below MA20 — short-term momentum negative")

    # ── 4. Long-term weekly trend: price vs MA200W ────────────────────────
    ma200w = row.get("MA200W", np.nan)
    if not np.isnan(ma200w):
        if price > ma200w:
            score += 2
            reasons.append("Price above 200-week MA — long-term secular uptrend")
        else:
            score -= 2
            reasons.append("Price below 200-week MA — long-term secular downtrend")

    return score, reasons


def overall_signal(score: int) -> tuple[str, str]:
    """Maps score → (label, css_color)."""
    if score >= 4:
        return "STRONG BUY",  "#16A34A"
    elif score >= 2:
        return "BUY",         "#22C55E"
    elif score >= 0:
        return "NEUTRAL",     "#EAB308"
    elif score >= -2:
        return "SELL",        "#F97316"
    else:
        return "STRONG SELL", "#DC2626"


# ── Chart builder ─────────────────────────────────────────────────────────────

def find_crosses(df: pd.DataFrame) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """
    Returns (golden_cross_dates, death_cross_dates) within df.
    A golden cross occurs when MA50 crosses above MA200 (prev below, now above).
    A death cross occurs when MA50 crosses below MA200 (prev above, now below).
    """
    ma50  = df["MA50"].dropna()
    ma200 = df["MA200"].dropna()
    common = ma50.index.intersection(ma200.index)
    if len(common) < 2:
        return pd.DatetimeIndex([]), pd.DatetimeIndex([])

    diff = (ma50[common] - ma200[common])          # positive = MA50 above MA200
    sign = diff.apply(lambda x: 1 if x > 0 else -1)
    sign_shift = sign.shift(1)

    golden = common[( sign == 1) & (sign_shift == -1)]
    death  = common[( sign == -1) & (sign_shift ==  1)]
    return golden, death


def compute_daily_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily gaps (current open - previous close) and track if filled."""
    df_gap = df[["Open", "Close", "High", "Low"]].copy()
    df_gap["Prev Close"] = df_gap["Close"].shift(1)
    df_gap["Gap"] = df_gap["Open"] - df_gap["Prev Close"]
    df_gap["Gap %"] = (df_gap["Gap"] / df_gap["Prev Close"] * 100).round(2)
    
    # Check if gap is filled within 3 trading days
    gap_filled_list = []
    for i in range(len(df_gap)):
        gap = df_gap.iloc[i]["Gap"]
        prev_close = df_gap.iloc[i]["Prev Close"]
        
        # Skip if no gap or NaN
        if pd.isna(gap) or pd.isna(prev_close) or gap == 0:
            gap_filled_list.append(False)
            continue
        
        is_filled = False
        gap_direction = 1 if gap > 0 else -1  # 1 for up gap, -1 for down gap
        
        # Check next 3 trading days
        for j in range(i + 1, min(i + 4, len(df_gap))):
            high = df_gap.iloc[j]["High"]
            low = df_gap.iloc[j]["Low"]
            
            if gap_direction > 0:  # Up gap: check if low touches prev close
                if low <= prev_close:
                    is_filled = True
                    break
            else:  # Down gap: check if high touches prev close
                if high >= prev_close:
                    is_filled = True
                    break
        
        gap_filled_list.append(is_filled)
    
    df_gap["Gap Filled"] = gap_filled_list
    df_gap["Open"] = df_gap["Open"].round(2)
    df_gap["Close"] = df_gap["Close"].round(2)
    df_gap["Prev Close"] = df_gap["Prev Close"].round(2)
    df_gap["Gap"] = df_gap["Gap"].round(2)
    return df_gap.dropna(subset=["Prev Close"])



def build_chart(df: pd.DataFrame, fib_levels: dict, ticker: str, show_vol: bool, show_fib: bool, show_patterns: bool) -> go.Figure:
    rows = 2 if show_vol else 1
    row_heights = [0.7, 0.3] if show_vol else [1.0]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name=ticker, increasing_line_color="#22C55E", decreasing_line_color="#EF4444",
    ), row=1, col=1)

    # Moving averages (daily)
    for p in MA_PERIODS:
        col = f"MA{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                name=f"MA{p}", line=dict(color=MA_COLORS[p], width=1.5),
                hovertemplate=f"MA{p}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # 200-week MA (weekly, forward-filled to daily)
    if "MA200W" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA200W"],
            name="MA200W", line=dict(color=MA200W_COLOR, width=2.5, dash="dash"),
            hovertemplate="MA200W: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Golden / Death cross markers
    golden_dates, death_dates = find_crosses(df)

    if len(golden_dates):
        fig.add_trace(go.Scatter(
            x=golden_dates,
            y=df.loc[golden_dates, "MA50"],
            mode="markers+text",
            name="Golden Cross",
            marker=dict(symbol="triangle-up", size=16, color="#FFD700",
                        line=dict(color="#B8860B", width=1)),
            text=["Golden Cross"] * len(golden_dates),
            textposition="top center",
            textfont=dict(color="#FFD700", size=10),
            hovertemplate="Golden Cross<br>%{x|%Y-%m-%d}<br>MA50: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if len(death_dates):
        fig.add_trace(go.Scatter(
            x=death_dates,
            y=df.loc[death_dates, "MA50"],
            mode="markers+text",
            name="Death Cross",
            marker=dict(symbol="triangle-down", size=16, color="#FF4444",
                        line=dict(color="#8B0000", width=1)),
            text=["Death Cross"] * len(death_dates),
            textposition="bottom center",
            textfont=dict(color="#FF4444", size=10),
            hovertemplate="Death Cross<br>%{x|%Y-%m-%d}<br>MA50: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if show_patterns:
        for col, label, bullish, symbol, color in REVERSAL_PATTERNS:
            if col not in df.columns:
                continue
            mask = df[col].fillna(False)
            if not mask.any():
                continue

            if bullish is True:
                y_values = df.loc[mask, "Low"] * 0.985
            elif bullish is False:
                y_values = df.loc[mask, "High"] * 1.015
            else:
                y_values = df.loc[mask, "Close"]

            fig.add_trace(go.Scatter(
                x=df.index[mask],
                y=y_values,
                mode="markers",
                name=label,
                marker=dict(symbol=symbol, size=14, color=color,
                            line=dict(color="#FFFFFF", width=1)),
                hovertemplate=f"{label}<br>%{{x|%Y-%m-%d}}<br>Close: $%{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # Fibonacci retracement lines
    if show_fib:
        for (label, price), color in zip(fib_levels.items(), FIB_COLORS):
            fig.add_hline(
                y=price, line_dash="dot", line_color=color, line_width=1,
                annotation_text=f"Fib {label}  ${price:.2f}",
                annotation_position="right",
                annotation_font_size=10,
                row=1, col=1,
            )

    # Volume bars
    if show_vol:
        colors = ["#22C55E" if c >= o else "#EF4444"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"], name="Volume",
            marker_color=colors, showlegend=False,
        ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=700,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=40, r=120, t=40, b=40),
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    if show_vol:
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


# ── Main flow ─────────────────────────────────────────────────────────────────

if analyze_btn or ticker:
    if not ticker:
        st.warning("Enter a ticker symbol in the sidebar.")
        st.stop()

    with st.spinner(f"Fetching data for **{ticker}**…"):
        end_date   = datetime.today()
        # Need ~200 weeks (~1400 days) warmup for MA200W plus display period
        start_date = end_date - timedelta(days=period_days + 1450)
        try:
            raw = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"),
                              end=end_date.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        except Exception as e:
            st.error(f"Failed to download data: {e}")
            st.stop()

    if raw.empty:
        st.error(f"No data found for **{ticker}**. Check the ticker symbol and try again.")
        st.stop()

    # Flatten multi-level columns yfinance ≥0.2 may return
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Drop rows where Close is NaN (can happen with invalid/delisted tickers)
    raw = raw.dropna(subset=["Close"])
    if len(raw) < 2:
        st.error(f"**{ticker}** returned insufficient price data. "
                 "It may be an invalid ticker, delisted, or too new. "
                 "Use the company search above to find the correct symbol.")
        st.stop()

    df = compute_mas(raw)
    # Compute 200-week MA on full history, then attach to daily df
    df["MA200W"] = compute_weekly_ma200(df)
    df = detect_reversal_patterns(df)
    # Trim to requested period for display (warmup rows hidden)
    display_df = df.tail(period_days).copy()

    if len(display_df) < 2:
        st.error(f"Not enough data in the selected period for **{ticker}**. "
                 "Try a longer historical period.")
        st.stop()

    fib = compute_fibonacci(display_df)

    # Signal on the latest row
    latest      = display_df.iloc[-1]
    prev        = display_df.iloc[-2]
    score, why  = signal_score(latest, prev)
    label, color = overall_signal(score)

    # ── KPI row ───────────────────────────────────────────────────────────
    info = yf.Ticker(ticker).fast_info
    company_name = ticker
    try:
        company_name = yf.Ticker(ticker).info.get("longName", ticker)
    except Exception:
        pass

    st.subheader(f"{company_name}  ({ticker})")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    price_now  = float(latest["Close"])
    price_prev = float(prev["Close"])
    change_pct = (price_now - price_prev) / price_prev * 100

    k1.metric("Last Close",    f"${price_now:.2f}", f"{change_pct:+.2f}%")
    k2.metric("MA 5",          f"${latest['MA5']:.2f}"    if not np.isnan(latest['MA5'])    else "N/A")
    k3.metric("MA 20",         f"${latest['MA20']:.2f}"   if not np.isnan(latest['MA20'])   else "N/A")
    k4.metric("MA 50",         f"${latest['MA50']:.2f}"   if not np.isnan(latest['MA50'])   else "N/A")
    k5.metric("MA 200",        f"${latest['MA200']:.2f}"  if not np.isnan(latest['MA200'])  else "N/A")
    k6.metric("MA 200W",       f"${latest['MA200W']:.2f}" if not np.isnan(latest['MA200W']) else "N/A")

    # ── Signal banner ─────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="
            background:{color}22;
            border:2px solid {color};
            border-radius:12px;
            padding:20px 28px;
            margin:16px 0;
        ">
            <span style="font-size:2rem;font-weight:800;color:{color};">{label}</span>
            <span style="font-size:1rem;color:#94A3B8;margin-left:16px;">
                Signal Score: {score:+d}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Reasoning ─────────────────────────────────────────────────────────
    with st.expander("Signal Reasoning", expanded=True):
        for r in why:
            icon = "✅" if "bullish" in r.lower() or "above" in r.lower() or "golden" in r.lower() else "🔴"
            st.markdown(f"- {icon} {r}")

    # ── Chart & Gap Table ─────────────────────────────────────────────────
    chart_col, gap_col = st.columns([2, 1])
    
    with chart_col:
        fig = build_chart(display_df, fib, ticker, show_volume, show_fibonacci, show_patterns)
        st.plotly_chart(fig, use_container_width=True)
    
    with gap_col:
        st.markdown("#### Daily Gaps (Last 30 Days)")
        gaps_df = compute_daily_gaps(display_df)
        gaps_last_30 = gaps_df.tail(30).copy()
        
        # Extract display columns and track unfilled status
        gaps_display_data = gaps_last_30[["Open", "Prev Close", "Gap", "Gap %", "Gap Filled"]].reset_index()
        gaps_display_data.columns = ["Date", "Open", "Prev Close", "Gap $", "Gap %", "Filled"]
        gaps_display_data["Date"] = gaps_display_data["Date"].dt.strftime("%m-%d")
        gaps_display_data = gaps_display_data.sort_values("Date", ascending=False).reset_index(drop=True)
        
        # Create colored display: highlight unfilled gaps in red
        gaps_for_display = gaps_display_data.drop("Filled", axis=1)
        
        # Apply styling: red background for unfilled gaps
        def highlight_unfilled(row):
            is_unfilled = gaps_display_data.loc[row.name, "Filled"] is False
            return ["background-color: rgba(239, 68, 68, 0.3); color: #EF4444; font-weight: bold"] * len(row) if is_unfilled else [""] * len(row)
        
        styled_df = gaps_for_display.style.apply(highlight_unfilled, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)

    if show_patterns:
        pattern_rows = []
        for col, label, bullish, *_ in REVERSAL_PATTERNS:
            count = int(display_df[col].sum()) if col in display_df.columns else 0
            if count:
                pattern_rows.append({
                    "Pattern": label,
                    "Count": count,
                    "Bias": "Bullish" if bullish is True else "Bearish" if bullish is False else "Neutral",
                })

        if pattern_rows:
            st.markdown("#### Reversal Patterns Detected")
            st.dataframe(pd.DataFrame(pattern_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No reversal patterns were detected in the selected period.")

    # ── Fibonacci table ───────────────────────────────────────────────────
    if show_fibonacci:
        st.markdown("#### Fibonacci Retracement Levels (200-session range)")
        fib_df = pd.DataFrame([
            {"Level": k, "Price": f"${v:.2f}",
             "vs Last Close": f"{(v - price_now) / price_now * 100:+.2f}%"}
            for k, v in fib.items()
        ])
        st.dataframe(fib_df, use_container_width=True, hide_index=True)

    # ── MA summary table ──────────────────────────────────────────────────
    st.markdown("#### Moving Average Summary")
    ma_rows = []
    for p in MA_PERIODS:
        val = latest.get(f"MA{p}", np.nan)
        if np.isnan(val):
            continue
        diff_pct = (price_now - val) / val * 100
        stance = "Above" if price_now > val else "Below"
        ma_rows.append({
            "MA Period": f"MA {p} (daily)",
            "Value": f"${val:.2f}",
            "Price vs MA": f"{diff_pct:+.2f}%",
            "Stance": stance,
        })
    # 200-week MA row
    val_w = latest.get("MA200W", np.nan)
    if not np.isnan(val_w):
        diff_pct_w = (price_now - val_w) / val_w * 100
        ma_rows.append({
            "MA Period": "MA 200 (weekly)",
            "Value": f"${val_w:.2f}",
            "Price vs MA": f"{diff_pct_w:+.2f}%",
            "Stance": "Above" if price_now > val_w else "Below",
        })
    ma_df = pd.DataFrame(ma_rows)
    st.dataframe(ma_df, use_container_width=True, hide_index=True)

else:
    st.info("Enter a ticker in the sidebar and click **Analyze**.")
