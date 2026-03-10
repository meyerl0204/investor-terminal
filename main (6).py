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
    if format_billions:
        data['Value'] = data['Value'] / 1e9
        label = f"{y_label} (B$)"
    else:
        label = y_label

    # Calculate growth badges
    growth_badges = []
    vals = data['Value'].tolist()
    n = len(vals)
    latest = vals[-1]
    periods = [(1, "1Q"), (2, "2Q"), (3, "3Q")] if quarterly else [(1, "1Y"), (2, "2Y"), (3, "3Y")]
    for steps, lbl in periods:
        idx = n - 1 - steps
        if idx >= 0 and vals[idx] != 0:
            pct = ((latest - vals[idx]) / abs(vals[idx])) * 100
            growth_badges.append((lbl, pct))

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
ticker_input = st.text_input("Enter Ticker (e.g., NVDA, TSLA, AAPL):", "NVDA").upper()

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
        st.metric("Forward P/E", f"{info.get('forwardPE', 'N/A')}")
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

    # ── Key Ratios ──
    st.subheader("📋 Key Ratios & Metrics")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Market Cap", f"${info.get('marketCap',0)/1e9:.1f}B" if info.get('marketCap') else "N/A")
    with k2:
        st.metric("P/E Ratio", f"{info.get('trailingPE'):.1f}" if info.get('trailingPE') else "N/A")
    with k3:
        st.metric("EV/EBITDA", f"{info.get('enterpriseToEbitda'):.1f}" if info.get('enterpriseToEbitda') else "N/A")
    with k4:
        st.metric("Profit Margin", f"{info.get('profitMargins',0)*100:.1f}%" if info.get('profitMargins') else "N/A")
    with k5:
        st.metric("Debt/Equity", f"{info.get('debtToEquity'):.1f}" if info.get('debtToEquity') else "N/A")

    st.divider()

    # ── Analyst Rankings ─────────────────────────────────────────────────────
    st.header("🏢 Wall Street Analyst Rankings")
    if recs is not None and not recs.empty:
        st.dataframe(recs.tail(10), use_container_width=True)
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
