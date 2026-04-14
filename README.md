# IndexIQ — Free S&P 500 Technical Analysis & Screener

[![CI](https://github.com/Mamun/indexiq/actions/workflows/ci.yml/badge.svg)](https://github.com/Mamun/indexiq/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B)](https://streamlit.io)
[![Sponsor](https://img.shields.io/badge/Sponsor-❤-pink)](https://github.com/sponsors/Mamun)

> **IndexIQ** is a free, open-source web app that gives retail investors institutional-grade technical analysis — moving averages, RSI, Fibonacci retracements, candlestick patterns, and AI-powered forecasts — without a Bloomberg terminal.

---

## Features

| Page | What it does |
|------|-------------|
| **SPY Live** | Real-time SPY price, index snapshot (S&P 500 / Nasdaq / Dow / Russell / VIX), intraday chart |
| **SPY Gap Table** | Every daily gap since 2022, live fill status updated during the session |
| **SPY AI Forecast** | Claude-powered 10-day SPY directional forecast with technical context |
| **Stock Analyzer** | Interactive chart with MA5/20/50/100/200, weekly MA200, RSI, Fibonacci retracement, 7 reversal patterns, Golden/Death cross, signal score |
| **Weekly/Monthly Screener** | Top 50 S&P 500 stocks ranked by candle pattern strength (Strong Buy → Sell) |
| **Bounce Radar** | Stocks within 5% of their 200-day MA — classic mean-reversion setups |
| **Squeeze Scanner** | High RSI + short interest = potential short squeeze candidates |
| **Strong Buy** | Analyst consensus: highest-rated stocks with ≥5% upside to price target |
| **Strong Sell** | Analyst consensus: most-downgraded stocks with ≥5% downside |
| **Munger Watchlist** | Quality companies (ROE, margins, growth, low debt) near their 200-week MA |

---

## Screenshots

> _Coming soon — feel free to add screenshots in a PR!_

---

## Quick Start

### Prerequisites

- Python 3.11 or 3.12
- An [Anthropic API key](https://console.anthropic.com/) (only required for the AI Forecast page)

### Installation

```bash
git clone https://github.com/Mamun/indexiq.git
cd picker

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
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
├── app.py              # Streamlit entry point — navigation wiring
├── config.py           # MA periods, colors, Fibonacci levels, ticker universe
├── indicators.py       # MA, RSI, Fibonacci, gap detection, reversal patterns
├── signals.py          # Signal scoring, golden/death cross detection
├── charts.py           # Plotly interactive chart builder
├── seo.py              # Meta tags & JSON-LD schema injection
├── data/
│   ├── fetch.py        # yfinance OHLCV download & company search
│   ├── market.py       # SPY/VIX/index snapshot helpers (with TTL caching)
│   └── screeners.py    # Multi-ticker screeners (bounce, squeeze, Munger, analyst)
├── views/              # Streamlit page modules (one file per page)
└── tests/              # pytest test suite
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

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a PR.

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and add tests
4. Run `pytest` and `ruff check .`
5. Open a Pull Request

See [good first issues](https://github.com/Mamun/indexiq/labels/good%20first%20issue) for a place to start.

---

## Sponsoring IndexIQ

IndexIQ is free and open source. Hosting, API costs, and development time are funded entirely by community support. If this tool saves you time or helps your trading research, please consider sponsoring:

| Platform | Link |
|----------|------|
| **GitHub Sponsors** | [github.com/sponsors/Mamun](https://github.com/sponsors/Mamun) |
| **Ko-fi** | [ko-fi.com/indexiq](https://ko-fi.com/indexiq) |
| **Open Collective** | [opencollective.com/indexiq](https://opencollective.com/indexiq) |
| **Buy Me a Coffee** | [buymeacoffee.com/indexiq](https://buymeacoffee.com/indexiq) |

Your sponsorship helps keep the project free for everyone and funds:

- Anthropic API costs for the AI Forecast feature
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

IndexIQ is for **educational and informational purposes only**. Nothing on this site constitutes financial advice. Always do your own research before making investment decisions.
