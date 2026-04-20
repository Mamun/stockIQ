# StockIQ — Free S&P 500 Technical Analysis & Screener

[![CI](https://github.com/Mamun/stockiq/actions/workflows/ci.yml/badge.svg)](https://github.com/Mamun/stockiq/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B)](https://streamlit.io)
[![Live App](https://img.shields.io/badge/Live%20App-stpicker.streamlit.app-brightgreen)](https://stpicker.streamlit.app/)
[![Sponsor](https://img.shields.io/badge/Sponsor-❤-pink)](https://github.com/sponsors/Mamun)

> **StockIQ** is a free, open-source web app that gives retail investors institutional-grade technical analysis — moving averages, RSI, Fibonacci retracements, candlestick patterns, options intelligence, and AI-powered forecasts — without a Bloomberg terminal.

## Try it now — no install needed

**[https://stpicker.streamlit.app/](https://stpicker.streamlit.app/)**

The live app runs on Streamlit Community Cloud and is free to use. No account or API key required.

---

## Features

### Market

| Page | What it does |
|------|-------------|
| **SPY Dashboard** | Real-time SPY price, index strip (S&P 500 / Nasdaq / Dow / Russell / VIX), RSI summary card, candlestick chart with VWAP (intraday) and options levels (daily), Options Intelligence section (Put/Call ratio, Max Pain, OI butterfly), SPY gap table, and VIX Fear Gauge |
| **SPY AI Outlook** | Claude-powered 10-day SPY directional forecast with technical context — gaps, RSI, price action, key levels |
| **SPY Gap Table** | Every daily gap since 2022, live fill status, intraday High/Low, RSI, and next-day direction — shareable standalone URL |

### S&P 500 Tools

| Page | What it does |
|------|-------------|
| **Stock Analyzer** | Interactive candlestick chart with MA5/20/50/100/200, weekly MA200, RSI subplot, Fibonacci retracement, 7 reversal patterns, Golden/Death cross, signal score card |
| **Candle Screener** | Top 50 S&P 500 stocks ranked by candle pattern strength (Strong Buy → Sell), weekly and monthly views |

### Scanners

| Page | What it does |
|------|-------------|
| **Pre-Market Scanner** | NASDAQ-100 pre-market movers with a 7-day daily close heatmap |
| **NASDAQ RSI Scanner** | NASDAQ-100 stocks filtered by RSI — quickly spot oversold / overbought conditions |
| **MA200 Bounce Radar** | Stocks within 5% of their 200-day MA — classic mean-reversion setups |
| **Short Squeeze Scanner** | High RSI + short interest = potential short squeeze candidates |
| **Analyst Buy Picks** | Highest-rated S&P 500 stocks by analyst consensus with ≥5% upside to price target |
| **Analyst Sell Picks** | Most-downgraded stocks with ≥5% downside to price target |
| **Munger Value Picks** | Quality companies (ROE, margins, growth, low debt) near their 200-week MA |
| **ETF Scanner** | Curated ETF categories — Retail Favorites, Semiconductors, Software — ranked by RSI and momentum |

---

## Screenshots

### SPY Dashboard
Full-page market hub: live SPY price, index strip, candlestick chart with VWAP, Options Intelligence (Max Pain, Put/Call ratio, OI butterfly), gap table, and VIX Fear Gauge.

![SPY Gap Table](docs/screenshots/spy_gaptable.png)

---

### AI-Powered SPY Outlook
Claude analyses recent gaps, RSI, and price action to generate a 10-day directional outlook with key levels and a plain-English rationale.

![SPY AI Forecast](docs/screenshots/spy_ai_claude_forecast.png)

---

### Stock Analyzer
Interactive candlestick chart with MA5/20/50/100/200, weekly MA200, RSI subplot, Fibonacci retracement, seven reversal patterns, and a signal score card.

![Stock Analyzer](docs/screenshots/analyzer.png)

---

### ETF Scanner
Curated ETF categories — Retail Favorites, Semiconductors, Software — ranked by RSI and momentum for quick sector rotation ideas.

![ETF Scanner](docs/screenshots/etf_scanner.png)

---

## Quick Start

### Prerequisites

- Python 3.11 or 3.12
- An [Anthropic API key](https://console.anthropic.com/) (only required for the AI Outlook page)

### Installation

```bash
git clone https://github.com/Mamun/stockiq.git
cd stockiq

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .            # installs the stockiq package + all dependencies
```

### Configuration

Create `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Or set the environment variable directly:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

### Optional: limit screener scope

The weekly/monthly screener scans the top 50 S&P 500 tickers by default. To speed up development:

```bash
export SCREENER_TICKER_COUNT=10
streamlit run app.py
```

---

## Running Tests

```bash
pip install pytest pytest-cov
pytest                                    # all tests
pytest --cov=. --cov-report=term-missing  # with coverage
pytest tests/test_indicators.py -v        # single file
```

Tests are network-free — all `yfinance` calls are mocked.

---

## Project Structure

```
.
├── app.py                          # Streamlit entry point — navigation wiring
├── src/stockiq/
│   ├── config.py                   # MA periods, colors, Fibonacci levels, ticker universe
│   ├── backend/
│   │   ├── models/                 # Pure data models (indicators, signals, options, spy context)
│   │   ├── data/
│   │   │   ├── yf_fetch.py         # yfinance OHLCV download & company search
│   │   │   ├── market.py           # SPY/VIX/index snapshot helpers (TTL-cached)
│   │   │   ├── screeners/          # Per-strategy screener modules (candle, analyst, volatility, ETF, …)
│   │   │   ├── local_ohlc_cache.py # Local OHLC cache for gap detection
│   │   │   ├── local_gap_cache.py  # Local gap cache
│   │   │   └── gcs_*.py            # GCS-backed caches (fundamentals, short interest, analyst consensus)
│   │   ├── services/
│   │   │   ├── spy_service.py      # SPY quote, chart, gap table
│   │   │   ├── market_service.py   # VIX, indices, put/call ratio, options analysis
│   │   │   ├── spy_dashboard_service.py  # Facade combining spy + market for the dashboard page
│   │   │   ├── analyzer_service.py # Per-ticker technical analysis pipeline
│   │   │   ├── ai_forecast_service.py    # Claude forecast composition
│   │   │   └── scanners/           # Scanner services (NASDAQ, SPX, ETF, pre-market)
│   │   ├── llm/                    # Claude provider + prompt templates
│   │   └── cache.py                # TTL cache decorator
│   └── frontend/
│       └── views/                  # Streamlit page modules (one file per page)
│           └── components/         # Reusable UI components (charts, gap table, summary card)
├── scripts/                        # Offline GCS cache build scripts
└── tests/                          # pytest test suite
```

---

## Tech Stack

| Library | Purpose |
|---------|---------|
| [Streamlit](https://streamlit.io) | Web UI framework |
| [yfinance](https://github.com/ranaroussi/yfinance) | Market data (Yahoo Finance) |
| [Plotly](https://plotly.com/python/) | Interactive charts |
| [pandas](https://pandas.pydata.org) | Data manipulation |
| [NumPy](https://numpy.org) | Numerical computation |
| [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) | Claude AI forecast |
| [Google Cloud Storage](https://cloud.google.com/storage) | Pre-built screener cache (GCS bucket) |

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a PR.

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and add tests
4. Run `pytest` and `ruff check .`
5. Open a Pull Request

See [good first issues](https://github.com/Mamun/stockiq/labels/good%20first%20issue) for a place to start.

---

## Sponsoring StockIQ

StockIQ is free and open source. Hosting, API costs, and development time are funded entirely by community support. If this tool saves you time or helps your trading research, please consider sponsoring:

| Platform | Link |
|----------|------|
| **GitHub Sponsors** | [github.com/sponsors/Mamun](https://github.com/sponsors/Mamun) |
| **Ko-fi** | [ko-fi.com/stockiq](https://ko-fi.com/stockiq) |
| **Open Collective** | [opencollective.com/stockiq](https://opencollective.com/stockiq) |
| **Buy Me a Coffee** | [buymeacoffee.com/mamuninfo](https://buymeacoffee.com/mamuninfo) |

Your sponsorship helps keep the project free for everyone and funds:

- Anthropic API costs for the AI Outlook feature
- Ongoing data-quality improvements
- New screeners and indicators requested by the community

---

## Roadmap

- [ ] Portfolio tracker — track a watchlist over time
- [ ] Alert system — email/webhook when a signal fires
- [ ] More tickers — extend beyond S&P 500
- [ ] MACD and Bollinger Bands indicators
- [ ] Mobile-responsive layout improvements
- [ ] Docker image for one-command deployment

---

## License

[MIT](LICENSE) © 2025 Mamun

---

## Disclaimer

StockIQ is for **educational and informational purposes only**. Nothing on this site constitutes financial advice. Always do your own research before making investment decisions.
