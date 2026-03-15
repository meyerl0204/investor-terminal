"""
simfin_fetcher.py  (v2 — corrected v3 API endpoint structure)
--------------------------------------------------------------
Drop-in replacement for the yfinance financial-statement calls in
investor-terminal.  Place this file next to main.py.

Simfin free tier: 7 years of fundamentals, 2 API calls/sec.
Sign up free at https://app.simfin.com → Data API → copy your key.

Quick test (before touching main.py):
    python simfin_fetcher.py YOUR_API_KEY AAPL
"""

import pandas as pd
import requests

# ── v3 endpoint ───────────────────────────────────────────────────────────────
_BASE = "https://backend.simfin.com/api/v3"

# ─────────────────────────────────────────────────────────────────────────────
# Low-level fetch
# ─────────────────────────────────────────────────────────────────────────────

def _get(path: str, api_key: str, params: dict) -> list | dict | None:
    headers = {"Authorization": f"api-key {api_key}",
               "Accept": "application/json"}
    try:
        r = requests.get(f"{_BASE}{path}", headers=headers,
                         params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[simfin_fetcher] request failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Parse the v3 "verbose" response into a wide DataFrame
#
# v3 verbose shape (list, one entry per company):
# [
#   {
#     "ticker": "AAPL",
#     "statements": [
#       {
#         "statement": "pl",
#         "period": "FY",
#         "fyear": 2023,
#         "reportDate": "2023-09-30",
#         "currency": "USD",
#         "data": {
#           "Revenue": 383285000000,
#           "Gross Profit": 169148000000,
#           ...
#         }
#       },
#       ...
#     ]
#   }
# ]
# ─────────────────────────────────────────────────────────────────────────────

def _parse_verbose(raw: list | dict) -> pd.DataFrame:
    """
    Convert v3 verbose response to DataFrame(rows=metrics, cols=Timestamps).
    This matches the yfinance orientation expected by main.py.
    """
    if not raw:
        return pd.DataFrame()

    if isinstance(raw, dict):
        raw = [raw]

    company    = raw[0] if raw else {}
    statements = company.get("statements", [])

    if not statements:
        return pd.DataFrame()

    rows = {}
    for period_block in statements:
        report_date = period_block.get("reportDate") or period_block.get("date")
        if not report_date:
            continue
        ts   = pd.Timestamp(report_date)
        data = period_block.get("data", {})
        if isinstance(data, dict):
            rows[ts] = data

    if not rows:
        return pd.DataFrame()

    # wide: index=date, cols=metrics  →  transpose to yfinance orientation
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index = pd.DatetimeIndex(df.index)
    df = df.sort_index()
    return df.T   # rows=metrics, cols=dates


# ─────────────────────────────────────────────────────────────────────────────
# Column-name mapping  (Simfin label → yfinance label used in main.py)
# ─────────────────────────────────────────────────────────────────────────────

_IS_MAP = {
    "Revenue":                              "Total Revenue",
    "Net Income":                           "Net Income",
    "Net Income (Common)":                  "Net Income",
    "Gross Profit":                         "Gross Profit",
    "Operating Income (Loss)":              "Operating Income",
    "Operating Income":                     "Operating Income",
    "Operating Expenses":                   "Operating Expense",
    "Basic EPS":                            "Basic EPS",
    "Diluted EPS":                          "Diluted EPS",
    "EPS (Diluted)":                        "Diluted EPS",
    "EPS (Basic)":                          "Basic EPS",
    "EBITDA":                               "EBITDA",
    "Interest Expense, Net":                "Interest Expense",
    "Interest Expense":                     "Interest Expense",
    "Income Tax (Expense) Benefit, Net":    "Income Tax Expense",
    "Income Tax":                           "Income Tax Expense",
    "R&D":                                  "Research And Development",
    "Selling, General & Admin":             "Selling General And Administration",
}

_CF_MAP = {
    "Free Cash Flow":                       "Free Cash Flow",
    "Net Cash from Operating Activities":   "Operating Cash Flow",
    "Cash from Operations":                 "Operating Cash Flow",
    "Net Cash from Investing Activities":   "Investing Cash Flow",
    "Net Cash from Financing Activities":   "Financing Cash Flow",
    "Capital Expenditures":                 "Capital Expenditure",
    "Depreciation & Amortization":          "Depreciation And Amortization",
    "Stock-Based Compensation":             "Stock Based Compensation",
    "Dividends Paid":                       "Common Stock Dividend Paid",
    "Change in Working Capital":            "Change In Working Capital",
    "Net Change in Cash":                   "Changes In Cash",
}

_BS_MAP = {
    "Total Assets":                         "Total Assets",
    "Total Liabilities":                    "Total Liabilities Net Minority Interest",
    "Total Equity":                         "Stockholders Equity",
    "Cash, Equivalents & Short Term Investments": "Cash And Cash Equivalents",
    "Cash & Equivalents":                   "Cash And Cash Equivalents",
    "Long Term Debt":                       "Long Term Debt",
    "Short Term Debt":                      "Short Term Debt",
    "Total Debt":                           "Total Debt",
    "Shares Outstanding (Common)":          "Ordinary Shares Number",
    "Common Shares Outstanding":            "Ordinary Shares Number",
    "Total Current Assets":                 "Current Assets",
    "Total Current Liabilities":            "Current Liabilities",
    "Goodwill":                             "Goodwill",
    "Total Intangible Assets":              "Other Intangible Assets",
    "Retained Earnings":                    "Retained Earnings",
    "Deferred Revenue":                     "Current Deferred Revenue",
    "Deferred Revenue (Current)":           "Current Deferred Revenue",
    "Deferred Revenue (Non-Current)":       "Long Term Deferred Revenue",
    "Total Invested Capital":               "Invested Capital",
}


def _remap(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Rename rows present in mapping; drop unmapped rows."""
    if df.empty:
        return df
    rename_map = {k: v for k, v in mapping.items() if k in df.index}
    df = df.rename(index=rename_map)
    keep = list(dict.fromkeys(mapping.values()))
    df   = df[df.index.isin(keep)]
    df   = df[~df.index.duplicated(keep="first")]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_statement(ticker: str, api_key: str,
                     stmt: str, period: str) -> pd.DataFrame:
    """
    stmt   : "pl" | "cf" | "bs"
    period : "FY" for annual, "Q1,Q2,Q3,Q4" for quarterly
    """
    raw = _get(
        "/companies/statements/verbose",
        api_key,
        params={
            "ticker":     ticker.upper(),
            "statements": stmt,
            "period":     period,
        },
    )
    return _parse_verbose(raw)


def fetch_simfin_both_periods(ticker: str, api_key: str) -> dict:
    """
    Fetch annual + quarterly for income statement, cash flow, balance sheet.

    Returns a dict with the six session_state keys used in main.py:
        financials, cashflow, balance_sheet,
        quarterly_fin, quarterly_cf, q_balance_sheet
    """
    sym = ticker.upper()

    # Annual
    a_is = _remap(_fetch_statement(sym, api_key, "pl", "FY"),         _IS_MAP)
    a_cf = _remap(_fetch_statement(sym, api_key, "cf", "FY"),         _CF_MAP)
    a_bs = _remap(_fetch_statement(sym, api_key, "bs", "FY"),         _BS_MAP)

    # Quarterly
    q_is = _remap(_fetch_statement(sym, api_key, "pl", "Q1,Q2,Q3,Q4"), _IS_MAP)
    q_cf = _remap(_fetch_statement(sym, api_key, "cf", "Q1,Q2,Q3,Q4"), _CF_MAP)
    q_bs = _remap(_fetch_statement(sym, api_key, "bs", "Q1,Q2,Q3,Q4"), _BS_MAP)

    return {
        "financials":      a_is,
        "cashflow":        a_cf,
        "balance_sheet":   a_bs,
        "quarterly_fin":   q_is,
        "quarterly_cf":    q_cf,
        "q_balance_sheet": q_bs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ── HOW TO WIRE THIS INTO main.py ────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. Add to imports at the top of main.py:
#
#       from simfin_fetcher import fetch_simfin_both_periods
#
# 2. Add Simfin key input in the sidebar (near the Groq key input):
#
#       simfin_api_key = st.sidebar.text_input(
#           "Simfin API Key", type="password",
#           help="Free at app.simfin.com — gives 7 years of history"
#       )
#
# 3. Inside the "Generate Deep Analysis" button block (~line 888),
#    REPLACE the six yfinance lines:
#
#       # DELETE these six lines:
#       st.session_state["financials"]      = stock.financials
#       st.session_state["quarterly_fin"]   = stock.quarterly_financials
#       st.session_state["cashflow"]        = stock.cashflow
#       st.session_state["quarterly_cf"]    = stock.quarterly_cashflow
#       st.session_state["balance_sheet"]   = stock.balance_sheet
#       st.session_state["q_balance_sheet"] = stock.quarterly_balance_sheet
#
#       # ADD this instead:
#       if simfin_api_key:
#           with st.spinner("Fetching extended history from Simfin..."):
#               sf_data = fetch_simfin_both_periods(ticker_input, simfin_api_key)
#           for k, v in sf_data.items():
#               st.session_state[k] = v
#       else:
#           st.session_state["financials"]      = stock.financials
#           st.session_state["quarterly_fin"]   = stock.quarterly_financials
#           st.session_state["cashflow"]        = stock.cashflow
#           st.session_state["quarterly_cf"]    = stock.quarterly_cashflow
#           st.session_state["balance_sheet"]   = stock.balance_sheet
#           st.session_state["q_balance_sheet"] = stock.quarterly_balance_sheet
#
# 4. No new packages needed — `requests` is already a yfinance dependency.
#
# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST — run this first to verify your key and see real data shapes
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    api_key = sys.argv[1] if len(sys.argv) > 1 else input("Simfin API key: ").strip()
    ticker  = sys.argv[2] if len(sys.argv) > 2 else "AAPL"

    print(f"\nTesting Simfin v3 fetch for {ticker}...\n")
    result = fetch_simfin_both_periods(ticker, api_key)

    for name, df in result.items():
        print(f"── {name} ──")
        if df is None or df.empty:
            print("  (empty — check API key or ticker)\n")
        else:
            print(f"  Metrics : {list(df.index)[:6]}")
            print(f"  Periods : {[str(c.date()) for c in df.columns[:6]]}")
            print(f"  Shape   : {df.shape}")
            if "Total Revenue" in df.index:
                rev = df.loc["Total Revenue"]
                print(f"  Revenue : { {str(k.date()): v for k, v in rev.items()} }")
            print()
