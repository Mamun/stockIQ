import streamlit as st

# All page paths are relative to the project root (where app.py lives).
_VIEWS = "src/stockiq/frontend/views"


def get_pages() -> dict:
    """Return the page registry consumed by st.navigation()."""
    return {
        "Market": [
            st.Page(f"{_VIEWS}/spy_dashboard.py",    title="SPY Dashboard",      icon="📈", url_path="spy",            default=True),
            st.Page(f"{_VIEWS}/volatility.py",       title="Volatility / VIX",   icon="📉", url_path="volatility"),
            st.Page(f"{_VIEWS}/ai_forecast_page.py", title="SPY AI Outlook",     icon="🤖", url_path="spy-ai-forecast"),
            st.Page(f"{_VIEWS}/spy_gap_table.py",    title="SPY Gap Table",      icon="📋", url_path="spy-gaps"),
            st.Page(f"{_VIEWS}/dte_guide.py",        title="0DTE Options Guide", icon="⚡", url_path="0dte-guide"),
        ],
        "S&P 500 Tools": [
            st.Page(f"{_VIEWS}/analyzer.py",                   title="Stock Analyzer",  icon="🔬", url_path="analyzer"),
            st.Page(f"{_VIEWS}/candle_momentum_screener.py",   title="Candle Screener", icon="📊", url_path="screener"),
        ],
        "Scanners": [
            st.Page(f"{_VIEWS}/premarket_scanner.py",       title="Pre-Market Scanner",    icon="🌅", url_path="premarket"),
            st.Page(f"{_VIEWS}/nasdaq_rsi_scanner.py",      title="NASDAQ RSI Scanner",    icon="📊", url_path="nasdaq-oversold"),
            st.Page(f"{_VIEWS}/bounce_radar_scanner.py",    title="MA200 Bounce Radar",    icon="📡", url_path="bounce-radar"),
            st.Page(f"{_VIEWS}/squeeze_scanner.py",         title="Short Squeeze Scanner", icon="🔥", url_path="squeeze"),
            st.Page(f"{_VIEWS}/strong_buy_scanner.py",      title="Analyst Buy Picks",     icon="💎", url_path="strong-buy"),
            st.Page(f"{_VIEWS}/strong_sell_scanner.py",     title="Analyst Sell Picks",    icon="🔻", url_path="strong-sell"),
            st.Page(f"{_VIEWS}/forward_pe_scanner.py",      title="Forward P/E Picks",     icon="📈", url_path="forward-pe"),
            st.Page(f"{_VIEWS}/munger_strategy_scanner.py", title="Munger Value Picks",    icon="🎩", url_path="munger"),
            st.Page(f"{_VIEWS}/etf_scanner.py",             title="ETF Scanner",           icon="🌐", url_path="etf-scanner"),
        ],
        "Info": [
            st.Page(f"{_VIEWS}/about.py", title="About StockIQ", icon="ℹ️", url_path="about"),
        ],
    }
