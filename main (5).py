import yfinance as yf
import streamlit as st
import pandas as pd
import altair as alt
import io
from groq import Groq

st.set_page_config(page_title="Pro Research Terminal", layout="wide")
st.title("🏛️ Institutional Research Terminal")

# ── Market Ticker Bar (static, always visible) ───────────────────────────────
@st.cache_data(ttl=300)  # refresh every 5 minutes
def get_market_indices():
    indices = {
        "S&P 500":    "^GSPC",
        "Nasdaq":     "^IXIC",
        "Dow Jones":  "^DJI",
        "Russell 2000": "^RUT",
    }
    results = {}
    for name, sym in indices.items():
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            price = info.last_price
            prev  = info.previous_close
            if price and prev:
                chg     = price - prev
                chg_pct = (chg / prev) * 100
                results[name] = {"price": price, "chg": chg, "pct": chg_pct}
        except:
            results[name] = None
    return results

@st.cache_data(ttl=300)  # refresh every 5 minutes
def get_fear_greed():
    import urllib.request, json as _json

    # Try CNN endpoint with browser-like headers
    urls_and_parsers = [
        (
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            lambda d: (float(d["fear_and_greed"]["score"]),
                       d["fear_and_greed"]["rating"].replace("_", " ").title())
        ),
        (
            "https://fear-and-greed-index.p.rapidapi.com/v1/fgi",
            None  # handled separately below
        ),
    ]

    headers_cnn = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.cnn.com/markets/fear-and-greed",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.cnn.com",
    }

    try:
        req = urllib.request.Request(urls_and_parsers[0][0], headers=headers_cnn)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = _json.loads(resp.read())
        score, rating = urls_and_parsers[0][1](data)
        return {"score": score, "rating": rating}
    except:
        pass

    # Fallback: derive a proxy score from VIX + S&P 500 momentum
    try:
        import yfinance as _yf
        vix = _yf.Ticker("^VIX").fast_info.last_price or 20
        spx = _yf.Ticker("^GSPC")
        hist = spx.history(period="1mo")["Close"]
        if len(hist) >= 2:
            momentum = (hist.iloc[-1] / hist.iloc[0] - 1) * 100
        else:
            momentum = 0
        # VIX >30 = fear zone, <15 = greed zone; blend with momentum
        vix_score = max(0, min(100, 100 - (vix - 10) * 2.5))
        mom_score = max(0, min(100, 50 + momentum * 5))
        score = round(vix_score * 0.6 + mom_score * 0.4, 1)
        if score >= 75: rating = "Extreme Greed"
        elif score >= 55: rating = "Greed"
        elif score >= 45: rating = "Neutral"
        elif score >= 25: rating = "Fear"
        else: rating = "Extreme Fear"
        return {"score": score, "rating": f"{rating}*", "proxy": True}
    except:
        return None

_indices = get_market_indices()
_fg = get_fear_greed()

_cols = st.columns(5)
_labels = ["S&P 500", "Nasdaq", "Dow Jones", "Russell 2000"]
for i, name in enumerate(_labels):
    d = _indices.get(name)
    with _cols[i]:
        if d:
            color  = "#2ecc71" if d["pct"] >= 0 else "#e74c3c"
            arrow  = "▲" if d["pct"] >= 0 else "▼"
            price_fmt = f"{d['price']:,.2f}"
            pct_fmt   = f"{arrow} {abs(d['pct']):.2f}%"
            st.markdown(
                f"""<div style="background:#f8f9fa;border-radius:10px;padding:10px 16px;
                border-left:4px solid {color};text-align:left;">
                <div style="font-size:11px;color:#999;text-transform:uppercase;
                letter-spacing:.6px;margin-bottom:2px;">{name}</div>
                <div style="font-size:20px;font-weight:700;color:#1a1a2e;">{price_fmt}</div>
                <div style="font-size:13px;font-weight:600;color:{color};">{pct_fmt}</div>
                </div>""",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"""<div style="background:#f8f9fa;border-radius:10px;padding:10px 16px;
                border-left:4px solid #ccc;">
                <div style="font-size:11px;color:#999;text-transform:uppercase;">{name}</div>
                <div style="font-size:16px;color:#aaa;">—</div></div>""",
                unsafe_allow_html=True
            )

# ── Fear & Greed Card ──
with _cols[4]:
    if _fg:
        score = _fg["score"]
        rating = _fg["rating"]
        if score >= 75:
            fg_color = "#00c853"   # bright green - Extreme Greed
        elif score >= 55:
            fg_color = "#a8d08d"   # light green - Greed
        elif score >= 45:
            fg_color = "#f1c40f"   # yellow - Neutral
        elif score >= 25:
            fg_color = "#e67e22"   # dark orange - Fear
        else:
            fg_color = "#e74c3c"   # red - Extreme Fear
        st.markdown(
            f"""<div style="background:#f8f9fa;border-radius:10px;padding:10px 16px;
            border-left:4px solid {fg_color};text-align:left;">
            <div style="font-size:11px;color:#999;text-transform:uppercase;
            letter-spacing:.6px;margin-bottom:2px;">Fear & Greed</div>
            <div style="font-size:20px;font-weight:700;color:#1a1a2e;">{score:.0f} / 100</div>
            <div style="font-size:13px;font-weight:600;color:{fg_color};">{rating}</div>
            </div>""",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """<div style="background:#f8f9fa;border-radius:10px;padding:10px 16px;
            border-left:4px solid #ccc;">
            <div style="font-size:11px;color:#999;text-transform:uppercase;">Fear & Greed</div>
            <div style="font-size:16px;color:#aaa;">—</div></div>""",
            unsafe_allow_html=True
        )

st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)
st.divider()

# ── Top-level navigation tabs ────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📈 Stock Analysis", "🏦 Insider Buys"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — INSIDER BUYS
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    import urllib.request as _req
    import re as _re

    st.markdown("## 🏦 Recent Insider Purchases")
    st.caption("Open-market purchase filings (Form 4, transaction code P) via OpenInsider. Filtered to $2B+ market cap companies and $50K+ purchases. Refreshed hourly.")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _parse_money(s):
        """Convert '$1,234,567' or '$1.23M' style strings to float."""
        if not s or s.strip() in ("", "—", "N/A"):
            return None
        s = s.strip().replace("$", "").replace(",", "")
        try:
            if s.endswith("M"):
                return float(s[:-1]) * 1e6
            if s.endswith("B"):
                return float(s[:-1]) * 1e9
            return float(s)
        except ValueError:
            return None

    def _fmt_val(v):
        if v is None or (isinstance(v, float) and (pd.isna(v) or v == 0)):
            return "N/A"
        if v >= 1e9: return f"${v/1e9:.2f}B"
        if v >= 1e6: return f"${v/1e6:.2f}M"
        if v >= 1e3: return f"${v/1e3:.1f}K"
        return f"${v:,.0f}"

    def _fmt_mktcap(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "N/A"
        if v >= 1e12: return f"${v/1e12:.2f}T"
        if v >= 1e9:  return f"${v/1e9:.1f}B"
        if v >= 1e6:  return f"${v/1e6:.1f}M"
        return f"${v:,.0f}"

    @st.cache_data(ttl=3600)
    def fetch_openinsider():
        """
        Scrape OpenInsider using Python's html.parser — handles nested quotes in
        onmouseover attributes that break regex-based approaches.
        """
        from html.parser import HTMLParser

        url = (
            "http://openinsider.com/screener?"
            "s=&o=&pl=&ph=&ll=&lh=&fd=30&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1"
            "&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
            "&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h="
            "&sortcol=0&cnt=200&page=1"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html",
        }
        try:
            req = _req.Request(url, headers=headers)
            with _req.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            return pd.DataFrame(), str(e)

        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_target_table = False
                self.in_td = False
                self.in_skip = False   # script/style
                self.skip_depth = 0
                self.rows = []
                self.current_row = None
                self.current_cell = []
                self.table_depth = 0

            def handle_starttag(self, tag, attrs):
                attr_dict = dict(attrs)
                if tag in ("script", "style"):
                    self.in_skip = True
                    self.skip_depth += 1
                    return
                if self.in_skip:
                    return
                if tag == "table":
                    classes = attr_dict.get("class", "")
                    if "tinytable" in classes:
                        self.in_target_table = True
                    if self.in_target_table:
                        self.table_depth += 1
                if not self.in_target_table:
                    return
                if tag == "tr":
                    self.current_row = []
                elif tag in ("td", "th"):
                    self.in_td = True
                    self.current_cell = []

            def handle_endtag(self, tag):
                if tag in ("script", "style"):
                    self.skip_depth -= 1
                    if self.skip_depth <= 0:
                        self.in_skip = False
                        self.skip_depth = 0
                    return
                if self.in_skip:
                    return
                if tag == "table" and self.in_target_table:
                    self.table_depth -= 1
                    if self.table_depth <= 0:
                        self.in_target_table = False
                if not self.in_target_table:
                    return
                if tag in ("td", "th") and self.in_td:
                    self.current_row.append("".join(self.current_cell).strip())
                    self.in_td = False
                    self.current_cell = []
                elif tag == "tr" and self.current_row is not None:
                    if any(c.strip() for c in self.current_row):
                        self.rows.append(self.current_row)
                    self.current_row = None

            def handle_data(self, data):
                if self.in_skip:
                    return
                if self.in_target_table and self.in_td:
                    self.current_cell.append(data)

            def handle_entityref(self, name):
                from html import unescape
                if self.in_target_table and self.in_td:
                    self.current_cell.append(unescape(f"&{name};"))

            def handle_charref(self, name):
                from html import unescape
                if self.in_target_table and self.in_td:
                    self.current_cell.append(unescape(f"&#{name};"))

        parser = TableParser()
        parser.feed(html)

        if not parser.rows:
            return pd.DataFrame(), "no_rows_parsed"

        # Map columns from header row
        col_map = {}
        header_row = None
        for row in parser.rows:
            joined = " ".join(row).lower()
            if "ticker" in joined and ("value" in joined or "qty" in joined):
                header_row = row
                break

        if header_row is None:
            return pd.DataFrame(), "header_not_found"

        for i, h in enumerate(header_row):
            hl = h.lower().strip()
            if "filing" in hl and "date" in hl:   col_map["filing_date"] = i
            elif "trade" in hl and "date" in hl:  col_map["trade_date"]  = i
            elif hl == "ticker":                   col_map["ticker"]      = i
            elif "company" in hl:                  col_map["company"]     = i
            elif "insider" in hl or hl == "name":  col_map["insider"]     = i
            elif "title" in hl:                    col_map["title"]       = i
            elif "price" in hl:                    col_map["price"]       = i
            elif "qty" in hl:                      col_map["qty"]         = i
            elif hl == "value":                    col_map["value"]       = i

        def get_cell(row, key, default=""):
            idx = col_map.get(key)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip()

        records = []
        past_header = False
        for row in parser.rows:
            if row == header_row:
                past_header = True
                continue
            if not past_header or len(row) < 5:
                continue

            ticker  = get_cell(row, "ticker").upper().strip()
            company = get_cell(row, "company")
            insider = get_cell(row, "insider")
            title   = get_cell(row, "title")
            price_s = get_cell(row, "price")
            qty_s   = get_cell(row, "qty")
            value_s = get_cell(row, "value")
            t_date  = get_cell(row, "trade_date") or get_cell(row, "filing_date")

            # Skip non-ticker rows or header repeats
            if not ticker or len(ticker) > 6 or not ticker.isalpha():
                continue

            try:
                price = float(price_s.replace("$","").replace(",","")) if price_s else None
            except ValueError:
                price = None
            try:
                qty = int(qty_s.replace(",","").replace("+","")) if qty_s else None
            except ValueError:
                qty = None

            value = _parse_money(value_s)
            if value is None and price and qty:
                value = price * qty

            try:
                trade_date = pd.to_datetime(t_date).date()
            except Exception:
                trade_date = None

            records.append({
                "Ticker":     ticker,
                "Company":    company or ticker,
                "Insider":    insider or "—",
                "Title":      title or "—",
                "Date":       trade_date,
                "Price":      price,
                "Shares":     qty,
                "Value ($)":  value,
                "Market Cap": None,
            })

        if not records:
            return pd.DataFrame(), "no_records_parsed"

        df = pd.DataFrame(records)

        # Drop noise trades under $50K
        df = df[df["Value ($)"].notna() & (df["Value ($)"] >= 50_000)]
        df = df.drop_duplicates(subset=["Ticker","Insider","Date","Shares"])
        df = df.sort_values("Date", ascending=False).reset_index(drop=True)

        # Fetch market caps for all unique tickers, then filter to $2B+ only
        unique_tickers = df["Ticker"].unique()
        mktcap_map = {}
        for sym in unique_tickers:
            try:
                mktcap_map[sym] = yf.Ticker(sym).fast_info.market_cap
            except Exception:
                mktcap_map[sym] = None

        df["Market Cap"] = df["Ticker"].map(mktcap_map)

        # Keep only companies with market cap >= $2B
        df = df[df["Market Cap"].notna() & (df["Market Cap"] >= 2_000_000_000)]
        df = df.sort_values("Date", ascending=False).reset_index(drop=True)

        return df, "ok"

    with st.spinner("Fetching insider purchases from OpenInsider..."):
        insider_df, fetch_status = fetch_openinsider()

    if insider_df.empty:
        st.error(
            f"Could not load insider data (status: `{fetch_status}`). "
            "OpenInsider may be temporarily unavailable. "
            "You can view the data directly at [openinsider.com](http://openinsider.com)."
        )
    else:
        # ── Sort & filter controls ─────────────────────────────────────────
        st.markdown("### 🔽 Sort & Filter")
        sfc1, sfc2, sfc3 = st.columns([2, 2, 2])
        with sfc1:
            sort_by = st.selectbox(
                "Sort by",
                ["Date (newest first)", "Ticker A → Z", "Dollar Amount (largest first)", "Market Cap (largest first)"],
                index=0, key="insider_sort"
            )
        with sfc2:
            min_val = st.number_input(
                "Min purchase value ($)", min_value=50000, value=50000, step=25000,
                help="Minimum transaction size shown", key="insider_minval"
            )
        with sfc3:
            search_ticker = st.text_input("Filter by ticker", "", key="insider_ticker").upper().strip()

        display_df = insider_df.copy()
        if search_ticker:
            display_df = display_df[display_df["Ticker"] == search_ticker]
        if min_val > 0:
            display_df = display_df[display_df["Value ($)"].fillna(0) >= min_val]

        if sort_by == "Ticker A → Z":
            display_df = display_df.sort_values("Ticker", ascending=True)
        elif sort_by == "Dollar Amount (largest first)":
            display_df = display_df.sort_values("Value ($)", ascending=False, na_position="last")
        elif sort_by == "Market Cap (largest first)":
            display_df = display_df.sort_values("Market Cap", ascending=False, na_position="last")
        else:
            display_df = display_df.sort_values("Date", ascending=False)

        display_df = display_df.reset_index(drop=True)

        # ── Summary bar ────────────────────────────────────────────────────
        total_value = display_df["Value ($)"].sum()
        sm1, sm2, sm3 = st.columns(3)
        for _col, _label, _val in [
            (sm1, "Total $ Purchased",  _fmt_val(total_value) if total_value > 0 else "N/A"),
            (sm2, "Purchase Events",    str(len(display_df))),
            (sm3, "Companies",          str(display_df["Ticker"].nunique())),
        ]:
            with _col:
                st.markdown(
                    f"""<div style="background:#f8f9fa;border-radius:10px;padding:12px 18px;
                    border-left:4px solid #2ecc71;margin-bottom:12px;">
                    <div style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.6px;">{_label}</div>
                    <div style="font-size:22px;font-weight:700;color:#1a1a2e;">{_val}</div>
                    </div>""",
                    unsafe_allow_html=True
                )

        st.markdown("<br>", unsafe_allow_html=True)

        if display_df.empty:
            st.info("No results match your filters.")
        else:
            # ── Card grid ──────────────────────────────────────────────────
            CARDS_PER_ROW = 3
            chunks = [display_df.iloc[i:i+CARDS_PER_ROW] for i in range(0, len(display_df), CARDS_PER_ROW)]

            for chunk in chunks:
                cols = st.columns(CARDS_PER_ROW)
                for idx, (_, r) in enumerate(chunk.iterrows()):
                    date_str    = str(r["Date"])    if r["Date"]    else "—"
                    val_str     = _fmt_val(r["Value ($)"])
                    mktcap_str  = _fmt_mktcap(r["Market Cap"])
                    price_str   = f"${r['Price']:,.2f}" if r.get("Price") else "—"
                    shares_str  = f"{int(r['Shares']):,}" if r.get("Shares") else "—"
                    insider_str = str(r["Insider"])[:30] + ("…" if len(str(r["Insider"])) > 30 else "")
                    title_str   = str(r["Title"])[:32]   + ("…" if len(str(r["Title"]))   > 32 else "")
                    co_str      = str(r["Company"])[:36] + ("…" if len(str(r["Company"])) > 36 else "")

                    with cols[idx]:
                        st.markdown(
                            f"""<div style="background:#ffffff;border:1px solid #e8ecef;border-radius:12px;
                            padding:16px 18px;margin-bottom:14px;box-shadow:0 2px 8px rgba(0,0,0,0.05);
                            border-top:3px solid #2ecc71;">
                              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                                <span style="font-size:18px;font-weight:800;color:#1a1a2e;">{r['Ticker']}</span>
                                <span style="font-size:11px;background:#eafaf1;color:#1a9e5c;border-radius:6px;
                                padding:3px 8px;font-weight:600;">{date_str}</span>
                              </div>
                              <div style="font-size:12px;color:#666;margin-bottom:8px;">{co_str}</div>
                              <div style="font-size:24px;font-weight:700;color:#2ecc71;margin-bottom:2px;">{val_str}</div>
                              <div style="font-size:12px;color:#888;margin-bottom:8px;">{shares_str} shares @ {price_str}</div>
                              <hr style="border:none;border-top:1px solid #f0f0f0;margin:8px 0;">
                              <div style="font-size:12px;color:#444;font-weight:600;">{insider_str}</div>
                              <div style="font-size:11px;color:#999;">{title_str}</div>
                              <div style="font-size:11px;color:#aaa;margin-top:6px;">Mkt Cap: {mktcap_str}</div>
                            </div>""",
                            unsafe_allow_html=True
                        )



# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — STOCK ANALYSIS (existing content)
# ════════════════════════════════════════════════════════════════════════════
with tab1:

    CSV_DATA = """Year,Max Drawdown %,Bottom-to-Year-End Return % (from max drawdown low),Full-Year Return %
    1975,-14.1,48.2,37.2
    1976,-7.9,26.7,23.8
    1977,-19.4,10.2,-7.2
    1978,-19.4,23.6,6.6
    1979,-10.2,25.5,18.4
    1980,-17.1,38.5,32.4
    1981,-25.0,15.4,-4.9
    1982,-27.1,58.3,21.4
    1983,-14.1,25.2,22.5
    1984,-14.4,20.4,6.3
    1985,-8.2,35.3,32.2
    1986,-9.9,28.6,18.5
    1987,-36.1,23.2,5.2
    1988,-11.3,20.5,16.8
    1989,-8.5,32.1,31.5
    1990,-19.9,13.9,-3.1
    1991,-6.8,38.9,30.5
    1992,-5.3,13.7,7.7
    1993,-8.9,15.4,9.9
    1994,-8.9,8.2,1.3
    1995,-3.1,34.4,37.6
    1996,-9.6,26.4,23.0
    1997,-10.8,33.9,33.4
    1998,-19.3,28.6,28.6
    1999,-12.1,29.0,21.0
    2000,-17.1,5.8,-9.1
    2001,-29.7,21.4,-11.9
    2002,-47.4,22.7,-22.1
    2003,-14.1,39.2,28.7
    2004,-8.2,14.6,10.9
    2005,-7.2,12.3,4.9
    2006,-7.7,19.7,15.8
    2007,-10.1,10.7,5.5
    2008,-56.8,24.2,-37.0
    2009,-27.6,64.8,26.5
    2010,-16.0,28.3,15.1
    2011,-19.4,14.9,2.1
    2012,-9.9,18.6,16.0
    2013,-5.8,32.4,32.4
    2014,-7.4,15.3,13.7
    2015,-12.4,11.7,1.4
    2016,-10.5,22.2,12.0
    2017,-2.8,21.8,21.8
    2018,-19.8,9.8,-4.4
    2019,-6.8,39.1,31.5
    2020,-33.9,68.0,18.4
    2021,-5.2,28.7,28.7
    2022,-25.4,14.0,-18.1
    2023,-10.3,26.2,26.3
    2024,-8.5,23.1,23.3
    2025,-10.2,0.0,0.0"""

    try:
        spx_df = pd.read_csv(io.StringIO(CSV_DATA))
        spx_df['Year'] = spx_df['Year'].astype(int)
        election_years = [year for year in range(1976, 2028, 4)]
        spx_df['Year_Type'] = spx_df['Year'].apply(lambda x: 'Election Year' if x in election_years else 'Standard Year')
        st.sidebar.success("✅ Database Connected")
    except Exception as e:
        st.sidebar.error(f"❌ Data Error: {e}")

    st.sidebar.divider()
    st.sidebar.header("🤖 AI News Summaries")
    groq_api_key = st.sidebar.text_input("Groq API Key", type="password",
        help="Get a free key at console.groq.com")

    # ── Session state defaults ──────────────────────────────────────────────────
    for key, val in [("analysis_done", False), ("price_range", "1Y"),
                     ("ticker_loaded", ""), ("stock_info", {}),
                     ("hist_full", None), ("financials", None),
                     ("quarterly_fin", None), ("cashflow", None),
                     ("quarterly_cf", None), ("recommendations", None),
                     ("news_list", [])]:
        if key not in st.session_state:
            st.session_state[key] = val

    def extract_news_fields(item):
        if 'content' in item:
            c = item['content']
            headline = c.get('title', '')
            publisher = c.get('provider', {}).get('displayName', '') if isinstance(c.get('provider'), dict) else c.get('provider', '')
            link = c.get('canonicalUrl', {}).get('url', '') or c.get('clickThroughUrl', {}).get('url', '')
        else:
            headline = item.get('title', '')
            publisher = item.get('publisher', '')
            link = item.get('link', '')
        return headline or 'No title', publisher or 'Unknown', link or '#'

    def get_ai_summary(ticker, headline, publisher, api_key):
        try:
            client = Groq(api_key=api_key)
            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": """You are a senior Wall Street analyst. Provide deep-dive analysis for institutional investors covering:
    1. What happened and why it matters
    2. Short-term price impact (bullish/bearish/neutral)
    3. Long-term implications
    4. Key risks or opportunities
    5. What to watch next
    Write in paragraphs, 150-200 words, professional tone."""},
                    {"role": "user", "content": f"Ticker: {ticker}\nPublisher: {publisher}\nHeadline: {headline}\n\nProvide institutional-grade analysis."}
                ], max_tokens=400, temperature=0.3)
            return r.choices[0].message.content
        except Exception as e:
            return f"⚠️ {str(e)}"

    def bar_chart(data, y_label, color, format_billions=True, quarterly=False):
        if data is None or data.empty:
            return None, []
        data = data.reset_index()
        data.columns = ['Date', 'Value']
        if quarterly:
            data['Date'] = pd.to_datetime(data['Date']).dt.to_period('Q').astype(str)
        else:
            data['Date'] = pd.to_datetime(data['Date']).dt.year.astype(str)

        # Drop NaN/inf values
        data = data.replace([float('inf'), float('-inf')], pd.NA).dropna(subset=['Value'])
        if data.empty:
            return None, []

        if format_billions:
            max_abs = data['Value'].abs().max()
            if max_abs >= 1e9:
                data['Value'] = data['Value'] / 1e9
                label = f"{y_label} (B$)"
                tooltip_prefix = "$"
                tooltip_suffix = "B"
            elif max_abs >= 1e6:
                data['Value'] = data['Value'] / 1e6
                label = f"{y_label} (M$)"
                tooltip_prefix = "$"
                tooltip_suffix = "M"
            elif max_abs >= 1e3:
                data['Value'] = data['Value'] / 1e3
                label = f"{y_label} (K$)"
                tooltip_prefix = "$"
                tooltip_suffix = "K"
            else:
                label = f"{y_label} ($)"
                tooltip_prefix = "$"
                tooltip_suffix = ""
        else:
            label = y_label
            tooltip_prefix = ""
            tooltip_suffix = ""

        # Calculate growth badges — only when value is valid and non-zero
        growth_badges = []
        vals = data['Value'].tolist()
        n = len(vals)
        latest = vals[-1]
        periods = [(1, "1Q"), (2, "2Q"), (3, "3Q")] if quarterly else [(1, "1Y"), (2, "2Y"), (3, "3Y")]
        for steps, lbl in periods:
            idx = n - 1 - steps
            if idx >= 0:
                prior = vals[idx]
                # Skip if either value is NaN, zero, or would produce NaN pct
                try:
                    if prior != 0 and prior == prior and latest == latest:
                        pct = ((latest - prior) / abs(prior)) * 100
                        if pct == pct:  # final NaN check
                            growth_badges.append((lbl, pct))
                except Exception:
                    pass

        chart = alt.Chart(data).mark_bar(color=color).encode(
            x=alt.X('Date:O', title='Quarter' if quarterly else 'Year', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('Value:Q', title=label),
            tooltip=['Date', alt.Tooltip('Value:Q', format='.2f')]
        ).properties(height=220)
        return chart, growth_badges

    def render_growth_badges(badges):
        if not badges:
            return
        cols = st.columns(len(badges))
        for i, (label, pct) in enumerate(badges):
            color = "#2ecc71" if pct >= 0 else "#e74c3c"
            arrow = "\u25b2" if pct >= 0 else "\u25bc"
            with cols[i]:
                st.markdown(
                    f'<div style="background:{color}22; border:1px solid {color}; border-radius:6px; '
                    f'padding:4px 10px; text-align:center; font-size:13px; font-weight:600; color:{color};">'
                    f'{label}: {arrow} {abs(pct):.1f}%</div>',
                    unsafe_allow_html=True
                )

    # ── Input + Generate button ─────────────────────────────────────────────────
    ticker_input = st.text_input("Enter Ticker (e.g., NVDA, TSLA, AAPL):", "").upper()

    if st.button("Generate Deep Analysis"):
        with st.spinner("Fetching data..."):
            import time as _time
            def _yf_fetch(ticker_sym):
                """Fetch yfinance data with up to 3 retries on rate limit."""
                for attempt in range(3):
                    try:
                        s = yf.Ticker(ticker_sym)
                        info = s.info
                        # If we get rate limited, info will be minimal
                        if not info or info.get("trailingPegRatio") == "Too Many Requests":
                            raise Exception("Rate limited")
                        return s
                    except Exception as e:
                        if "Too Many Requests" in str(e) or "Rate" in str(e):
                            if attempt < 2:
                                _time.sleep(3 + attempt * 2)
                                continue
                        raise e
                raise Exception("Rate limited after 3 attempts. Please wait a moment and try again.")

            try:
                stock = _yf_fetch(ticker_input)
                st.session_state["stock_info"]       = stock.info
                st.session_state["hist_full"]        = stock.history(period="max")
                st.session_state["financials"]       = stock.financials
                st.session_state["quarterly_fin"]    = stock.quarterly_financials
                st.session_state["cashflow"]         = stock.cashflow
                st.session_state["quarterly_cf"]     = stock.quarterly_cashflow
                st.session_state["balance_sheet"]    = stock.balance_sheet
                st.session_state["q_balance_sheet"]  = stock.quarterly_balance_sheet
                st.session_state["recommendations"]  = stock.recommendations
                st.session_state["news_list"]        = stock.news or []
                st.session_state["ticker_loaded"]    = ticker_input
                st.session_state["analysis_done"]    = True
                st.session_state["price_range"]      = "1Y"
            except Exception as e:
                st.error(f"Error fetching data: {e}")

    # ── Render results if analysis has been run ──────────────────────────────────
    if st.session_state["analysis_done"]:
        info         = st.session_state["stock_info"]
        hist_full    = st.session_state["hist_full"]
        spy_hist_raw = st.session_state.get("spy_hist", None)


        financials   = st.session_state["financials"]
        quarterly_fin= st.session_state["quarterly_fin"]
        cashflow     = st.session_state["cashflow"]
        quarterly_cf = st.session_state["quarterly_cf"]
        recs         = st.session_state["recommendations"]
        news_list    = st.session_state["news_list"]
        loaded_ticker= st.session_state["ticker_loaded"]
        balance_sheet  = st.session_state.get("balance_sheet")
        q_balance_sheet= st.session_state.get("q_balance_sheet")

        # ── Company Name ──
        company_name = info.get("longName") or info.get("shortName") or loaded_ticker
        st.markdown(f"## {company_name} &nbsp;<span style='font-size:16px;color:#888;font-weight:400;'>({loaded_ticker})</span>", unsafe_allow_html=True)

        # ── Top metrics ──
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Price", f"${info.get('currentPrice', 'N/A')}")
        with col2:
            st.metric("Wall St. Target", f"${info.get('targetMeanPrice', 'N/A')}")
        with col3:
            _fpe_display = info.get('forwardPE')
            if _fpe_display is None:
                _feps2 = info.get("forwardEps")
                _pr2 = info.get("currentPrice")
                if _feps2 and _pr2 and _feps2 != 0:
                    _fpe_display = round(_pr2 / _feps2, 2)
            st.metric("Forward P/E", f"{_fpe_display}" if _fpe_display is not None else "N/A")
        with col4:
            inst_pct = info.get('heldPercentInstitutions', 0)
            st.metric("Inst. Ownership", f"{inst_pct*100:.1f}%" if inst_pct else "N/A")

        st.divider()

        # ── Compact Chart Grid (Price + KPIs) ─────────────────────────────────────
        st.header("📊 Charts")

        import streamlit.components.v1 as components
        import json

        # ── Collect all chart data ──
        chart_datasets = []

        # Price History
        if hist_full is not None and not hist_full.empty:
            hf = hist_full.reset_index() if hist_full.index.name in [None, "Date", "date", "index"] else hist_full.copy()
            if "Date" not in hf.columns and "date" in hf.columns:
                hf = hf.rename(columns={"date": "Date"})
            if "Date" in hf.columns and "Close" in hf.columns:
                hf["Date"] = pd.to_datetime(hf["Date"]).dt.tz_localize(None)
                hf = hf.sort_values("Date")
                today = pd.Timestamp.today().normalize()
                days_map = {"1W": 7, "1M": 30, "1Y": 365, "5Y": 1825, "ALL": 99999}
                price_ranges = {}
                for lbl, days in days_map.items():
                    if lbl == "ALL":
                        sub = hf
                    elif lbl == "YTD":
                        sub = hf[hf["Date"] >= pd.Timestamp(today.year, 1, 1)]
                    else:
                        sub = hf[hf["Date"] >= today - pd.Timedelta(days=days)]
                    if sub.empty: sub = hf
                    price_ranges[lbl] = {
                        "dates": [str(d.date()) for d in sub["Date"].tolist()],
                        "prices": [round(float(p), 2) for p in sub["Close"].tolist()]
                    }
                chart_datasets.append({
                    "id": "price", "title": "Price History", "type": "line",
                    "color": "#4fc3f7", "isPrice": True, "ranges": price_ranges,
                    "labels": list(price_ranges["1Y"]["dates"]),
                    "data": price_ranges["1Y"]["prices"]
                })

        def _series_to_chart(series, title, color, is_shares=False, flip_neg=False, quarterly=False):
            if series is None or series.empty: return None
            s = series.sort_index()
            if flip_neg and s.mean() < 0: s = s * -1
            lbl = [str(x.year) for x in s.index]
            vals = [round(float(v)/1e9, 3) if abs(float(v)) >= 1e8 else round(float(v), 2) for v in s.values]
            suffix = "B" if abs(s.mean()) >= 1e8 else ""

            # Compute growth badges: 1, 2, 3 periods back from latest
            badges = []
            clean = [(l, v) for l, v in zip(lbl, vals) if v == v and v is not None]
            if len(clean) >= 2:
                periods = [(1,"1Q"),(2,"2Q"),(3,"3Q")] if quarterly else [(1,"1Y"),(2,"2Y"),(3,"3Y")]
                latest_v = clean[-1][1]
                for steps, badge_lbl in periods:
                    idx = len(clean) - 1 - steps
                    if idx >= 0:
                        prior_v = clean[idx][1]
                        try:
                            if prior_v != 0 and prior_v == prior_v and latest_v == latest_v:
                                pct = round(((latest_v - prior_v) / abs(prior_v)) * 100, 1)
                                if pct == pct:
                                    badges.append({"label": badge_lbl, "pct": pct})
                        except Exception:
                            pass

            return {"id": title.lower().replace(" ","_"), "title": title, "type": "bar",
                    "color": color, "labels": lbl, "data": vals, "suffix": suffix,
                    "isShares": is_shares, "badges": badges}

        def _get_fin(df, *keys):
            if df is None: return None
            for k in keys:
                if k in df.index: return df.loc[k].sort_index()
            return None

        # Annual charts
        annual_charts = [
            _series_to_chart(_get_fin(financials, "Total Revenue"), "Revenue", "#2ecc71"),
            _series_to_chart(_get_fin(financials, "Net Income"), "Net Income", "#4fc3f7"),
            _series_to_chart(_get_fin(financials, "Basic EPS", "Diluted EPS"), "EPS", "#9b59b6"),
            _series_to_chart(_get_fin(cashflow, "Free Cash Flow"), "Free Cash Flow", "#e67e22"),
            _series_to_chart(_get_fin(financials, "Gross Profit"), "Gross Profit", "#1abc9c"),
            _series_to_chart(_get_fin(financials, "Operating Income"), "Op. Income", "#e74c3c"),
            _series_to_chart(_get_fin(balance_sheet, "Ordinary Shares Number","Share Issued","Common Stock"), "Shares Out.", "#e91e8c", is_shares=True),
            _series_to_chart(_get_fin(cashflow, "Capital Expenditure","Purchase Of Property Plant And Equipment","Capital Expenditures"), "CapEx", "#8e44ad", flip_neg=True),
        ]
        rpo = _get_fin(balance_sheet, "Remaining Performance Obligation","Deferred Revenue","DeferredRevenue")
        if rpo is not None and rpo.abs().max() > 0:
            annual_charts.append(_series_to_chart(rpo, "RPO / Deferred Rev", "#16a085"))

        # Quarterly charts
        quarterly_charts = [
            _series_to_chart(_get_fin(quarterly_fin, "Total Revenue"), "Revenue (Q)", "#2ecc71", quarterly=True),
            _series_to_chart(_get_fin(quarterly_fin, "Net Income"), "Net Income (Q)", "#4fc3f7", quarterly=True),
            _series_to_chart(_get_fin(quarterly_fin, "Basic EPS","Diluted EPS"), "EPS (Q)", "#9b59b6", quarterly=True),
            _series_to_chart(_get_fin(quarterly_cf, "Free Cash Flow"), "FCF (Q)", "#e67e22", quarterly=True),
            _series_to_chart(_get_fin(quarterly_fin, "Gross Profit"), "Gross Profit (Q)", "#1abc9c", quarterly=True),
            _series_to_chart(_get_fin(quarterly_fin, "Operating Income"), "Op. Income (Q)", "#e74c3c", quarterly=True),
            _series_to_chart(_get_fin(q_balance_sheet, "Ordinary Shares Number","Share Issued","Common Stock"), "Shares Out. (Q)", "#e91e8c", is_shares=True, quarterly=True),
            _series_to_chart(_get_fin(quarterly_cf, "Capital Expenditure","Purchase Of Property Plant And Equipment","Capital Expenditures"), "CapEx (Q)", "#8e44ad", flip_neg=True, quarterly=True),
        ]
        q_rpo = _get_fin(q_balance_sheet, "Remaining Performance Obligation","Deferred Revenue","DeferredRevenue")
        if q_rpo is not None and q_rpo.abs().max() > 0:
            quarterly_charts.append(_series_to_chart(q_rpo, "RPO / Def. Rev (Q)", "#16a085", quarterly=True))

        all_annual  = [c for c in annual_charts if c]
        all_quarter = [c for c in quarterly_charts if c]
        all_charts_annual   = json.dumps(chart_datasets + all_annual)
        all_charts_quarterly = json.dumps(chart_datasets + all_quarter)

        grid_html = f"""<!DOCTYPE html>
    <html>
    <head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
      *{{box-sizing:border-box;margin:0;padding:0}}
      body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:transparent;padding:4px 0}}
      .tab-row{{display:flex;gap:6px;margin-bottom:12px}}
      .tab-btn{{padding:6px 18px;border-radius:20px;border:1.5px solid #ddd;background:white;
        cursor:pointer;font-size:13px;font-weight:500;transition:all .2s}}
      .tab-btn.active{{background:#ff4b4b;color:white;border-color:#ff4b4b}}
      .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
      .card{{background:white;border:1px solid #e8e8e8;border-radius:10px;
        padding:10px 12px 8px;position:relative;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
      .card-title{{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;
        letter-spacing:.4px;margin-bottom:4px;padding-right:20px}}
      .expand-btn{{position:absolute;top:8px;right:8px;width:20px;height:20px;
        border:none;background:none;cursor:pointer;color:#bbb;font-size:14px;
        display:flex;align-items:center;justify-content:center;border-radius:4px;
        transition:all .15s;line-height:1}}
      .expand-btn:hover{{background:#f0f0f0;color:#555}}
      .card canvas{{max-height:130px}}
      .range-row{{display:flex;gap:4px;margin-bottom:4px;flex-wrap:wrap}}
      .r-btn{{padding:2px 7px;border-radius:4px;border:1px solid #ddd;background:white;
        cursor:pointer;font-size:10px;font-weight:500;transition:all .15s}}
      .r-btn.active{{background:#ff4b4b;color:white;border-color:#ff4b4b}}
      /* Modal */
      .modal-bg{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);
        z-index:9999;align-items:center;justify-content:center}}
      .modal-bg.open{{display:flex}}
      .modal{{background:white;border-radius:14px;padding:24px;width:min(800px,92vw);
        max-height:90vh;overflow:auto;position:relative}}
      .modal-title{{font-size:17px;font-weight:700;margin-bottom:16px;color:#222}}
      .modal canvas{{max-height:420px;width:100%!important}}
      .modal-close{{position:absolute;top:14px;right:16px;background:none;border:none;
        font-size:22px;cursor:pointer;color:#888;line-height:1}}
      .modal-close:hover{{color:#333}}
      .badges{{display:flex;gap:4px;margin-top:5px;flex-wrap:wrap}}
      .badge{{padding:2px 7px;border-radius:5px;font-size:10px;font-weight:700;}}
      .badge.pos{{background:#e8f8f0;color:#1a9e5c;border:1px solid #a8d8bc}}
      .badge.neg{{background:#fdf0ef;color:#c0392b;border:1px solid #f0b8b0}}
      .modal-badges{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}}
      .modal-badge{{padding:4px 12px;border-radius:6px;font-size:13px;font-weight:700}}
      .modal-badge.pos{{background:#e8f8f0;color:#1a9e5c;border:1px solid #a8d8bc}}
      .modal-badge.neg{{background:#fdf0ef;color:#c0392b;border:1px solid #f0b8b0}}
    </style>
    </head>
    <body>

    <div class="tab-row">
      <button class="tab-btn active" onclick="switchTab('annual',this)">📅 Annual</button>
      <button class="tab-btn" onclick="switchTab('quarterly',this)">📆 Quarterly</button>
    </div>

    <div id="grid" class="grid"></div>

    <!-- Modal -->
    <div class="modal-bg" id="modalBg" onclick="closeModal(event)">
      <div class="modal">
        <button class="modal-close" onclick="closeModalDirect()">✕</button>
        <div class="modal-title" id="modalTitle"></div>
        <div id="modalBadges" class="modal-badges"></div>
        <div id="modalRangeRow" class="range-row" style="margin-bottom:12px"></div>
        <canvas id="modalCanvas"></canvas>
      </div>
    </div>

    <script>
    const annualData   = {all_charts_annual};
    const quarterlyData = {all_charts_quarterly};
    let currentTab = "annual";
    let charts = {{}};
    let modalChart = null;
    let expandedId = null;

    function fmt(v, suffix) {{
      if (v === null || v === undefined || isNaN(v)) return "";
      const abs = Math.abs(v);
      if (suffix === "B") return (v >= 0 ? "" : "-") + "$" + Math.abs(v).toFixed(1) + "B";
      return v % 1 === 0 ? v.toString() : v.toFixed(2);
    }}

    function makeChart(canvasId, ds, small=true) {{
      const ctx = document.getElementById(canvasId);
      if (!ctx) return null;
      const isLine = ds.type === "line";
      const color = ds.color || "#4fc3f7";
      const isUp = ds.data && ds.data.length > 1 && ds.data[ds.data.length-1] >= ds.data[0];
      const lineColor = ds.isPrice ? (isUp ? "#2ecc71" : "#e74c3c") : color;
      const fillColor = ds.isPrice ? (isUp ? "rgba(46,204,113,0.1)" : "rgba(231,76,60,0.1)") : color + "33";

      return new Chart(ctx, {{
        type: isLine ? "line" : "bar",
        data: {{
          labels: ds.labels,
          datasets: [{{
            data: ds.data,
            borderColor: lineColor,
            backgroundColor: isLine ? fillColor : color + "cc",
            borderWidth: isLine ? (small ? 1.5 : 2) : 0,
            borderRadius: isLine ? 0 : (small ? 3 : 5),
            pointRadius: 0,
            fill: isLine,
            tension: 0.3
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          animation: {{ duration: small ? 400 : 700 }},
          interaction: {{ intersect: false, mode: "index" }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              callbacks: {{
                label: c => {{
                  const v = c.parsed.y;
                  if (ds.isPrice) return "$" + v.toFixed(2);
                  if (ds.suffix === "B") return (v < 0 ? "-$" : "$") + Math.abs(v).toFixed(2) + "B";
                  return v.toFixed(2);
                }}
              }}
            }}
          }},
          scales: {{
            x: {{
              ticks: {{ maxTicksLimit: small ? 4 : 10, maxRotation: 0, font: {{ size: small ? 9 : 11 }} }},
              grid: {{ display: false }}
            }},
            y: {{
              ticks: {{
                maxTicksLimit: small ? 3 : 6,
                font: {{ size: small ? 9 : 11 }},
                callback: v => {{
                  if (ds.isPrice) return "$" + v.toFixed(0);
                  if (ds.suffix === "B") return "$" + v.toFixed(0) + "B";
                  return v;
                }}
              }},
              grid: {{ color: "rgba(0,0,0,0.04)" }}
            }}
          }}
        }}
      }});
    }}

    function buildGrid(datasets) {{
      // Destroy old charts
      Object.values(charts).forEach(c => c && c.destroy());
      charts = {{}};

      const grid = document.getElementById("grid");
      grid.innerHTML = "";

      datasets.forEach((ds, i) => {{
        const card = document.createElement("div");
        card.className = "card";

        let rangeRow = "";
        if (ds.isPrice && ds.ranges) {{
          rangeRow = `<div class="range-row" id="range_${{i}}">` +
            Object.keys(ds.ranges).map(r =>
              `<button class="r-btn${{r==="1Y"?" active":""}}" onclick="switchPriceRange(${{i}},'${{r}}')" id="rb_${{i}}_${{r}}">${{r}}</button>`
            ).join("") + `</div>`;
        }}

        let badgeHtml = "";
        if (ds.badges && ds.badges.length > 0 && !ds.isPrice) {{
          const parts = ds.badges.map(function(b) {{
            const cls = b.pct >= 0 ? "pos" : "neg";
            const arrow = b.pct >= 0 ? "\u25b2" : "\u25bc";
            return '<span class="badge ' + cls + '">' + b.label + ': ' + arrow + ' ' + Math.abs(b.pct).toFixed(1) + '%</span>';
          }});
          badgeHtml = '<div class="badges">' + parts.join("") + '</div>';
        }}

        card.innerHTML = `
          <div class="card-title">${{ds.title}}</div>
          ${{rangeRow}}
          <div style="position:relative;height:120px">
            <canvas id="c_${{i}}"></canvas>
          </div>
          ${{badgeHtml}}
          <button class="expand-btn" onclick="openModal(${{i}})" title="Expand">⤢</button>
        `;
        grid.appendChild(card);

        requestAnimationFrame(() => {{
          charts[i] = makeChart("c_" + i, ds, true);
        }});
      }});
    }}

    function switchPriceRange(idx, range) {{
      const ds = (currentTab === "annual" ? annualData : quarterlyData)[idx];
      if (!ds || !ds.ranges || !ds.ranges[range]) return;
      // Update buttons
      Object.keys(ds.ranges).forEach(r => {{
        const btn = document.getElementById("rb_" + idx + "_" + r);
        if (btn) btn.className = "r-btn" + (r === range ? " active" : "");
      }});
      const newData = ds.ranges[range];
      const isUp = newData.prices[newData.prices.length-1] >= newData.prices[0];
      const c = charts[idx];
      if (c) {{
        c.data.labels = newData.dates;
        c.data.datasets[0].data = newData.prices;
        c.data.datasets[0].borderColor = isUp ? "#2ecc71" : "#e74c3c";
        c.data.datasets[0].backgroundColor = isUp ? "rgba(46,204,113,0.1)" : "rgba(231,76,60,0.1)";
        c.update();
      }}
    }}

    function openModal(idx) {{
      const datasets = currentTab === "annual" ? annualData : quarterlyData;
      const ds = datasets[idx];
      expandedId = idx;
      document.getElementById("modalTitle").textContent = ds.title;

      // Build modal badges
      const mb = document.getElementById("modalBadges");
      mb.innerHTML = "";
      if (ds.badges && ds.badges.length > 0 && !ds.isPrice) {{
        ds.badges.forEach(function(b) {{
          const span = document.createElement("span");
          span.className = "modal-badge " + (b.pct >= 0 ? "pos" : "neg");
          const arrow = b.pct >= 0 ? "\u25b2" : "\u25bc";
          span.textContent = b.label + ": " + arrow + " " + Math.abs(b.pct).toFixed(1) + "%";
          mb.appendChild(span);
        }});
      }}

      // Build modal range buttons for price
      const rr = document.getElementById("modalRangeRow");
      rr.innerHTML = "";
      if (ds.isPrice && ds.ranges) {{
        Object.keys(ds.ranges).forEach(r => {{
          const b = document.createElement("button");
          b.className = "r-btn" + (r === "1Y" ? " active" : "");
          b.textContent = r;
          b.id = "mrb_" + r;
          b.onclick = () => switchModalRange(r, ds);
          rr.appendChild(b);
        }});
      }}

      if (modalChart) {{ modalChart.destroy(); modalChart = null; }}
      const canvas = document.getElementById("modalCanvas");
      canvas.style.height = "400px";
      modalChart = makeChart("modalCanvas", ds, false);
      document.getElementById("modalBg").classList.add("open");
    }}

    function switchModalRange(range, ds) {{
      if (!ds.ranges || !ds.ranges[range]) return;
      Object.keys(ds.ranges).forEach(r => {{
        const b = document.getElementById("mrb_" + r);
        if (b) b.className = "r-btn" + (r === range ? " active" : "");
      }});
      const nd = ds.ranges[range];
      const isUp = nd.prices[nd.prices.length-1] >= nd.prices[0];
      if (modalChart) {{
        modalChart.data.labels = nd.dates;
        modalChart.data.datasets[0].data = nd.prices;
        modalChart.data.datasets[0].borderColor = isUp ? "#2ecc71" : "#e74c3c";
        modalChart.data.datasets[0].backgroundColor = isUp ? "rgba(46,204,113,0.1)" : "rgba(231,76,60,0.1)";
        modalChart.update();
      }}
    }}

    function closeModal(e) {{
      if (e.target === document.getElementById("modalBg")) closeModalDirect();
    }}
    function closeModalDirect() {{
      document.getElementById("modalBg").classList.remove("open");
      if (modalChart) {{ modalChart.destroy(); modalChart = null; }}
    }}

    function switchTab(tab, btn) {{
      currentTab = tab;
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      buildGrid(tab === "annual" ? annualData : quarterlyData);
    }}

    // Init
    buildGrid(annualData);
    </script>
    </body>
    </html>"""

        total_charts = len(all_annual) + 1
        grid_height = 220 + (((total_charts - 1) // 4) * 200)
        components.html(grid_html, height=max(grid_height, 500))

        st.divider()

        # ── Key Ratios ──
        st.subheader("📋 Key Ratios & Metrics")


        import streamlit.components.v1 as components

        def badge(text, color, bg):
            return ('<span style="background:' + bg + ';color:' + color +
                    ';border:1px solid ' + color +
                    ';border-radius:5px;padding:2px 7px;font-size:11px;font-weight:700;">' +
                    text + '</span>')

        mkt_cap      = info.get("marketCap", 0) or 0
        pe           = info.get("trailingPE")
        # If yfinance returns None for PE (common with negative earnings), calculate manually
        if pe is None:
            _eps = info.get("trailingEps")
            _price = info.get("currentPrice")
            if _eps and _price and _eps != 0:
                pe = round(_price / _eps, 2)
        fpe          = info.get("forwardPE")
        if fpe is None:
            _feps = info.get("forwardEps")
            _price = info.get("currentPrice")
            if _feps and _price and _feps != 0:
                fpe = round(_price / _feps, 2)
        ev_ebitda    = info.get("enterpriseToEbitda")
        price        = info.get("currentPrice")
        shares_out   = info.get("sharesOutstanding")
        total_rev    = info.get("totalRevenue")
        net_income   = info.get("netIncomeToCommon")
        total_debt   = info.get("totalDebt") or 0
        total_cash   = info.get("totalCash") or 0
        equity       = info.get("stockholdersEquity") or info.get("bookValue", 0)
        ebitda       = info.get("ebitda")
        gross_profit = info.get("grossProfits")
        op_cashflow  = info.get("operatingCashflow")
        fcf          = info.get("freeCashflow")

        # Profit margin — fallback: net income / revenue
        margin = info.get("profitMargins")
        if margin is None and net_income and total_rev and total_rev != 0:
            margin = net_income / total_rev
        margin = margin or 0

        # Operating margin — fallback: operating income / revenue
        op_margin = info.get("operatingMargins")
        if op_margin is None and total_rev and total_rev != 0:
            op_income_raw = _get_fin(financials, "Operating Income")
            if op_income_raw is not None and not op_income_raw.empty:
                op_margin = float(op_income_raw.iloc[-1]) / total_rev
        op_margin = op_margin if op_margin is not None else None

        # Debt/Equity — fallback using bookValue per share * sharesOutstanding
        de = info.get("debtToEquity")
        if de is None and total_debt and shares_out:
            bvps_raw = info.get("bookValue")
            if bvps_raw and bvps_raw != 0:
                total_equity = bvps_raw * shares_out
                if total_equity != 0:
                    de = round((total_debt / abs(total_equity)) * 100, 1)

        # ROE / ROA — yfinance returns these as ratios (e.g. -36.46 means -3646%)
        # Normalize: if abs value > 1, it's already a percentage-style ratio, divide by 100
        roe = info.get("returnOnEquity")
        roa = info.get("returnOnAssets")
        if roe is not None and abs(roe) > 1:
            roe = roe / 100
        if roa is not None and abs(roa) > 1:
            roa = roa / 100
        # Fallback ROE: net income / (bookValue * shares)
        if roe is None and net_income and shares_out:
            bvps_raw = info.get("bookValue")
            if bvps_raw and bvps_raw != 0:
                total_equity = bvps_raw * shares_out
                if total_equity != 0:
                    roe = net_income / abs(total_equity)
        # Fallback ROA
        total_assets = info.get("totalAssets")
        if roa is None and net_income and total_assets and total_assets != 0:
            roa = net_income / total_assets
        roic_proxy = (roe * 0.6 + roa * 0.4) if (roe and roa) else (roe or roa)

        # Revenue growth — fallback from financials if available
        rev_growth   = info.get("revenueGrowth")

        # Earnings growth
        earn_growth  = info.get("earningsGrowth")

        # PEG Ratio — prefer yfinance trailingPegRatio, fallback: trailing P/E / (earn_growth * 100)
        peg = info.get("trailingPegRatio")
        if peg is None and pe is not None and earn_growth and earn_growth > 0:
            peg = round(pe / (earn_growth * 100), 2)

        # P/S ratio — fallback: market cap / total revenue
        ps_ratio = info.get("priceToSalesTrailing12Months")
        if ps_ratio is None and mkt_cap and total_rev and total_rev != 0:
            ps_ratio = round(mkt_cap / total_rev, 2)

        # P/B ratio — fallback: price / book value per share
        pb_ratio = info.get("priceToBook")
        bvps = info.get("bookValue")
        if pb_ratio is None and price and bvps and bvps != 0:
            pb_ratio = round(price / bvps, 2)

        # EV/EBITDA fallback
        ev_raw = info.get("enterpriseValue")
        if ev_ebitda is None and ev_raw and ebitda and ebitda != 0:
            ev_ebitda = round(ev_raw / ebitda, 1)

        beta         = info.get("beta")
        curr_ratio   = info.get("currentRatio")
        short_pct    = info.get("shortPercentOfFloat")
        div_yield    = info.get("dividendYield")
        payout_ratio = info.get("payoutRatio")
        pfcf         = (mkt_cap / fcf) if (mkt_cap and fcf and fcf != 0) else None

        # Market Cap
        if mkt_cap >= 200e9:   mcap_b = badge("Mega Cap",  "#3498db", "#ebf5fb")
        elif mkt_cap >= 10e9:  mcap_b = badge("Large Cap", "#2980b9", "#ebf5fb")
        elif mkt_cap >= 2e9:   mcap_b = badge("Mid Cap",   "#f39c12", "#fef9e7")
        else:                  mcap_b = badge("Small Cap", "#e74c3c", "#fdf0ef")
        mcap_val = (f"${mkt_cap/1e12:.2f}T" if mkt_cap >= 1e12 else f"${mkt_cap/1e9:.1f}B" if mkt_cap >= 1e9 else f"${mkt_cap/1e6:.0f}M") if mkt_cap else "N/A"

        # P/E
        if pe is not None:
            if pe < 0:     pe_b = badge("Negative Earnings", "#e74c3c", "#fdf0ef")
            elif pe < 15:  pe_b = badge("Cheap",             "#27ae60", "#eafaf1")
            elif pe < 25:  pe_b = badge("Fair",              "#f39c12", "#fef9e7")
            elif pe < 40:  pe_b = badge("Pricey",            "#e67e22", "#fdf2e9")
            else:          pe_b = badge("Expensive",         "#e74c3c", "#fdf0ef")
        else: pe_b = ""
        if pe is not None and fpe is not None and pe > 0 and fpe > 0:
            pe_trend_b = badge("▼ Growth Expected", "#27ae60", "#eafaf1") if fpe < pe else badge("▲ Slowing", "#e74c3c", "#fdf0ef")
        else: pe_trend_b = ""
        pe_val = f"{pe:.1f}" if pe is not None else "N/A"

        # EV/EBITDA
        if ev_ebitda:
            if ev_ebitda < 10:    ev_b = badge("Undervalued", "#27ae60", "#eafaf1")
            elif ev_ebitda < 15:  ev_b = badge("Fair",        "#f39c12", "#fef9e7")
            elif ev_ebitda < 20:  ev_b = badge("Stretched",   "#e67e22", "#fdf2e9")
            else:                 ev_b = badge("Expensive",   "#e74c3c", "#fdf0ef")
        else: ev_b = ""
        ev_val = f"{ev_ebitda:.1f}x" if ev_ebitda else "N/A"

        # Profit Margin
        mg_val = f"{margin*100:.1f}%" if margin != 0 else "—"
        if mg_val == "—":      mg_b = badge("No Data",    "#95a5a6", "#f0f0f0")
        elif margin >= 0.25:   mg_b = badge("Exceptional", "#1a9e5c", "#e8f8f2")
        elif margin >= 0.15:   mg_b = badge("Strong",      "#27ae60", "#eafaf1")
        elif margin >= 0.08:   mg_b = badge("Healthy",     "#f39c12", "#fef9e7")
        elif margin > 0:       mg_b = badge("Thin",        "#e67e22", "#fdf2e9")
        elif margin == 0:      mg_b = ""
        else:                  mg_b = badge("Negative",    "#e74c3c", "#fdf0ef")

        # Operating Margin
        om_val = f"{op_margin*100:.1f}%" if op_margin is not None else "—"
        if op_margin is None:       om_b = badge("No Data",     "#95a5a6", "#f0f0f0")
        elif op_margin >= 0.30:     om_b = badge("Exceptional", "#1a9e5c", "#e8f8f2")
        elif op_margin >= 0.20:     om_b = badge("Strong",      "#27ae60", "#eafaf1")
        elif op_margin >= 0.10:     om_b = badge("Healthy",     "#f39c12", "#fef9e7")
        elif op_margin > 0:         om_b = badge("Thin",        "#e67e22", "#fdf2e9")
        else:                       om_b = badge("Negative",    "#e74c3c", "#fdf0ef")

        # Debt/Equity
        if de is not None:
            if de < 30:    de_b = badge("Conservative", "#27ae60", "#eafaf1")
            elif de < 80:  de_b = badge("Moderate",     "#f39c12", "#fef9e7")
            elif de < 150: de_b = badge("Leveraged",    "#e67e22", "#fdf2e9")
            else:          de_b = badge("High Risk",    "#e74c3c", "#fdf0ef")
        else: de_b = ""
        de_val = f"{de:.0f}%" if de is not None else "N/A"

        # Revenue Growth
        if rev_growth is not None:
            if rev_growth >= 0.20:    rg_b = badge("&#9650; Hyper Growth", "#1a9e5c", "#e8f8f2")
            elif rev_growth >= 0.10:  rg_b = badge("&#9650; Strong",       "#27ae60", "#eafaf1")
            elif rev_growth >= 0.03:  rg_b = badge("&#9650; Steady",       "#f39c12", "#fef9e7")
            elif rev_growth >= 0:     rg_b = badge("&#9650; Slow",         "#e67e22", "#fdf2e9")
            else:                     rg_b = badge("&#9660; Declining",    "#e74c3c", "#fdf0ef")
        else: rg_b = badge("No Data", "#95a5a6", "#f0f0f0")
        rg_val = f"{rev_growth*100:.1f}%" if rev_growth is not None else "—"

        # ROIC
        if roic_proxy:
            rp = roic_proxy * 100
            if rp >= 20:    roic_b = badge("Excellent", "#1a9e5c", "#e8f8f2")
            elif rp >= 12:  roic_b = badge("Good",      "#27ae60", "#eafaf1")
            elif rp >= 6:   roic_b = badge("Average",   "#f39c12", "#fef9e7")
            else:           roic_b = badge("Weak",      "#e74c3c", "#fdf0ef")
            roe_b = badge("ROE: " + f"{roe*100:.0f}%", "#888", "#f0f0f0") if roe else ""
        else:
            roic_b = ""
            roe_b = ""
        roic_val = f"{roic_proxy*100:.1f}%" if roic_proxy else "N/A"

        # Beta
        if beta:
            if beta < 0.8:    beta_b = badge("Low Risk",    "#27ae60", "#eafaf1")
            elif beta < 1.2:  beta_b = badge("Market Risk", "#f39c12", "#fef9e7")
            else:             beta_b = badge("High Vol",    "#e74c3c", "#fdf0ef")
        else: beta_b = ""
        beta_val = f"{beta:.2f}" if beta else "N/A"

        # Current Ratio
        if curr_ratio is not None:
            if curr_ratio >= 2.0:   cr_b = badge("Very Liquid",  "#1a9e5c", "#e8f8f2")
            elif curr_ratio >= 1.5: cr_b = badge("Healthy",      "#27ae60", "#eafaf1")
            elif curr_ratio >= 1.0: cr_b = badge("Adequate",     "#f39c12", "#fef9e7")
            else:                   cr_b = badge("Liquidity Risk","#e74c3c", "#fdf0ef")
        else: cr_b = ""
        cr_val = f"{curr_ratio:.2f}" if curr_ratio is not None else "N/A"

        # P/S Ratio
        if ps_ratio is not None:
            if ps_ratio < 2:    ps_b = badge("Cheap",     "#27ae60", "#eafaf1")
            elif ps_ratio < 5:  ps_b = badge("Fair",      "#f39c12", "#fef9e7")
            elif ps_ratio < 10: ps_b = badge("Pricey",    "#e67e22", "#fdf2e9")
            else:               ps_b = badge("Expensive", "#e74c3c", "#fdf0ef")
        else: ps_b = badge("No Data", "#95a5a6", "#f0f0f0")
        ps_val = f"{ps_ratio:.1f}x" if ps_ratio is not None else "—"

        # P/B Ratio
        if pb_ratio is not None:
            if pb_ratio < 1:    pb_b = badge("Below Book",  "#1a9e5c", "#e8f8f2")
            elif pb_ratio < 3:  pb_b = badge("Reasonable",  "#27ae60", "#eafaf1")
            elif pb_ratio < 6:  pb_b = badge("Premium",     "#f39c12", "#fef9e7")
            else:               pb_b = badge("Very Premium","#e74c3c", "#fdf0ef")
        else: pb_b = ""
        pb_val = f"{pb_ratio:.1f}x" if pb_ratio is not None else "N/A"

        # Short Interest
        if short_pct is not None:
            if short_pct < 0.03:   si_b = badge("Very Low",   "#1a9e5c", "#e8f8f2")
            elif short_pct < 0.07: si_b = badge("Low",        "#27ae60", "#eafaf1")
            elif short_pct < 0.15: si_b = badge("Moderate",   "#f39c12", "#fef9e7")
            elif short_pct < 0.25: si_b = badge("High",       "#e67e22", "#fdf2e9")
            else:                  si_b = badge("Heavy Short", "#e74c3c", "#fdf0ef")
        else: si_b = ""
        si_val = f"{short_pct*100:.1f}%" if short_pct is not None else "N/A"

        # Earnings Growth
        if earn_growth is not None:
            if earn_growth >= 0.25:   eg_b = badge("&#9650; Explosive", "#1a9e5c", "#e8f8f2")
            elif earn_growth >= 0.10: eg_b = badge("&#9650; Strong",    "#27ae60", "#eafaf1")
            elif earn_growth >= 0:    eg_b = badge("&#9650; Growing",   "#f39c12", "#fef9e7")
            else:                     eg_b = badge("&#9660; Shrinking", "#e74c3c", "#fdf0ef")
        else: eg_b = badge("No Data", "#95a5a6", "#f0f0f0")
        eg_val = f"{earn_growth*100:.1f}%" if earn_growth is not None else "—"

        # Dividend Yield
        # yfinance inconsistently returns either 0.0089 or 0.89 for ~0.89% yield
        # Normalize: if >= 0.25 it's already in % form (e.g. 0.89 = 0.89%), divide by 100
        if div_yield and div_yield > 0:
            if div_yield >= 0.25:
                div_yield = div_yield / 100
            dy_pct = div_yield * 100
            if dy_pct >= 4.0:     dy_b = badge("High Yield",  "#1a9e5c", "#e8f8f2")
            elif dy_pct >= 1.5:   dy_b = badge("Solid Yield", "#27ae60", "#eafaf1")
            elif dy_pct > 0:      dy_b = badge("Low Yield",   "#f39c12", "#fef9e7")
            dy_val = f"{dy_pct:.4f}%" if dy_pct < 0.1 else f"{dy_pct:.2f}%"
        else:
            dy_b = badge("No Dividend", "#95a5a6", "#f0f0f0")
            dy_val = "—"

        # Payout Ratio
        # yfinance returns as decimal (0.21 = 21%) — normalize if > 1.5
        if payout_ratio and payout_ratio > 0 and div_yield and div_yield > 0:
            if payout_ratio > 1.5:
                payout_ratio = payout_ratio / 100
            pr_pct = payout_ratio * 100
            if pr_pct <= 35:    pr_b = badge("Sustainable",   "#1a9e5c", "#e8f8f2")
            elif pr_pct <= 60:  pr_b = badge("Healthy",       "#27ae60", "#eafaf1")
            elif pr_pct <= 80:  pr_b = badge("Stretched",     "#f39c12", "#fef9e7")
            else:               pr_b = badge("Unsustainable", "#e74c3c", "#fdf0ef")
            pr_val = f"{pr_pct:.2f}%"
        else:
            pr_b = badge("N/A", "#95a5a6", "#f0f0f0")
            pr_val = "—"

        # Enterprise Value
        if ev_raw:
            if ev_raw >= 1e12:   ev_raw_val = f"${ev_raw/1e12:.2f}T"
            elif ev_raw >= 1e9:  ev_raw_val = f"${ev_raw/1e9:.1f}B"
            else:                ev_raw_val = f"${ev_raw/1e6:.0f}M"
            # Compare EV to market cap to signal debt load
            if mkt_cap and mkt_cap > 0:
                ev_ratio = ev_raw / mkt_cap
                if ev_ratio < 0.95:     ev_raw_b = badge("Net Cash Position",  "#1a9e5c", "#e8f8f2")
                elif ev_ratio < 1.05:   ev_raw_b = badge("Clean Balance Sheet","#27ae60", "#eafaf1")
                elif ev_ratio < 1.20:   ev_raw_b = badge("Light Debt",         "#f39c12", "#fef9e7")
                elif ev_ratio < 1.50:   ev_raw_b = badge("Moderate Debt",      "#e67e22", "#fdf2e9")
                elif ev_ratio < 2.00:   ev_raw_b = badge("Heavy Debt",         "#e74c3c", "#fdf0ef")
                else:                   ev_raw_b = badge("Debt Loaded",        "#922b21", "#fdf0ef")
            else:
                ev_raw_b = ""
        else:
            ev_raw_val = "N/A"
            ev_raw_b = ""

        # Price / Free Cash Flow
        if pfcf is not None:
            if pfcf < 0:     pfcf_b = badge("Negative FCF",  "#e74c3c", "#fdf0ef")
            elif pfcf < 15:  pfcf_b = badge("Cheap",         "#27ae60", "#eafaf1")
            elif pfcf < 25:  pfcf_b = badge("Fair",          "#f39c12", "#fef9e7")
            elif pfcf < 40:  pfcf_b = badge("Pricey",        "#e67e22", "#fdf2e9")
            else:            pfcf_b = badge("Expensive",     "#e74c3c", "#fdf0ef")
            pfcf_val = f"{pfcf:.1f}x"
        else:
            pfcf_b = badge("No Data", "#95a5a6", "#f0f0f0")
            pfcf_val = "—"

        # PEG Ratio badges (Lynch's #1 metric: <1 = undervalued, >2 = expensive)
        if peg is not None and peg > 0:
            if peg < 0.5:    peg_b = badge("Very Cheap",  "#1a9e5c", "#e8f8f2")
            elif peg < 1.0:  peg_b = badge("Undervalued", "#27ae60", "#eafaf1")
            elif peg < 1.5:  peg_b = badge("Fair",        "#f39c12", "#fef9e7")
            elif peg < 2.0:  peg_b = badge("Stretched",   "#e67e22", "#fdf2e9")
            else:            peg_b = badge("Expensive",   "#e74c3c", "#fdf0ef")
            peg_val = f"{peg:.2f}"
        elif peg is not None and peg <= 0:
            peg_b = badge("Negative / N/M", "#95a5a6", "#f0f0f0")
            peg_val = f"{peg:.2f}"
        else:
            peg_b = badge("No Data", "#95a5a6", "#f0f0f0")
            peg_val = "—"

        def card(label, value, badges_html, top_color):
            return (
                '<div class="card" style="border-top-color:' + top_color + ';">' +
                '<div class="card-label">' + label + '</div>' +
                '<div class="card-value">' + value + '</div>' +
                '<div class="card-badges">' + badges_html + '</div>' +
                '</div>'
            )

        cards_html = (
            card("Market Cap",         mcap_val,    mcap_b,                    "#3498db") +
            card("P/E Ratio",          pe_val,      pe_b + " " + pe_trend_b,   "#9b59b6") +
            card("PEG Ratio",          peg_val,     peg_b,                     "#8e44ad") +
            card("EV / EBITDA",        ev_val,      ev_b,                      "#e67e22") +
            card("Profit Margin",      mg_val,      mg_b,                      "#2ecc71") +
            card("Operating Margin",   om_val,      om_b,                      "#27ae60") +
            card("Debt / Equity",      de_val,      de_b,                      "#e74c3c") +
            card("Rev Growth (YoY)",   rg_val,      rg_b,                      "#1abc9c") +
            card("Return on Capital",  roic_val,    roic_b + " " + roe_b,      "#f1c40f") +
            card("Beta",               beta_val,    beta_b,                    "#95a5a6") +
            card("Current Ratio",      cr_val,      cr_b,                      "#16a085") +
            card("Price / Sales",      ps_val,      ps_b,                      "#8e44ad") +
            card("Price / Book",       pb_val,      pb_b,                      "#2471a3") +
            card("Short Interest",     si_val,      si_b,                      "#c0392b") +
            card("Earnings Growth",    eg_val,      eg_b,                      "#117a65") +
            card("Dividend Yield",     dy_val,      dy_b,                      "#27ae60") +
            card("Payout Ratio",       pr_val,      pr_b,                      "#1e8449") +
            card("Enterprise Value",   ev_raw_val,  ev_raw_b,                  "#2980b9") +
            card("Price / Free CF",    pfcf_val,    pfcf_b,                    "#6c3483")
        )

        metrics_html = """<!DOCTYPE html><html><head><style>
    body{font-family:-apple-system,sans-serif;margin:0;padding:0;}
    .grid{display:flex;flex-wrap:wrap;gap:10px;}
    .card{background:#f8f9fa;border-radius:10px;padding:12px 16px;flex:1;min-width:140px;max-width:175px;border-top:3px solid #e0e0e0;}
    .card:hover{box-shadow:0 4px 12px rgba(0,0,0,0.08);}
    .card-label{font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px;}
    .card-value{font-size:20px;font-weight:700;color:#1a1a2e;margin-bottom:6px;}
    .card-badges{display:flex;flex-wrap:wrap;gap:4px;}
    </style></head><body>
    <div class="grid">""" + cards_html + """</div></body></html>"""

        components.html(metrics_html, height=460)
        st.divider()

        # ── P/E Ratio Chart (animated, time-range buttons) ───────────────────────
        st.header("📈 P/E Ratio History")
        try:
            import streamlit.components.v1 as components
            import json

            # Build daily P/E from price history and trailing EPS from financials
            if hist_full is not None and not hist_full.empty and financials is not None:
                # Get annual EPS
                eps_annual = None
                for col in ['Basic EPS', 'Diluted EPS']:
                    if col in financials.index:
                        eps_annual = financials.loc[col].sort_index()
                        break

                if eps_annual is not None and not eps_annual.empty:
                    ph = hist_full.copy()
                    # Date may be index or column depending on state
                    if "Date" not in ph.columns:
                        ph = ph.reset_index()
                        if "date" in ph.columns: ph = ph.rename(columns={"date": "Date"})
                    ph["Date"] = pd.to_datetime(ph["Date"]).dt.tz_localize(None)
                    ph = ph.sort_values("Date")

                    # For each price date, find most recent trailing EPS
                    eps_dates = pd.to_datetime(eps_annual.index).tz_localize(None)
                    eps_vals  = eps_annual.values

                    pe_dates, pe_vals = [], []
                    for _, row in ph.iterrows():
                        d = row["Date"]
                        # find most recent EPS reported before this date
                        mask = eps_dates <= d
                        if mask.any():
                            trailing_eps = float(eps_vals[mask][-1])
                            if trailing_eps and trailing_eps != 0:
                                pe = round(float(row["Close"]) / trailing_eps, 2)
                                if 0 < pe < 1000:  # filter outliers
                                    pe_dates.append(str(d.date()))
                                    pe_vals.append(pe)

                    if pe_dates:
                        # Pre-compute time ranges
                        today = pd.Timestamp.today().normalize()
                        days_map = {"1Y": 365, "3Y": 1095, "5Y": 1825, "10Y": 3650}
                        all_pe_ranges = {}
                        full_df = pd.DataFrame({"Date": pd.to_datetime(pe_dates), "PE": pe_vals})

                        for label in ["1Y", "3Y", "5Y", "10Y", "ALL"]:
                            if label == "ALL":
                                sub = full_df
                            else:
                                sub = full_df[full_df["Date"] >= today - pd.Timedelta(days=days_map[label])]
                            if sub.empty:
                                sub = full_df
                            all_pe_ranges[label] = {
                                "dates": [str(d.date()) for d in sub["Date"]],
                                "vals":  [round(v, 2) for v in sub["PE"]]
                            }

                        pe_json = json.dumps(all_pe_ranges)
                        cur_pe = round(float(ph["Close"].iloc[-1]) / float(eps_vals[-1]), 2) if eps_vals[-1] != 0 else None
                        avg_pe = round(sum(pe_vals) / len(pe_vals), 1)

                        pe_html = f"""<!DOCTYPE html><html><head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
    body{{font-family:-apple-system,sans-serif;margin:0;padding:8px 0 0 0;}}
    .info-row{{display:flex;gap:16px;margin-bottom:10px;flex-wrap:wrap;}}
    .info-pill{{background:#f0f0f0;border-radius:6px;padding:5px 14px;font-size:13px;font-weight:600;color:#444;}}
    .btn-row{{display:flex;gap:6px;margin-bottom:10px;}}
    .btn{{padding:5px 14px;border-radius:6px;border:1px solid #ccc;background:white;cursor:pointer;font-size:13px;font-weight:500;transition:all 0.2s;}}
    .btn.active{{background:#9b59b6;color:white;border-color:#9b59b6;}}
    .btn:hover:not(.active){{background:#f0f0f0;}}
    #peContainer{{position:relative;height:300px;transition:opacity 0.35s ease;}}
    #peContainer.fading{{opacity:0;}}
    </style></head><body>
    <div class="info-row">
      <div class="info-pill">Current P/E: <span style="color:#9b59b6;font-weight:700">{cur_pe if cur_pe else "N/A"}</span></div>
      <div class="info-pill">Historical Avg: <span style="color:#e67e22;font-weight:700">{avg_pe}</span></div>
    </div>
    <div class="btn-row" id="peBtnRow"></div>
    <div id="peContainer"><canvas id="peChart"></canvas></div>
    <script>
    const allData = {pe_json};
    let cur = "1Y";
    const labels = ["1Y","3Y","5Y","10Y","ALL"];
    const avgPe = {avg_pe};

    const btnRow = document.getElementById("peBtnRow");
    labels.forEach(l => {{
      const b = document.createElement("button");
      b.className = "btn" + (l === cur ? " active" : "");
      b.textContent = l; b.id = "pebtn_"+l;
      b.onclick = () => switchPe(l);
      btnRow.appendChild(b);
    }});

    const d0 = allData[cur];
    const ctx = document.getElementById("peChart").getContext("2d");
    const chart = new Chart(ctx, {{
      type:"line",
      data:{{
        labels: d0.dates,
        datasets:[
          {{data:d0.vals, borderColor:"#9b59b6", borderWidth:1.8, pointRadius:0, fill:true,
            backgroundColor:"rgba(155,89,182,0.08)", tension:0.2, label:"P/E"}},
          {{data:d0.dates.map(()=>avgPe), borderColor:"#e67e22", borderWidth:1.5,
            borderDash:[5,5], pointRadius:0, fill:false, label:"Avg"}}
        ]
      }},
      options:{{
        responsive:true, maintainAspectRatio:false,
        animation:{{duration:600, easing:"easeInOutQuart"}},
        interaction:{{intersect:false, mode:"index"}},
        plugins:{{
          legend:{{display:true, position:"top", labels:{{boxWidth:12,font:{{size:11}}}}}},
          tooltip:{{callbacks:{{label:c=>c.dataset.label+": "+c.parsed.y.toFixed(1)+"x"}}}}
        }},
        scales:{{
          x:{{ticks:{{maxTicksLimit:8,maxRotation:0,font:{{size:11}}}},grid:{{display:false}}}},
          y:{{ticks:{{callback:v=>v+"x",font:{{size:11}}}},grid:{{color:"rgba(0,0,0,0.05)"}}}}
        }}
      }}
    }});

    function switchPe(range){{
      if(range===cur) return;
      cur=range;
      labels.forEach(l=>{{document.getElementById("pebtn_"+l).className="btn"+(l===range?" active":"");}});
      const container=document.getElementById("peContainer");
      container.classList.add("fading");
      setTimeout(()=>{{
        const nd=allData[range];
        const newAvg = nd.vals.reduce((a,b)=>a+b,0)/nd.vals.length;
        chart.data.labels=nd.dates;
        chart.data.datasets[0].data=nd.vals;
        chart.data.datasets[1].data=nd.dates.map(()=>parseFloat(newAvg.toFixed(1)));
        chart.update();
        container.classList.remove("fading");
      }},350);
    }}
    </script></body></html>"""

                        components.html(pe_html, height=420)
                    else:
                        st.info("Not enough price/EPS data to calculate P/E history.")
                else:
                    st.info("No EPS data available to build P/E chart.")
            else:
                st.info("Insufficient data to build P/E chart.")
        except Exception as e:
            st.info(f"P/E chart unavailable: {e}")

        st.divider()

        # ── Analyst Rankings ─────────────────────────────────────────────────────
        st.header("🏢 Wall Street Analyst Consensus")
        if recs is not None and not recs.empty:
            import streamlit.components.v1 as components

            # Use last 4 rows (most recent months)
            r = recs.tail(4).copy()
            # Normalize column names to lowercase
            r.columns = [c.lower() for c in r.columns]

            def safe_int(val):
                try: return int(val)
                except: return 0

            rows = []
            for i, row in r.iterrows():
                period_raw = str(row.get('period', '')).strip()
                if period_raw == '0m':
                    label = 'This Month'
                elif period_raw == '-1m':
                    label = '1 Month Ago'
                elif period_raw == '-2m':
                    label = '2 Months Ago'
                elif period_raw == '-3m':
                    label = '3 Months Ago'
                else:
                    label = period_raw
                sb  = safe_int(row.get('strongbuy', 0))
                b   = safe_int(row.get('buy', 0))
                h   = safe_int(row.get('hold', 0))
                s   = safe_int(row.get('sell', 0))
                ss  = safe_int(row.get('strongsell', 0))
                total = sb + b + h + s + ss
                score = round((sb*5 + b*4 + h*3 + s*2 + ss*1) / total, 2) if total > 0 else 0
                rows.append({"label": label, "sb": sb, "b": b, "h": h, "s": s, "ss": ss, "total": total, "score": score})

            # Latest row for headline stats
            latest = rows[0] if rows else None
            oldest = rows[-1] if len(rows) > 1 else None

            if latest:
                total = latest["total"]
                score = latest["score"]
                if score >= 4.5:   verdict, vcolor = "Strong Buy", "#2ecc71"
                elif score >= 3.8: verdict, vcolor = "Buy",         "#27ae60"
                elif score >= 3.2: verdict, vcolor = "Hold",        "#f39c12"
                elif score >= 2.5: verdict, vcolor = "Sell",        "#e74c3c"
                else:              verdict, vcolor = "Strong Sell", "#c0392b"

                trend_arrow = ""
                trend_color = "#888"
                if oldest:
                    delta = latest["score"] - oldest["score"]
                    if delta > 0.05:   trend_arrow, trend_color = "▲ Improving", "#2ecc71"
                    elif delta < -0.05: trend_arrow, trend_color = "▼ Deteriorating", "#e74c3c"
                    else:               trend_arrow, trend_color = "→ Stable", "#f39c12"

                # Build rows JSON for the HTML table
                import json
                rows_json = json.dumps(rows)

                analyst_html = f"""
    <!DOCTYPE html><html><head>
    <style>
      body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 0; }}
      .top-row {{ display: flex; gap: 16px; align-items: stretch; margin-bottom: 20px; flex-wrap: wrap; }}
      .stat-card {{
        background: #f8f9fa; border-radius: 10px; padding: 14px 20px;
        min-width: 140px; flex: 1;
      }}
      .stat-card .label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }}
      .stat-card .value {{ font-size: 26px; font-weight: 700; }}
      .stat-card .sub {{ font-size: 12px; color: #aaa; margin-top: 2px; }}
      table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
      th {{ background: #f1f3f5; padding: 8px 12px; text-align: left; font-weight: 600; color: #555; border-bottom: 2px solid #e0e0e0; }}
      td {{ padding: 10px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
      tr:last-child td {{ border-bottom: none; }}
      tr:first-child td {{ font-weight: 600; }}
      .bar-wrap {{ display: flex; height: 14px; border-radius: 4px; overflow: hidden; width: 100%; min-width: 120px; }}
      .seg {{ height: 100%; transition: width 0.4s ease; }}
      .pill {{
        display: inline-block; padding: 2px 8px; border-radius: 10px;
        font-size: 11px; font-weight: 600; color: white;
      }}
      .sb {{ background: #1a9e5c; }} .b {{ background: #2ecc71; }}
      .h  {{ background: #f39c12; }} .s {{ background: #e74c3c; }}
      .ss {{ background: #922b21; }}
    </style>
    </head><body>

    <div class="top-row">
      <div class="stat-card">
        <div class="label">Consensus</div>
        <div class="value" style="color:{vcolor}">{verdict}</div>
        <div class="sub">{total} analysts covering</div>
      </div>
      <div class="stat-card">
        <div class="label">Analyst Score</div>
        <div class="value" style="color:{vcolor}">{score:.2f}<span style="font-size:14px;color:#aaa"> / 5.0</span></div>
        <div class="sub" style="color:{trend_color}; font-weight:600;">{trend_arrow}</div>
      </div>
      <div class="stat-card">
        <div class="label">Strong Buy / Buy</div>
        <div class="value" style="color:#2ecc71">{latest['sb'] + latest['b']}</div>
        <div class="sub">of {total} analysts</div>
      </div>
      <div class="stat-card">
        <div class="label">Hold</div>
        <div class="value" style="color:#f39c12">{latest['h']}</div>
        <div class="sub">of {total} analysts</div>
      </div>
      <div class="stat-card">
        <div class="label">Sell / Strong Sell</div>
        <div class="value" style="color:#e74c3c">{latest['s'] + latest['ss']}</div>
        <div class="sub">of {total} analysts</div>
      </div>
    </div>

    <table>
      <tr>
        <th>Period</th>
        <th>Consensus Bar</th>
        <th><span class="pill sb">Strong Buy</span></th>
        <th><span class="pill b">Buy</span></th>
        <th><span class="pill h">Hold</span></th>
        <th><span class="pill s">Sell</span></th>
        <th><span class="pill ss">Strong Sell</span></th>
        <th>Score</th>
      </tr>
      <tbody id="tbody"></tbody>
    </table>

    <script>
    const rows = {rows_json};
    const tbody = document.getElementById("tbody");
    rows.forEach((r, i) => {{
      const t = r.total || 1;
      const sbW = (r.sb/t*100).toFixed(1);
      const bW  = (r.b/t*100).toFixed(1);
      const hW  = (r.h/t*100).toFixed(1);
      const sW  = (r.s/t*100).toFixed(1);
      const ssW = (r.ss/t*100).toFixed(1);
      const scoreCol = r.score >= 4.5 ? "#1a9e5c" : r.score >= 3.8 ? "#2ecc71" : r.score >= 3.2 ? "#f39c12" : "#e74c3c";
      tbody.innerHTML += `
        <tr>
          <td>${{r.label}}</td>
          <td>
            <div class="bar-wrap">
              <div class="seg" style="width:${{sbW}}%;background:#1a9e5c;" title="Strong Buy: ${{r.sb}}"></div>
              <div class="seg" style="width:${{bW}}%;background:#2ecc71;" title="Buy: ${{r.b}}"></div>
              <div class="seg" style="width:${{hW}}%;background:#f39c12;" title="Hold: ${{r.h}}"></div>
              <div class="seg" style="width:${{sW}}%;background:#e74c3c;" title="Sell: ${{r.s}}"></div>
              <div class="seg" style="width:${{ssW}}%;background:#922b21;" title="Strong Sell: ${{r.ss}}"></div>
            </div>
          </td>
          <td style="color:#1a9e5c;font-weight:600">${{r.sb}}</td>
          <td style="color:#2ecc71;font-weight:600">${{r.b}}</td>
          <td style="color:#f39c12;font-weight:600">${{r.h}}</td>
          <td style="color:#e74c3c;font-weight:600">${{r.s}}</td>
          <td style="color:#922b21;font-weight:600">${{r.ss}}</td>
          <td style="color:${{scoreCol}};font-weight:700">${{r.score.toFixed(2)}}</td>
        </tr>`;
    }});
    </script>
    </body></html>"""

                components.html(analyst_html, height=380)
        else:
            st.info("No recent analyst data available.")

        st.divider()

        # ── Relative Performance Chart ───────────────────────────────────────────
        st.header("📊 Performance vs. S&P 500")
        try:
            import json
            import streamlit.components.v1 as components

            # Use yf.download which is more reliable for index alignment
            spy_dl = yf.download("SPY", period="max", progress=False, auto_adjust=True)
            stock_dl = hist_full[["Close"]].copy()

            # Flatten MultiIndex columns if present
            if isinstance(spy_dl.columns, pd.MultiIndex):
                spy_dl.columns = spy_dl.columns.get_level_values(0)

            spy_close   = spy_dl[["Close"]].copy()

            # Strip tz from both
            spy_close.index   = pd.to_datetime(spy_close.index).tz_localize(None).normalize()
            stock_dl.index    = pd.to_datetime(stock_dl.index).tz_localize(None).normalize()

            # Dedupe
            spy_close   = spy_close[~spy_close.index.duplicated(keep='last')]
            stock_dl    = stock_dl[~stock_dl.index.duplicated(keep='last')]

            # Merge on date so alignment is guaranteed
            merged = pd.merge(
                stock_dl.rename(columns={"Close": "stock"}),
                spy_close.rename(columns={"Close": "spy"}),
                left_index=True, right_index=True, how="inner"
            ).dropna()

            today = pd.Timestamp.today().normalize()
            range_days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "3Y": 1095, "5Y": 1825, "ALL": None}

            all_ranges = {}
            for label, days in range_days.items():
                start = today - pd.Timedelta(days=days) if days else merged.index.min()
                sub = merged[merged.index >= start]
                if len(sub) < 5:
                    continue
                s_norm = (sub["stock"] / sub["stock"].iloc[0] * 100).round(2).tolist()
                m_norm = (sub["spy"]   / sub["spy"].iloc[0]   * 100).round(2).tolist()
                dates  = [str(d.date()) for d in sub.index]
                s_ret  = round((sub["stock"].iloc[-1] / sub["stock"].iloc[0] - 1) * 100, 2)
                m_ret  = round((sub["spy"].iloc[-1]   / sub["spy"].iloc[0]   - 1) * 100, 2)
                all_ranges[label] = {"dates": dates, "stock": s_norm, "spy": m_norm,
                                     "stock_ret": s_ret, "spy_ret": m_ret}

            if all_ranges:
                ticker_label = loaded_ticker
                ranges_json  = json.dumps(all_ranges)
                default_range = "1Y" if "1Y" in all_ranges else list(all_ranges.keys())[0]

                rel_html = f"""<!DOCTYPE html><html><head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
    body{{font-family:-apple-system,sans-serif;margin:0;padding:8px 0 0 0;}}
    .top{{display:flex;gap:12px;margin-bottom:10px;flex-wrap:wrap;align-items:center;}}
    .pill{{background:#f0f0f0;border-radius:6px;padding:5px 14px;font-size:13px;font-weight:600;color:#444;}}
    .pill span{{font-weight:700;}}
    .pill.stock span{{color:#2980b9;}}
    .pill.spy span{{color:#e67e22;}}
    .pill.delta span.pos{{color:#27ae60;}}
    .pill.delta span.neg{{color:#e74c3c;}}
    .btn-row{{display:flex;gap:6px;margin-bottom:10px;}}
    .btn{{padding:5px 14px;border-radius:6px;border:1px solid #ccc;background:white;cursor:pointer;font-size:13px;font-weight:500;transition:all 0.2s;}}
    .btn.active{{background:#2980b9;color:white;border-color:#2980b9;}}
    .btn:hover:not(.active){{background:#f0f0f0;}}
    #chartWrap{{position:relative;height:320px;transition:opacity 0.35s ease;}}
    #chartWrap.fading{{opacity:0;}}
    </style></head><body>
    <div class="top">
      <div class="pill stock">📈 {ticker_label}: <span id="stockRet"></span></div>
      <div class="pill spy">📊 S&P 500: <span id="spyRet"></span></div>
      <div class="pill delta">vs Market: <span id="deltaRet"></span></div>
    </div>
    <div class="btn-row" id="btnRow"></div>
    <div id="chartWrap"><canvas id="relChart"></canvas></div>
    <script>
    const data = {ranges_json};
    let cur = "{default_range}";
    const rangeKeys = Object.keys(data);

    const btnRow = document.getElementById("btnRow");
    rangeKeys.forEach(l => {{
      const b = document.createElement("button");
      b.className = "btn" + (l === cur ? " active" : "");
      b.textContent = l; b.id = "rbtn_"+l;
      b.onclick = () => switchRange(l);
      btnRow.appendChild(b);
    }});

    function updatePills(d) {{
      const sr = d.stock_ret, mr = d.spy_ret, delta = (sr - mr).toFixed(2);
      document.getElementById("stockRet").textContent = (sr >= 0 ? "+" : "") + sr + "%";
      document.getElementById("spyRet").textContent   = (mr >= 0 ? "+" : "") + mr + "%";
      const el = document.getElementById("deltaRet");
      el.textContent = (delta >= 0 ? "+" : "") + delta + "%";
      el.className   = parseFloat(delta) >= 0 ? "pos" : "neg";
    }}

    const d0 = data[cur];
    updatePills(d0);
    const ctx = document.getElementById("relChart").getContext("2d");
    const chart = new Chart(ctx, {{
      type:"line",
      data:{{
        labels: d0.dates,
        datasets:[
          {{label:"{ticker_label}", data:d0.stock, borderColor:"#2980b9", borderWidth:2,
            pointRadius:0, fill:false, tension:0.1}},
          {{label:"S&P 500 (SPY)", data:d0.spy, borderColor:"#e67e22", borderWidth:2,
            borderDash:[5,4], pointRadius:0, fill:false, tension:0.1}}
        ]
      }},
      options:{{
        responsive:true, maintainAspectRatio:false,
        animation:{{duration:500, easing:"easeInOutQuart"}},
        interaction:{{intersect:false, mode:"index"}},
        plugins:{{
          legend:{{display:true, position:"top", labels:{{boxWidth:12,font:{{size:11}}}}}},
          tooltip:{{callbacks:{{
            label: c => c.dataset.label + ": " + (c.parsed.y - 100).toFixed(2) + "%"
          }}}}
        }},
        scales:{{
          x:{{ticks:{{maxTicksLimit:8,maxRotation:0,font:{{size:11}}}},grid:{{display:false}}}},
          y:{{
            ticks:{{callback:v=>(v-100).toFixed(0)+"%",font:{{size:11}}}},
            grid:{{color:"rgba(0,0,0,0.05)"}},
            title:{{display:true,text:"Return %",font:{{size:11}}}}
          }}
        }}
      }}
    }});

    function switchRange(range) {{
      if(range===cur) return;
      cur=range;
      rangeKeys.forEach(l=>{{document.getElementById("rbtn_"+l).className="btn"+(l===range?" active":"");}});
      const wrap=document.getElementById("chartWrap");
      wrap.classList.add("fading");
      setTimeout(()=>{{
        const nd=data[range];
        chart.data.labels=nd.dates;
        chart.data.datasets[0].data=nd.stock;
        chart.data.datasets[1].data=nd.spy;
        updatePills(nd);
        chart.update();
        wrap.classList.remove("fading");
      }},350);
    }}
    </script></body></html>"""

                components.html(rel_html, height=460)
            else:
                st.info("Not enough data to build relative performance chart.")
        except StopIteration:
            pass
        except Exception as e:
            st.error(f"Relative performance chart error: {e}")

        st.divider()

        # ── News + AI Analysis ───────────────────────────────────────────────────
        st.header("🎙️ CEO Guidance & Earnings News")
        if not groq_api_key:
            st.info("💡 Enter your Groq API key in the sidebar for AI-powered deep analysis.")

        if news_list:
            for item in news_list[:5]:
                headline, publisher, link = extract_news_fields(item)
                with st.expander(f"📰 {publisher} — {headline}"):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"**Source:** {publisher}")
                    with col_b:
                        if link != '#':
                            st.markdown(f"🔗 [Read Full Article]({link})")
                    st.divider()
                    if groq_api_key:
                        with st.spinner("🤖 Generating deep analysis..."):
                            summary = get_ai_summary(loaded_ticker, headline, publisher, groq_api_key)
                        st.markdown("### 🤖 AI Deep Analysis")
                        st.markdown(summary)
                    else:
                        st.caption("🔒 Add your Groq API key to unlock AI deep analysis.")
        else:
            st.write("No recent news found.")
