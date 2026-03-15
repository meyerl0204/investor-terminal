"""
simfin_fetcher.py
-----------------
Drop-in replacement for the yfinance financial-statement calls used in
investor-terminal.  Paste this file next to main.py, then swap the
data-fetch block in main.py as shown at the bottom of this file.

Simfin free tier gives you 7 years of fundamentals history — already
a meaningful improvement over yfinance's ~4-year window.

Setup
-----
1.  pip install simfin pandas
2.  Register at https://app.simfin.com and copy your free API key.
3.  Add the key to your Streamlit secrets or the sidebar input shown below.
"""

import pandas as pd
import requests
from datetime import datetime

# ── Simfin REST API base ──────────────────────────────────────────────────────
_BASE = "https://backend.simfin.com/api/v3"


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get(endpoint: str, api_key: str, params: dict = None) -> dict | list | None:
    """Fire a GET request; return parsed JSON or None on failure."""
    headers = {"Authorization": f"api-key {api_key}"}
    try:
        r = requests.get(f"{_BASE}{endpoint}", headers=headers,
                         params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _statements_to_df(data: list, date_col: str = "reportDate") -> pd.DataFrame:
    """
    Convert a list of statement dicts from Simfin into a wide DataFrame
    indexed by report date (as Timestamp), columns = line-item names.
    """
    if not data:
        return pd.DataFrame()
    rows = {}
    for period in data:
        raw_date = period.get(date_col) or period.get("date")
        if not raw_date:
            continue
        ts = pd.Timestamp(raw_date)
        row = {}
        for item in period.get("data", []):
            name = item.get("concept") or item.get("name", "")
            val  = item.get("value")
            if name:
                row[name] = val
        rows[ts] = row
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index = pd.DatetimeIndex(df.index)
    df = df.sort_index()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Name-mapping helpers  (Simfin concept → yfinance row label)
# ─────────────────────────────────────────────────────────────────────────────

# Income statement
_IS_MAP = {
    "Revenue":                    "Total Revenue",
    "Net Income":                 "Net Income",
    "Net Income (Common)":        "Net Income",
    "Gross Profit":               "Gross Profit",
    "Operating Income (Loss)":    "Operating Income",
    "Operating Income":           "Operating Income",
    "Basic EPS":                  "Basic EPS",
    "Diluted EPS":                "Diluted EPS",
    "EPS (Diluted)":              "Diluted EPS",
    "EPS (Basic)":                "Basic EPS",
    "EBITDA":                     "EBITDA",
    "Interest Expense":           "Interest Expense",
    "Income Tax":                 "Income Tax Expense",
}

# Cash-flow statement
_CF_MAP = {
    "Free Cash Flow":             "Free Cash Flow",
    "Net Cash from Operations":   "Operating Cash Flow",
    "Cash from Operations":       "Operating Cash Flow",
    "Capital Expenditures":       "Capital Expenditure",
    "Net Cash from Investing":    "Investing Cash Flow",
    "Net Cash from Financing":    "Financing Cash Flow",
    "Depreciation & Amortization":"Depreciation And Amortization",
    "Stock-Based Compensation":   "Stock Based Compensation",
    "Dividends Paid":             "Common Stock Dividend Paid",
    "Change in Working Capital":  "Change In Working Capital",
}

# Balance sheet
_BS_MAP = {
    "Total Assets":                    "Total Assets",
    "Total Liabilities":               "Total Liabilities Net Minority Interest",
    "Total Equity":                    "Stockholders Equity",
    "Cash & Equivalents":              "Cash And Cash Equivalents",
    "Cash, Equivalents & Short Term Investments": "Cash And Cash Equivalents",
    "Long Term Debt":                  "Long Term Debt",
    "Short Term Debt":                 "Short Term Debt",
    "Total Debt":                      "Total Debt",
    "Shares Outstanding (Common)":     "Ordinary Shares Number",
    "Common Shares Outstanding":       "Ordinary Shares Number",
    "Shares Outstanding":              "Ordinary Shares Number",
    "Total Current Assets":            "Current Assets",
    "Total Current Liabilities":       "Current Liabilities",
    "Goodwill":                        "Goodwill",
    "Total Intangible Assets":         "Other Intangible Assets",
    "Retained Earnings":               "Retained Earnings",
    "Deferred Revenue":                "Current Deferred Revenue",
    "Deferred Revenue (Current)":      "Current Deferred Revenue",
    "Deferred Revenue (Non-Current)":  "Long Term Deferred Revenue",
}


def _remap(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Transpose so rows = metrics, columns = dates  (yfinance convention),
    then rename rows according to the mapping dict.
    Keeps only rows that have a mapping entry.
    """
    if df.empty:
        return df
    df = df.T  # metrics → rows, dates → columns
    rename_map = {k: v for k, v in mapping.items() if k in df.index}
    df = df.rename(index=rename_map)
    # Deduplicate: if two source rows map to the same target, keep first non-NaN
    df = df[~df.index.duplicated(keep="first")]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Public API  — mimics yfinance Ticker attributes
# ─────────────────────────────────────────────────────────────────────────────

def fetch_simfin_financials(
    ticker: str,
    api_key: str,
    period: str = "annual",   # "annual" or "quarterly"
) -> dict:
    """
    Returns a dict with keys matching yfinance Ticker attributes:
        financials, quarterly_financials,
        cashflow,    quarterly_cashflow,
        balance_sheet, quarterly_balance_sheet

    Each value is a pd.DataFrame in yfinance orientation:
        rows = metric names, columns = period-end Timestamps
    """
    variant = "annual" if period == "annual" else "quarterly"
    sym = ticker.upper()

    def _fetch_stmt(stmt: str) -> pd.DataFrame:
        """Fetch one statement type; returns empty DF on failure."""
        data = _get(
            f"/companies/statements/compact",
            api_key,
            params={"ticker": sym, "statements": stmt,
                    "period": variant, "fyear": ""},
        )
        # v3 compact response shape: list of period dicts
        if not data:
            return pd.DataFrame()
        # Sometimes wrapped in {"data": [...]}
        if isinstance(data, dict):
            data = data.get("data", [])
        return _statements_to_df(data)

    is_df  = _fetch_stmt("pl")   # income / profit & loss
    cf_df  = _fetch_stmt("cf")   # cash flow
    bs_df  = _fetch_stmt("bs")   # balance sheet

    return {
        "financials":    _remap(is_df, _IS_MAP),
        "cashflow":      _remap(cf_df, _CF_MAP),
        "balance_sheet": _remap(bs_df, _BS_MAP),
    }


def fetch_simfin_both_periods(ticker: str, api_key: str) -> dict:
    """
    Fetch annual AND quarterly in one call bundle.
    Returns dict with all six keys used by main.py session state.
    """
    annual    = fetch_simfin_financials(ticker, api_key, "annual")
    quarterly = fetch_simfin_financials(ticker, api_key, "quarterly")

    return {
        "financials":         annual["financials"],
        "cashflow":           annual["cashflow"],
        "balance_sheet":      annual["balance_sheet"],
        "quarterly_fin":      quarterly["financials"],
        "quarterly_cf":       quarterly["cashflow"],
        "q_balance_sheet":    quarterly["balance_sheet"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# ── HOW TO WIRE THIS INTO main.py ────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
#
# 1.  Add to your imports at the top of main.py:
#
#       from simfin_fetcher import fetch_simfin_both_periods
#
# 2.  Add a sidebar input for the Simfin key (near your Groq key input):
#
#       simfin_api_key = st.sidebar.text_input(
#           "Simfin API Key", type="password",
#           help="Free key at app.simfin.com — unlocks 7 years of financials"
#       )
#
# 3.  Inside the "Generate Deep Analysis" button block, REPLACE lines 892-897:
#
#       # OLD (yfinance) — delete these:
#       st.session_state["financials"]      = stock.financials
#       st.session_state["quarterly_fin"]   = stock.quarterly_financials
#       st.session_state["cashflow"]        = stock.cashflow
#       st.session_state["quarterly_cf"]    = stock.quarterly_cashflow
#       st.session_state["balance_sheet"]   = stock.balance_sheet
#       st.session_state["q_balance_sheet"] = stock.quarterly_balance_sheet
#
#       # NEW — add this instead:
#       if simfin_api_key:
#           sf_data = fetch_simfin_both_periods(ticker_input, simfin_api_key)
#           for k, v in sf_data.items():
#               st.session_state[k] = v
#       else:
#           # Fallback to yfinance if no Simfin key entered
#           st.session_state["financials"]      = stock.financials
#           st.session_state["quarterly_fin"]   = stock.quarterly_financials
#           st.session_state["cashflow"]        = stock.cashflow
#           st.session_state["quarterly_cf"]    = stock.quarterly_cashflow
#           st.session_state["balance_sheet"]   = stock.balance_sheet
#           st.session_state["q_balance_sheet"] = stock.quarterly_balance_sheet
#
#   That's it — all chart/KPI code below reads from session_state
#   unchanged, so nothing else needs to be touched.
#
# 4.  Add to requirements.txt (or packages.txt on Streamlit Cloud):
#       simfin
#       requests   ← already present via yfinance deps, but list it anyway
#
# ─────────────────────────────────────────────────────────────────────────────
# TESTING (run standalone to verify your key works before integrating)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    api_key = sys.argv[1] if len(sys.argv) > 1 else input("Enter your Simfin API key: ").strip()
    ticker  = sys.argv[2] if len(sys.argv) > 2 else "AAPL"

    print(f"\nFetching {ticker} from Simfin...\n")
    result = fetch_simfin_both_periods(ticker, api_key)

    for name, df in result.items():
        print(f"── {name} ──")
        if df is None or df.empty:
            print("  (empty)\n")
        else:
            print(f"  rows={list(df.index[:6])}")
            print(f"  cols={list(df.columns[:6])}")
            print(f"  shape={df.shape}\n")
