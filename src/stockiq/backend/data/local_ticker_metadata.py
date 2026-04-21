"""
Local ticker metadata cache (company name + sector).

Populated by: scripts/build_metadata_cache.py (run as needed)
Cache file:   cache/screener/ticker_metadata.json

Falls back to a static hardcoded dict when the cache file is absent,
so the app works out of the box without running any build scripts first.
"""

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent.parent.parent / "cache" / "screener" / "ticker_metadata.json"
_metadata_cache: dict | None = None


class TickerMeta(TypedDict):
    name: str
    sector: str


# Static fallback — covers all 200 tickers in the SPX universe.
# Company names and sectors change rarely; the local cache overrides these when available.
_STATIC_FALLBACK: dict[str, TickerMeta] = {
    # ── Mega-cap / top 50 ─────────────────────────────────────────────────────
    "AAPL":  {"name": "Apple Inc.",                     "sector": "Technology"},
    "MSFT":  {"name": "Microsoft Corporation",           "sector": "Technology"},
    "NVDA":  {"name": "NVIDIA Corporation",              "sector": "Technology"},
    "AMZN":  {"name": "Amazon.com Inc.",                 "sector": "Consumer Discretionary"},
    "GOOGL": {"name": "Alphabet Inc. (Class A)",         "sector": "Communication Services"},
    "META":  {"name": "Meta Platforms Inc.",             "sector": "Communication Services"},
    "BRK-B": {"name": "Berkshire Hathaway Inc.",         "sector": "Financials"},
    "LLY":   {"name": "Eli Lilly and Company",           "sector": "Healthcare"},
    "AVGO":  {"name": "Broadcom Inc.",                   "sector": "Technology"},
    "TSLA":  {"name": "Tesla Inc.",                      "sector": "Consumer Discretionary"},
    "JPM":   {"name": "JPMorgan Chase & Co.",            "sector": "Financials"},
    "V":     {"name": "Visa Inc.",                       "sector": "Financials"},
    "UNH":   {"name": "UnitedHealth Group",              "sector": "Healthcare"},
    "XOM":   {"name": "Exxon Mobil Corporation",         "sector": "Energy"},
    "MA":    {"name": "Mastercard Incorporated",         "sector": "Financials"},
    "HD":    {"name": "The Home Depot Inc.",             "sector": "Consumer Discretionary"},
    "PG":    {"name": "Procter & Gamble Co.",            "sector": "Consumer Staples"},
    "JNJ":   {"name": "Johnson & Johnson",               "sector": "Healthcare"},
    "ABBV":  {"name": "AbbVie Inc.",                     "sector": "Healthcare"},
    "WMT":   {"name": "Walmart Inc.",                    "sector": "Consumer Staples"},
    "COST":  {"name": "Costco Wholesale Corporation",    "sector": "Consumer Staples"},
    "MRK":   {"name": "Merck & Co. Inc.",                "sector": "Healthcare"},
    "ORCL":  {"name": "Oracle Corporation",              "sector": "Technology"},
    "CRM":   {"name": "Salesforce Inc.",                 "sector": "Technology"},
    "BAC":   {"name": "Bank of America Corporation",     "sector": "Financials"},
    "AMD":   {"name": "Advanced Micro Devices Inc.",     "sector": "Technology"},
    "KO":    {"name": "The Coca-Cola Company",           "sector": "Consumer Staples"},
    "CVX":   {"name": "Chevron Corporation",             "sector": "Energy"},
    "MCD":   {"name": "McDonald's Corporation",          "sector": "Consumer Discretionary"},
    "NFLX":  {"name": "Netflix Inc.",                    "sector": "Communication Services"},
    "PFE":   {"name": "Pfizer Inc.",                     "sector": "Healthcare"},
    "ABT":   {"name": "Abbott Laboratories",             "sector": "Healthcare"},
    "TXN":   {"name": "Texas Instruments Incorporated",  "sector": "Technology"},
    "CSCO":  {"name": "Cisco Systems Inc.",              "sector": "Technology"},
    "PM":    {"name": "Philip Morris International",     "sector": "Consumer Staples"},
    "LIN":   {"name": "Linde plc",                       "sector": "Materials"},
    "ACN":   {"name": "Accenture plc",                   "sector": "Technology"},
    "NKE":   {"name": "Nike Inc.",                       "sector": "Consumer Discretionary"},
    "DIS":   {"name": "The Walt Disney Company",         "sector": "Communication Services"},
    "AXP":   {"name": "American Express Company",        "sector": "Financials"},
    "HON":   {"name": "Honeywell International Inc.",    "sector": "Industrials"},
    "INTC":  {"name": "Intel Corporation",               "sector": "Technology"},
    "IBM":   {"name": "International Business Machines", "sector": "Technology"},
    "AMGN":  {"name": "Amgen Inc.",                      "sector": "Healthcare"},
    "GE":    {"name": "GE Aerospace",                    "sector": "Industrials"},
    "LOW":   {"name": "Lowe's Companies Inc.",           "sector": "Consumer Discretionary"},
    "SBUX":  {"name": "Starbucks Corporation",           "sector": "Consumer Discretionary"},
    "BA":    {"name": "The Boeing Company",              "sector": "Industrials"},
    "RTX":   {"name": "RTX Corporation",                 "sector": "Industrials"},
    "CAT":   {"name": "Caterpillar Inc.",                "sector": "Industrials"},
    # ── Next 50 ───────────────────────────────────────────────────────────────
    "NOW":   {"name": "ServiceNow Inc.",                 "sector": "Technology"},
    "INTU":  {"name": "Intuit Inc.",                     "sector": "Technology"},
    "ISRG":  {"name": "Intuitive Surgical Inc.",         "sector": "Healthcare"},
    "GS":    {"name": "The Goldman Sachs Group Inc.",    "sector": "Financials"},
    "SPGI":  {"name": "S&P Global Inc.",                 "sector": "Financials"},
    "MS":    {"name": "Morgan Stanley",                  "sector": "Financials"},
    "BLK":   {"name": "BlackRock Inc.",                  "sector": "Financials"},
    "SYK":   {"name": "Stryker Corporation",             "sector": "Healthcare"},
    "PEP":   {"name": "PepsiCo Inc.",                    "sector": "Consumer Staples"},
    "TMO":   {"name": "Thermo Fisher Scientific Inc.",   "sector": "Healthcare"},
    "PLD":   {"name": "Prologis Inc.",                   "sector": "Real Estate"},
    "VRTX":  {"name": "Vertex Pharmaceuticals Inc.",     "sector": "Healthcare"},
    "REGN":  {"name": "Regeneron Pharmaceuticals Inc.",  "sector": "Healthcare"},
    "MMC":   {"name": "Marsh & McLennan Companies",      "sector": "Financials"},
    "CB":    {"name": "Chubb Limited",                   "sector": "Financials"},
    "ETN":   {"name": "Eaton Corporation plc",           "sector": "Industrials"},
    "DE":    {"name": "Deere & Company",                 "sector": "Industrials"},
    "BKNG":  {"name": "Booking Holdings Inc.",           "sector": "Consumer Discretionary"},
    "MDT":   {"name": "Medtronic plc",                   "sector": "Healthcare"},
    "NEE":   {"name": "NextEra Energy Inc.",             "sector": "Utilities"},
    "MO":    {"name": "Altria Group Inc.",               "sector": "Consumer Staples"},
    "T":     {"name": "AT&T Inc.",                       "sector": "Communication Services"},
    "VZ":    {"name": "Verizon Communications Inc.",     "sector": "Communication Services"},
    "CL":    {"name": "Colgate-Palmolive Company",       "sector": "Consumer Staples"},
    "BMY":   {"name": "Bristol-Myers Squibb Company",    "sector": "Healthcare"},
    "GILD":  {"name": "Gilead Sciences Inc.",            "sector": "Healthcare"},
    "CI":    {"name": "The Cigna Group",                 "sector": "Healthcare"},
    "ELV":   {"name": "Elevance Health Inc.",            "sector": "Healthcare"},
    "HCA":   {"name": "HCA Healthcare Inc.",             "sector": "Healthcare"},
    "MCO":   {"name": "Moody's Corporation",             "sector": "Financials"},
    "ICE":   {"name": "Intercontinental Exchange Inc.",  "sector": "Financials"},
    "TJX":   {"name": "The TJX Companies Inc.",          "sector": "Consumer Discretionary"},
    "USB":   {"name": "U.S. Bancorp",                    "sector": "Financials"},
    "PNC":   {"name": "PNC Financial Services Group",    "sector": "Financials"},
    "AON":   {"name": "Aon plc",                         "sector": "Financials"},
    "ZTS":   {"name": "Zoetis Inc.",                     "sector": "Healthcare"},
    "COF":   {"name": "Capital One Financial Corp.",     "sector": "Financials"},
    "APD":   {"name": "Air Products and Chemicals Inc.", "sector": "Materials"},
    "ECL":   {"name": "Ecolab Inc.",                     "sector": "Materials"},
    "CME":   {"name": "CME Group Inc.",                  "sector": "Financials"},
    "LRCX":  {"name": "Lam Research Corporation",        "sector": "Technology"},
    "KLAC":  {"name": "KLA Corporation",                 "sector": "Technology"},
    "AMAT":  {"name": "Applied Materials Inc.",          "sector": "Technology"},
    "PANW":  {"name": "Palo Alto Networks Inc.",         "sector": "Technology"},
    "MU":    {"name": "Micron Technology Inc.",          "sector": "Technology"},
    "SNPS":  {"name": "Synopsys Inc.",                   "sector": "Technology"},
    "CDNS":  {"name": "Cadence Design Systems Inc.",     "sector": "Technology"},
    "ADI":   {"name": "Analog Devices Inc.",             "sector": "Technology"},
    "MRVL":  {"name": "Marvell Technology Inc.",         "sector": "Technology"},
    "QCOM":  {"name": "Qualcomm Incorporated",           "sector": "Technology"},
    # ── Additional 100 ────────────────────────────────────────────────────────
    "WFC":   {"name": "Wells Fargo & Company",           "sector": "Financials"},
    "SCHW":  {"name": "The Charles Schwab Corporation",  "sector": "Financials"},
    "AIG":   {"name": "American International Group",    "sector": "Financials"},
    "ALL":   {"name": "The Allstate Corporation",        "sector": "Financials"},
    "PRU":   {"name": "Prudential Financial Inc.",       "sector": "Financials"},
    "AFL":   {"name": "Aflac Incorporated",              "sector": "Financials"},
    "MET":   {"name": "MetLife Inc.",                    "sector": "Financials"},
    "TRV":   {"name": "The Travelers Companies Inc.",    "sector": "Financials"},
    "PGR":   {"name": "The Progressive Corporation",     "sector": "Financials"},
    "BK":    {"name": "The Bank of New York Mellon",     "sector": "Financials"},
    "STT":   {"name": "State Street Corporation",        "sector": "Financials"},
    "FITB":  {"name": "Fifth Third Bancorp",             "sector": "Financials"},
    "KEY":   {"name": "KeyCorp",                         "sector": "Financials"},
    "RF":    {"name": "Regions Financial Corporation",   "sector": "Financials"},
    "MMM":   {"name": "3M Company",                      "sector": "Industrials"},
    "FDX":   {"name": "FedEx Corporation",               "sector": "Industrials"},
    "UPS":   {"name": "United Parcel Service Inc.",      "sector": "Industrials"},
    "EMR":   {"name": "Emerson Electric Co.",            "sector": "Industrials"},
    "GD":    {"name": "General Dynamics Corporation",    "sector": "Industrials"},
    "LMT":   {"name": "Lockheed Martin Corporation",     "sector": "Industrials"},
    "NOC":   {"name": "Northrop Grumman Corporation",    "sector": "Industrials"},
    "SLB":   {"name": "SLB",                             "sector": "Energy"},
    "BSX":   {"name": "Boston Scientific Corporation",   "sector": "Healthcare"},
    "EW":    {"name": "Edwards Lifesciences Corporation","sector": "Healthcare"},
    "NSC":   {"name": "Norfolk Southern Corporation",    "sector": "Industrials"},
    "UNP":   {"name": "Union Pacific Corporation",       "sector": "Industrials"},
    "CSX":   {"name": "CSX Corporation",                 "sector": "Industrials"},
    "GWW":   {"name": "W.W. Grainger Inc.",              "sector": "Industrials"},
    "ITW":   {"name": "Illinois Tool Works Inc.",        "sector": "Industrials"},
    "PH":    {"name": "Parker Hannifin Corporation",     "sector": "Industrials"},
    "AME":   {"name": "AMETEK Inc.",                     "sector": "Industrials"},
    "TGT":   {"name": "Target Corporation",              "sector": "Consumer Discretionary"},
    "DG":    {"name": "Dollar General Corporation",      "sector": "Consumer Discretionary"},
    "KR":    {"name": "The Kroger Co.",                  "sector": "Consumer Staples"},
    "CVS":   {"name": "CVS Health Corporation",          "sector": "Healthcare"},
    "MCK":   {"name": "McKesson Corporation",            "sector": "Healthcare"},
    "IQV":   {"name": "IQVIA Holdings Inc.",             "sector": "Healthcare"},
    "DGX":   {"name": "Quest Diagnostics Incorporated",  "sector": "Healthcare"},
    "A":     {"name": "Agilent Technologies Inc.",       "sector": "Healthcare"},
    "STE":   {"name": "STERIS plc",                      "sector": "Healthcare"},
    "ADSK":  {"name": "Autodesk Inc.",                   "sector": "Technology"},
    "IT":    {"name": "Gartner Inc.",                    "sector": "Technology"},
    "GDDY":  {"name": "GoDaddy Inc.",                    "sector": "Technology"},
    "VRSN":  {"name": "VeriSign Inc.",                   "sector": "Technology"},
    "CDW":   {"name": "CDW Corporation",                 "sector": "Technology"},
    "WDC":   {"name": "Western Digital Corporation",     "sector": "Technology"},
    "STX":   {"name": "Seagate Technology Holdings",     "sector": "Technology"},
    "HPQ":   {"name": "HP Inc.",                         "sector": "Technology"},
    "DELL":  {"name": "Dell Technologies Inc.",          "sector": "Technology"},
    "ZBRA":  {"name": "Zebra Technologies Corporation",  "sector": "Technology"},
    "COP":   {"name": "ConocoPhillips",                  "sector": "Energy"},
    "EOG":   {"name": "EOG Resources Inc.",              "sector": "Energy"},
    "DVN":   {"name": "Devon Energy Corporation",        "sector": "Energy"},
    "OXY":   {"name": "Occidental Petroleum Corporation","sector": "Energy"},
    "HAL":   {"name": "Halliburton Company",             "sector": "Energy"},
    "MPC":   {"name": "Marathon Petroleum Corporation",  "sector": "Energy"},
    "PSX":   {"name": "Phillips 66",                     "sector": "Energy"},
    "VLO":   {"name": "Valero Energy Corporation",       "sector": "Energy"},
    "HES":   {"name": "Hess Corporation",                "sector": "Energy"},
    "MRO":   {"name": "Marathon Oil Corporation",        "sector": "Energy"},
    "EQT":   {"name": "EQT Corporation",                 "sector": "Energy"},
    "D":     {"name": "Dominion Energy Inc.",            "sector": "Utilities"},
    "DUK":   {"name": "Duke Energy Corporation",         "sector": "Utilities"},
    "SO":    {"name": "The Southern Company",            "sector": "Utilities"},
    "SRE":   {"name": "Sempra",                          "sector": "Utilities"},
    "ES":    {"name": "Eversource Energy",               "sector": "Utilities"},
    "PPL":   {"name": "PPL Corporation",                 "sector": "Utilities"},
    "CMS":   {"name": "CMS Energy Corporation",          "sector": "Utilities"},
    "ATO":   {"name": "Atmos Energy Corporation",        "sector": "Utilities"},
    "WEC":   {"name": "WEC Energy Group Inc.",           "sector": "Utilities"},
    "XEL":   {"name": "Xcel Energy Inc.",                "sector": "Utilities"},
    "PCG":   {"name": "PG&E Corporation",                "sector": "Utilities"},
    "SPG":   {"name": "Simon Property Group Inc.",       "sector": "Real Estate"},
    "AMT":   {"name": "American Tower Corporation",      "sector": "Real Estate"},
    "CCI":   {"name": "Crown Castle Inc.",               "sector": "Real Estate"},
    "EQIX":  {"name": "Equinix Inc.",                    "sector": "Real Estate"},
    "PSA":   {"name": "Public Storage",                  "sector": "Real Estate"},
    "WELL":  {"name": "Welltower Inc.",                  "sector": "Real Estate"},
    "DLR":   {"name": "Digital Realty Trust Inc.",       "sector": "Real Estate"},
    "O":     {"name": "Realty Income Corporation",       "sector": "Real Estate"},
    "EQR":   {"name": "Equity Residential",              "sector": "Real Estate"},
    "AVB":   {"name": "AvalonBay Communities Inc.",      "sector": "Real Estate"},
    "EXR":   {"name": "Extra Space Storage Inc.",        "sector": "Real Estate"},
    "IRM":   {"name": "Iron Mountain Inc.",              "sector": "Real Estate"},
    "UBER":  {"name": "Uber Technologies Inc.",          "sector": "Industrials"},
    "DASH":  {"name": "DoorDash Inc.",                   "sector": "Consumer Discretionary"},
    "RCL":   {"name": "Royal Caribbean Cruises Ltd.",    "sector": "Consumer Discretionary"},
    "HLT":   {"name": "Hilton Worldwide Holdings Inc.",  "sector": "Consumer Discretionary"},
    "CCL":   {"name": "Carnival Corporation & plc",      "sector": "Consumer Discretionary"},
    "DAL":   {"name": "Delta Air Lines Inc.",            "sector": "Industrials"},
    "UAL":   {"name": "United Airlines Holdings Inc.",   "sector": "Industrials"},
    "NET":   {"name": "Cloudflare Inc.",                 "sector": "Technology"},
    "SNOW":  {"name": "Snowflake Inc.",                  "sector": "Technology"},
    "MDB":   {"name": "MongoDB Inc.",                    "sector": "Technology"},
    "VEEV":  {"name": "Veeva Systems Inc.",              "sector": "Healthcare"},
    "HUBS":  {"name": "HubSpot Inc.",                    "sector": "Technology"},
    "TWLO":  {"name": "Twilio Inc.",                     "sector": "Technology"},
    "PINS":  {"name": "Pinterest Inc.",                  "sector": "Communication Services"},
    "F":     {"name": "Ford Motor Company",              "sector": "Consumer Discretionary"},
    "GM":    {"name": "General Motors Company",          "sector": "Consumer Discretionary"},
}


def get_metadata() -> dict[str, TickerMeta]:
    """
    Return ticker metadata dict, with this priority:
      1. Local cache file (if cache/screener/ticker_metadata.json exists)
      2. Static hardcoded fallback (always available, no file needed)
    """
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    if not _CACHE_FILE.exists():
        logger.debug("Ticker metadata cache not found at %s — using static fallback", _CACHE_FILE)
        _metadata_cache = dict(_STATIC_FALLBACK)
        return _metadata_cache

    try:
        gcs_data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        _metadata_cache = {**_STATIC_FALLBACK, **gcs_data}
        logger.info("Loaded ticker metadata: %d tickers from %s", len(gcs_data), _CACHE_FILE)
    except Exception as exc:
        logger.warning("Failed to load ticker metadata cache (%s) — using static fallback", exc)
        _metadata_cache = dict(_STATIC_FALLBACK)

    return _metadata_cache


def invalidate() -> None:
    """Force a fresh load on next get_metadata() call."""
    global _metadata_cache
    _metadata_cache = None
