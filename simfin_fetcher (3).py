"""
simfin_fetcher.py  (v3 — free-tier compatible, loops year by year)
-------------------------------------------------------------------
Free tier limitation: can only request ONE period at a time.
This version loops through the last 7 years individually and stitches
the results together into DataFrames matching yfinance orientation.

Place next to main.py in your GitHub repo.
"""

import pandas as pd
import requests
from datetime import datetime

_BASE = "https://backend.simfin.com/api/v3"


def _get(path: str, api_key: str, params: dict) -> list | dict | None:
    headers = {"Authorization": f"api-key {api_key}",
               "Accept": "application/json"}
    try:
        r = requests.get(f"{_BASE}{path}", headers=headers,
                         params=params, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[simfin_fetcher] {e}")
        return None


def _extract_data(raw) -> dict | None:
    """Pull the flat data dict from a single-period verbose response."""
    if not raw:
        return None
    if isinstance(raw, dict):
        raw = [raw]
    if not raw:
        return None
    company = raw[0]
    statements = company.get("statements", [])
    if not statements:
        return None
    # Take first statement block
    block = statements[0]
    report_date = block.get("reportDate") or block.get("date")
    data = block.get("data", {})
    if not report_date or not data:
        return None
    return {"date": report_date, "data": data}


def _fetch_annual_all_years(ticker: str, api_key: str, stmt: str) -> pd.DataFrame:
    """
    Fetch annual (FY) statement for each of the last 7 years one at a time.
    Returns DataFrame: rows=metrics, cols=Timestamps (yfinance orientation).
    """
    current_year = datetime.now().year
    rows = {}

    for year in range(current_year - 7, current_year + 1):
        raw = _get(
            "/companies/statements/verbose",
            api_key,
            params={
                "ticker":     ticker,
                "statements": stmt,
                "period":     "FY",
                "fyear":      str(year),
            },
        )
        result = _extract_data(raw)
        if result:
            ts = pd.Timestamp(result["date"])
            rows[ts] = result["data"]

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index = pd.DatetimeIndex(df.index)
    return df.sort_index().T   # yfinance orientation: rows=metrics, cols=dates


def _fetch_quarterly_all_years(ticker: str, api_key: str, stmt: str) -> pd.DataFrame:
    """
    Fetch each quarter individually for the last 3 years.
    Returns DataFrame: rows=metrics, cols=Timestamps.
    """
    current_year = datetime.now().year
    rows = {}

    for year in range(current_year - 3, current_year + 1):
        for quarter in ["Q1", "Q2", "Q3", "Q4"]:
            raw = _get(
                "/companies/statements/verbose",
                api_key,
                params={
                    "ticker":     ticker,
                    "statements": stmt,
                    "period":     quarter,
                    "fyear":      str(year),
                },
            )
            result = _extract_data(raw)
            if result:
                ts = pd.Timestamp(result["date"])
                rows[ts] = result["data"]

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index = pd.DatetimeIndex(df.index)
    return df.sort_index().T


# ── Name mapping: Simfin labels → yfinance labels used in main.py ────────────

_IS_MAP = {
    "Revenue":                              "Total Revenue",
    "Net Income":                           "Net Income",
    "Net Income (Common)":                  "Net Income",
    "Gross Profit":                         "Gross Profit",
    "Operating Income (Loss)":              "Operating Income",
    "Operating Income":                     "Operating Income",
    "Basic EPS":                            "Basic EPS",
    "Diluted EPS":                          "Diluted EPS",
    "EPS (Diluted)":                        "Diluted EPS",
    "EPS (Basic)":                          "Basic EPS",
    "EBITDA":                               "EBITDA",
    "Interest Expense, Net":                "Interest Expense",
    "Interest Expense":                     "Interest Expense",
    "Income Tax (Expense) Benefit, Net":    "Income Tax Expense",
    "R&D":                                  "Research And Development",
    "Selling, General & Admin":             "Selling General And Administration",
}

_CF_MAP = {
    "Free Cash Flow":                       "Free Cash Flow",
    "Net Cash from Operating Activities":   "Operating Cash Flow",
    "Net Cash from Investing Activities":   "Investing Cash Flow",
    "Net Cash from Financing Activities":   "Financing Cash Flow",
    "Capital Expenditures":                 "Capital Expenditure",
    "Depreciation & Amortization":          "Depreciation And Amortization",
    "Stock-Based Compensation":             "Stock Based Compensation",
    "Dividends Paid":                       "Common Stock Dividend Paid",
}

_BS_MAP = {
    "Total Assets":                              "Total Assets",
    "Total Liabilities":                         "Total Liabilities Net Minority Interest",
    "Total Equity":                              "Stockholders Equity",
    "Cash, Equivalents & Short Term Investments":"Cash And Cash Equivalents",
    "Cash & Equivalents":                        "Cash And Cash Equivalents",
    "Long Term Debt":                            "Long Term Debt",
    "Short Term Debt":                           "Short Term Debt",
    "Total Debt":                                "Total Debt",
    "Shares Outstanding (Common)":               "Ordinary Shares Number",
    "Common Shares Outstanding":                 "Ordinary Shares Number",
    "Total Current Assets":                      "Current Assets",
    "Total Current Liabilities":                 "Current Liabilities",
    "Retained Earnings":                         "Retained Earnings",
    "Deferred Revenue":                          "Current Deferred Revenue",
    "Deferred Revenue (Current)":                "Current Deferred Revenue",
    "Deferred Revenue (Non-Current)":            "Long Term Deferred Revenue",
}


def _remap(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.rename(index={k: v for k, v in mapping.items() if k in df.index})
    keep = list(dict.fromkeys(mapping.values()))
    df = df[df.index.isin(keep)]
    return df[~df.index.duplicated(keep="first")]


# ── Public function ───────────────────────────────────────────────────────────

def fetch_simfin_both_periods(ticker: str, api_key: str) -> dict:
    """
    Fetch 7 years annual + ~3 years quarterly for all three statements.
    Returns the six session_state keys used in main.py.
    NOTE: Makes up to ~40 API calls (free tier allows 2,000/day).
    """
    sym = ticker.upper()

    a_is = _remap(_fetch_annual_all_years(sym, api_key, "pl"),    _IS_MAP)
    a_cf = _remap(_fetch_annual_all_years(sym, api_key, "cf"),    _CF_MAP)
    a_bs = _remap(_fetch_annual_all_years(sym, api_key, "bs"),    _BS_MAP)

    q_is = _remap(_fetch_quarterly_all_years(sym, api_key, "pl"), _IS_MAP)
    q_cf = _remap(_fetch_quarterly_all_years(sym, api_key, "cf"), _CF_MAP)
    q_bs = _remap(_fetch_quarterly_all_years(sym, api_key, "bs"), _BS_MAP)

    return {
        "financials":      a_is,
        "cashflow":        a_cf,
        "balance_sheet":   a_bs,
        "quarterly_fin":   q_is,
        "quarterly_cf":    q_cf,
        "q_balance_sheet": q_bs,
    }


if __name__ == "__main__":
    import sys
    api_key = sys.argv[1] if len(sys.argv) > 1 else input("Simfin API key: ").strip()
    ticker  = sys.argv[2] if len(sys.argv) > 2 else "AAPL"

    print(f"\nFetching {ticker} from Simfin (free tier — looping years)...\n")
    result = fetch_simfin_both_periods(ticker, api_key)

    for name, df in result.items():
        print(f"── {name} ──")
        if df is None or df.empty:
            print("  (empty)\n")
        else:
            print(f"  Metrics : {list(df.index)[:5]}")
            print(f"  Periods : {[str(c.date()) for c in df.columns]}")
            if "Total Revenue" in df.index:
                print(f"  Revenue : {df.loc['Total Revenue'].to_dict()}")
            print()
