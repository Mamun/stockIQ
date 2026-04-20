import pandas as pd
import streamlit as st


def render_about_tab() -> None:
    st.title("ℹ️ About This Stock Analyzer")
    st.markdown("""
    **StockIQ** is a free technical analysis tool designed to help traders and investors
    make informed decisions with real-time data.

    **Key Features:**
    - **Moving Averages**: Track price trends with 5, 20, 50, 100, and 200-day moving averages
    - **Fibonacci Retracement**: Identify potential support and resistance levels
    - **Reversal Pattern Detection**: Automatic detection of 7 candlestick reversal patterns
    - **Golden/Death Cross Signals**: Major trend reversal indicators based on MA50 and MA200 crossovers
    - **Buy/Sell Signal Score**: Scoring system combining multiple technical indicators
    - **Weekly Trend Analysis**: 200-week moving average for long-term secular trend confirmation

    **How It Works:**
    1. Use the **Search by Company** tab to find a stock by name or enter a ticker directly
    2. Select your preferred historical period
    3. Choose which indicators to display
    4. Click **Analyze** to generate real-time technical analysis

    **Screener:**
    The **Weekly/Monthly Screener** analyzes the top 30 S&P 500 stocks and generates BUY/SELL signals
    based on weekly and monthly candlestick patterns.

    - **BUY**: All 4 recent weeks green AND at least 3 of the last 4 months green
    - **SELL/HOLD**: All other combinations

    All data is sourced from Yahoo Finance and updated in real-time.
    """)

    st.markdown("---")
    st.markdown("**Supported Reversal Patterns:**")
    st.dataframe(pd.DataFrame([
        {"Pattern": "Hammer",            "Type": "Bullish", "Description": "Small body at top, long lower wick — signals potential reversal from downtrend"},
        {"Pattern": "Bullish Engulfing", "Type": "Bullish", "Description": "Green candle fully engulfs prior red candle — strong reversal signal"},
        {"Pattern": "Morning Star",      "Type": "Bullish", "Description": "3-candle pattern: bearish → indecision → bullish — reversal from downtrend"},
        {"Pattern": "Shooting Star",     "Type": "Bearish", "Description": "Small body at bottom, long upper wick — signals potential reversal from uptrend"},
        {"Pattern": "Bearish Engulfing", "Type": "Bearish", "Description": "Red candle fully engulfs prior green candle — strong reversal signal"},
        {"Pattern": "Evening Star",      "Type": "Bearish", "Description": "3-candle pattern: bullish → indecision → bearish — reversal from uptrend"},
        {"Pattern": "Doji",              "Type": "Neutral", "Description": "Open ≈ Close — market indecision, potential trend change"},
    ]), width='stretch', hide_index=True, height=8 * 35 + 4)


render_about_tab()

