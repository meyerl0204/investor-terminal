import yfinance as yf
import streamlit as st
import pandas as pd
import altair as alt
import io
from groq import Groq

st.set_page_config(page_title="Pro Research Terminal", layout="wide")
st.title("🏛️ Institutional Research Terminal")

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
        try:
            stock = yf.Ticker(ticker_input)
            st.session_state["stock_info"]       = stock.info
            st.session_state["hist_full"]        = stock.history(period="max")
            st.session_state["financials"]       = stock.financials
            st.session_state["quarterly_fin"]    = stock.quarterly_financials
            st.session_state["cashflow"]         = stock.cashflow
            st.session_state["quarterly_cf"]     = stock.quarterly_cashflow
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


    financials   = st.session_state["financials"]
    quarterly_fin= st.session_state["quarterly_fin"]
    cashflow     = st.session_state["cashflow"]
    quarterly_cf = st.session_state["quarterly_cf"]
    recs         = st.session_state["recommendations"]
    news_list    = st.session_state["news_list"]
    loaded_ticker= st.session_state["ticker_loaded"]

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

    # ── Price History ────────────────────────────────────────────────────────
    st.header("📊 Price History")
    if hist_full is not None and not hist_full.empty:
        import streamlit.components.v1 as components
        import json

        hist_full = hist_full.reset_index()
        hist_full["Date"] = pd.to_datetime(hist_full["Date"].dt.date)

        # Pre-compute all time ranges
        today = pd.Timestamp.today().normalize()
        days_map = {"1W": 7, "1M": 30, "1Y": 365, "5Y": 1825, "10Y": 3650}
        all_ranges = {}
        for label in ["1W", "1M", "YTD", "1Y", "5Y", "10Y", "ALL"]:
            if label == "ALL":
                hf = hist_full.copy()
            elif label == "YTD":
                hf = hist_full[hist_full["Date"] >= pd.Timestamp(today.year, 1, 1)]
            else:
                hf = hist_full[hist_full["Date"] >= today - pd.Timedelta(days=days_map[label])]
            if hf.empty:
                hf = hist_full.copy()
            all_ranges[label] = {
                "dates": [str(d) for d in hf["Date"].tolist()],
                "prices": [round(float(p), 2) for p in hf["Close"].tolist()]
            }

        ipo_year = hist_full["Date"].dt.year.min()
        trading_days = len(hist_full)
        ranges_json = json.dumps(all_ranges)
        default_range = st.session_state["price_range"]

        chart_html = f"""
<!DOCTYPE html>
<html>
<head>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  body {{ margin: 0; padding: 8px 0 0 0; background: transparent; font-family: -apple-system, sans-serif; }}
  .header-row {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
  }}
  .price-emoji {{ font-size: 22px; transition: opacity 0.3s; }}
  .pct-label {{
    font-size: 13px; color: #555; transition: opacity 0.3s;
  }}
  .pct-value {{ font-weight: 600; }}
  .btn-row {{ display: flex; gap: 6px; margin-bottom: 10px; }}
  .btn {{
    padding: 5px 14px; border-radius: 6px; border: 1px solid #ccc;
    background: white; cursor: pointer; font-size: 13px; font-weight: 500;
    transition: all 0.2s;
  }}
  .btn.active {{ background: #ff4b4b; color: white; border-color: #ff4b4b; }}
  .btn:hover:not(.active) {{ background: #f0f0f0; }}
  #chartContainer {{
    position: relative; height: 320px;
    transition: opacity 0.35s ease;
  }}
  #chartContainer.fading {{ opacity: 0; }}
</style>
</head>
<body>
<div class="header-row">
  <span class="price-emoji" id="priceEmoji">📊</span>
  <span class="pct-label" id="pctLabel">Loading...</span>
</div>
<div class="btn-row" id="btnRow"></div>
<div id="chartContainer"><canvas id="priceChart"></canvas></div>
<script>
  const allData = {ranges_json};
  let currentRange = "{default_range}";
  const labels = ["1W","1M","YTD","1Y","5Y","10Y","ALL"];

  function getPct(range) {{
    const d = allData[range];
    const first = d.prices[0];
    const last = d.prices[d.prices.length - 1];
    return ((last - first) / first) * 100;
  }}

  function updateHeader(range) {{
    const pct = getPct(range);
    const d = allData[range];
    const last = d.prices[d.prices.length - 1];
    const isUp = pct >= 0;
    const emoji = isUp ? "📈" : "📉";
    const arrow = isUp ? "▲" : "▼";
    const col = isUp ? "#2ecc71" : "#e74c3c";
    document.getElementById("priceEmoji").textContent = emoji;
    document.getElementById("pctLabel").innerHTML =
      `<span class="pct-value" style="color:${{col}}">${{arrow}} ${{Math.abs(pct).toFixed(2)}}%</span> over selected period &nbsp;|&nbsp; Current: <strong>$${{last.toFixed(2)}}</strong>`;
  }}

  // Build buttons
  const btnRow = document.getElementById("btnRow");
  labels.forEach(l => {{
    const b = document.createElement("button");
    b.className = "btn" + (l === currentRange ? " active" : "");
    b.textContent = l;
    b.onclick = () => switchRange(l);
    b.id = "btn_" + l;
    btnRow.appendChild(b);
  }});

  // Init chart
  const d0 = allData[currentRange];
  const isUp0 = d0.prices[d0.prices.length-1] >= d0.prices[0];
  updateHeader(currentRange);

  const ctx = document.getElementById("priceChart").getContext("2d");
  const chart = new Chart(ctx, {{
    type: "line",
    data: {{
      labels: d0.dates,
      datasets: [{{
        data: d0.prices,
        borderColor: isUp0 ? "#2ecc71" : "#e74c3c",
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        backgroundColor: isUp0 ? "rgba(46,204,113,0.08)" : "rgba(231,76,60,0.08)",
        tension: 0.3
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      animation: {{ duration: 600, easing: "easeInOutQuart" }},
      interaction: {{ intersect: false, mode: "index" }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: ctx => "$" + ctx.parsed.y.toFixed(2),
            title: ctx => ctx[0].label
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ maxTicksLimit: 8, maxRotation: 0, font: {{ size: 11 }} }},
          grid: {{ display: false }}
        }},
        y: {{
          ticks: {{ callback: v => "$" + v.toFixed(0), font: {{ size: 11 }} }},
          grid: {{ color: "rgba(0,0,0,0.05)" }}
        }}
      }}
    }}
  }});

  function switchRange(range) {{
    if (range === currentRange) return;
    currentRange = range;
    labels.forEach(l => {{
      document.getElementById("btn_" + l).className = "btn" + (l === range ? " active" : "");
    }});
    const container = document.getElementById("chartContainer");
    container.classList.add("fading");
    setTimeout(() => {{
      const nd = allData[range];
      const up = nd.prices[nd.prices.length-1] >= nd.prices[0];
      const col = up ? "#2ecc71" : "#e74c3c";
      const fill = up ? "rgba(46,204,113,0.08)" : "rgba(231,76,60,0.08)";
      chart.data.labels = nd.dates;
      chart.data.datasets[0].data = nd.prices;
      chart.data.datasets[0].borderColor = col;
      chart.data.datasets[0].backgroundColor = fill;
      chart.update();
      updateHeader(range);
      container.classList.remove("fading");
    }}, 350);
  }}
</script>
</body>
</html>"""

        components.html(chart_html, height=460)
        st.caption(f"Full history available from {ipo_year} — {trading_days:,} trading days")

    st.divider()

    # ── Financial KPIs ───────────────────────────────────────────────────────
    st.header("📊 Financial KPIs")
    kpi_tab1, kpi_tab2 = st.tabs(["📅 Annual (4 Years)", "📆 Quarterly (4 Quarters)"])

    with kpi_tab1:
        c1, c2 = st.columns(2)
        with c1:
            if financials is not None and 'Total Revenue' in financials.index:
                ch, bg = bar_chart(financials.loc['Total Revenue'].sort_index(), "Revenue", "#2ecc71")
                if ch:
                    st.subheader("Annual Revenue")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        with c2:
            if financials is not None and 'Net Income' in financials.index:
                ch, bg = bar_chart(financials.loc['Net Income'].sort_index(), "Net Income", "#3498db")
                if ch:
                    st.subheader("Net Income")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        c3, c4 = st.columns(2)
        with c3:
            eps_row, eps_lbl = None, ""
            if financials is not None and 'Basic EPS' in financials.index:
                eps_row, eps_lbl = financials.loc['Basic EPS'].sort_index(), "Basic EPS"
            elif financials is not None and 'Diluted EPS' in financials.index:
                eps_row, eps_lbl = financials.loc['Diluted EPS'].sort_index(), "Diluted EPS"
            if eps_row is not None:
                ch, bg = bar_chart(eps_row, "EPS ($)", "#9b59b6", format_billions=False)
                if ch:
                    st.subheader(eps_lbl)
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        with c4:
            if cashflow is not None and 'Free Cash Flow' in cashflow.index:
                ch, bg = bar_chart(cashflow.loc['Free Cash Flow'].sort_index(), "FCF", "#e67e22")
                if ch:
                    st.subheader("Free Cash Flow")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        c5, c6 = st.columns(2)
        with c5:
            if financials is not None and 'Gross Profit' in financials.index:
                ch, bg = bar_chart(financials.loc['Gross Profit'].sort_index(), "Gross Profit", "#1abc9c")
                if ch:
                    st.subheader("Gross Profit")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        with c6:
            if financials is not None and 'Operating Income' in financials.index:
                ch, bg = bar_chart(financials.loc['Operating Income'].sort_index(), "Operating Income", "#e74c3c")
                if ch:
                    st.subheader("Operating Income")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        # Shares Outstanding (annual from balance sheet)
        c7, c8 = st.columns(2)
        with c7:
            shares_data = None
            for shares_key in ['Ordinary Shares Number', 'Share Issued', 'Common Stock']:
                try:
                    bs = stock.balance_sheet
                    if bs is not None and shares_key in bs.index:
                        shares_data = bs.loc[shares_key].sort_index()
                        break
                except: pass
            if shares_data is not None and not shares_data.empty:
                ch, bg = bar_chart(shares_data, "Shares", "#e91e8c", format_billions=True)
                if ch:
                    st.subheader("Shares Outstanding")
                    st.altair_chart(ch, use_container_width=True)
                    # For shares, decreasing = buybacks = good (green), increasing = dilution = bad
                    if len(bg) > 0:
                        buyback_badges = []
                        for lbl, pct in bg:
                            if pct < -2:
                                buyback_badges.append((lbl + " Buybacks ▼", abs(pct), True))
                            elif pct > 2:
                                buyback_badges.append((lbl + " Dilution ▲", pct, False))
                            else:
                                buyback_badges.append((lbl + " Stable", abs(pct), None))
                        badge_html = '<div style="display:flex;gap:8px;margin-top:6px;margin-bottom:14px;flex-wrap:wrap;">'
                        for label, pct, good in buyback_badges:
                            if good is True:   color = "#27ae60"; bg_c = "#eafaf1"
                            elif good is False: color = "#e74c3c"; bg_c = "#fdf0ef"
                            else:               color = "#888";    bg_c = "#f0f0f0"
                            badge_html += (f'<div style="background:{bg_c};border:1px solid {color};border-radius:6px;'
                                          f'padding:4px 12px;font-size:13px;font-weight:600;color:{color};">'
                                          f'{label} ({pct:.1f}%)</div>')
                        badge_html += '</div>'
                        st.markdown(badge_html, unsafe_allow_html=True)

    with kpi_tab2:
        c1, c2 = st.columns(2)
        with c1:
            if quarterly_fin is not None and 'Total Revenue' in quarterly_fin.index:
                ch, bg = bar_chart(quarterly_fin.loc['Total Revenue'].sort_index(), "Revenue", "#2ecc71", quarterly=True)
                if ch:
                    st.subheader("Quarterly Revenue")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        with c2:
            if quarterly_fin is not None and 'Net Income' in quarterly_fin.index:
                ch, bg = bar_chart(quarterly_fin.loc['Net Income'].sort_index(), "Net Income", "#3498db", quarterly=True)
                if ch:
                    st.subheader("Quarterly Net Income")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        c3, c4 = st.columns(2)
        with c3:
            eps_row, eps_lbl = None, ""
            if quarterly_fin is not None and 'Basic EPS' in quarterly_fin.index:
                eps_row, eps_lbl = quarterly_fin.loc['Basic EPS'].sort_index(), "Quarterly Basic EPS"
            elif quarterly_fin is not None and 'Diluted EPS' in quarterly_fin.index:
                eps_row, eps_lbl = quarterly_fin.loc['Diluted EPS'].sort_index(), "Quarterly Diluted EPS"
            if eps_row is not None:
                ch, bg = bar_chart(eps_row, "EPS ($)", "#9b59b6", format_billions=False, quarterly=True)
                if ch:
                    st.subheader(eps_lbl)
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        with c4:
            if quarterly_cf is not None and 'Free Cash Flow' in quarterly_cf.index:
                ch, bg = bar_chart(quarterly_cf.loc['Free Cash Flow'].sort_index(), "FCF", "#e67e22", quarterly=True)
                if ch:
                    st.subheader("Quarterly Free Cash Flow")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        c5, c6 = st.columns(2)
        with c5:
            if quarterly_fin is not None and 'Gross Profit' in quarterly_fin.index:
                ch, bg = bar_chart(quarterly_fin.loc['Gross Profit'].sort_index(), "Gross Profit", "#1abc9c", quarterly=True)
                if ch:
                    st.subheader("Quarterly Gross Profit")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        with c6:
            if quarterly_fin is not None and 'Operating Income' in quarterly_fin.index:
                ch, bg = bar_chart(quarterly_fin.loc['Operating Income'].sort_index(), "Operating Income", "#e74c3c", quarterly=True)
                if ch:
                    st.subheader("Quarterly Operating Income")
                    st.altair_chart(ch, use_container_width=True)
                    render_growth_badges(bg)
        # Quarterly shares outstanding
        c7, c8 = st.columns(2)
        with c7:
            q_shares_data = None
            for shares_key in ['Ordinary Shares Number', 'Share Issued', 'Common Stock']:
                try:
                    qbs = stock.quarterly_balance_sheet
                    if qbs is not None and shares_key in qbs.index:
                        q_shares_data = qbs.loc[shares_key].sort_index()
                        break
                except: pass
            if q_shares_data is not None and not q_shares_data.empty:
                ch, bg = bar_chart(q_shares_data, "Shares", "#e91e8c", format_billions=True, quarterly=True)
                if ch:
                    st.subheader("Shares Outstanding (Quarterly)")
                    st.altair_chart(ch, use_container_width=True)
                    if len(bg) > 0:
                        buyback_badges = []
                        for lbl, pct in bg:
                            if pct < -2:    buyback_badges.append((lbl + " Buybacks ▼", abs(pct), True))
                            elif pct > 2:   buyback_badges.append((lbl + " Dilution ▲", pct, False))
                            else:           buyback_badges.append((lbl + " Stable", abs(pct), None))
                        badge_html = '<div style="display:flex;gap:8px;margin-top:6px;margin-bottom:14px;flex-wrap:wrap;">'
                        for label, pct, good in buyback_badges:
                            if good is True:    color = "#27ae60"; bg_c = "#eafaf1"
                            elif good is False: color = "#e74c3c"; bg_c = "#fdf0ef"
                            else:               color = "#888";    bg_c = "#f0f0f0"
                            badge_html += (f'<div style="background:{bg_c};border:1px solid {color};border-radius:6px;'
                                          f'padding:4px 12px;font-size:13px;font-weight:600;color:{color};">'
                                          f'{label} ({pct:.1f}%)</div>')
                        badge_html += '</div>'
                        st.markdown(badge_html, unsafe_allow_html=True)

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
    pfcf         = (price * shares_out / fcf) if (price and shares_out and fcf and fcf != 0) else None

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
    if div_yield and div_yield > 0:
        if div_yield >= 0.05:   dy_b = badge("High Yield",  "#1a9e5c", "#e8f8f2")
        elif div_yield >= 0.02: dy_b = badge("Solid Yield", "#27ae60", "#eafaf1")
        else:                   dy_b = badge("Low Yield",   "#f39c12", "#fef9e7")
        dy_val = f"{div_yield*100:.2f}%"
    else:
        dy_b = badge("No Dividend", "#95a5a6", "#f0f0f0")
        dy_val = "—"

    # Payout Ratio
    if payout_ratio and payout_ratio > 0 and div_yield and div_yield > 0:
        if payout_ratio <= 0.35:   pr_b = badge("Sustainable",  "#1a9e5c", "#e8f8f2")
        elif payout_ratio <= 0.60: pr_b = badge("Healthy",      "#27ae60", "#eafaf1")
        elif payout_ratio <= 0.80: pr_b = badge("Stretched",    "#f39c12", "#fef9e7")
        else:                      pr_b = badge("Unsustainable","#e74c3c", "#fdf0ef")
        pr_val = f"{payout_ratio*100:.0f}%"
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
        card("EV / EBITDA",        ev_val,      ev_b,                      "#e67e22") +
        card("Profit Margin",      mg_val,      mg_b,                      "#2ecc71") +
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

    components.html(metrics_html, height=420)
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
                ph["Date"] = pd.to_datetime(ph["Date"].dt.date if hasattr(ph["Date"].dt, "date") else ph["Date"])
                ph = ph.sort_values("Date")

                # For each price date, find most recent trailing EPS
                eps_dates = pd.to_datetime(eps_annual.index)
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

    # ── S&P 500 Recovery Chart ───────────────────────────────────────────────
    st.header("📈 S&P 500 Historical Recovery Chart")
    st.write("Visualizing the 'Bottom-to-Year-End' bounce. Election years are **Red**.")
    recovery_col = 'Bottom-to-Year-End Return % (from max drawdown low)'
    chart_data = spx_df.rename(columns={recovery_col: 'Recovery'})
    recovery_chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Year:O', title='Year'),
        y=alt.Y('Recovery:Q', title='Recovery % from Low'),
        color=alt.Color('Year_Type:N',
                        scale=alt.Scale(domain=['Election Year', 'Standard Year'],
                                        range=['#ff4b4b', '#31333f']),
                        title="Market Type"),
        tooltip=['Year', 'Recovery', 'Year_Type']
    ).properties(height=400)
    st.altair_chart(recovery_chart, use_container_width=True)

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
