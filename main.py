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
    df = pd.read_csv(io.StringIO(CSV_DATA))
    df['Year'] = df['Year'].astype(int)
    election_years = [year for year in range(1976, 2028, 4)]
    df['Year_Type'] = df['Year'].apply(lambda x: 'Election Year' if x in election_years else 'Standard Year')
    st.sidebar.success("✅ Database Connected")
except Exception as e:
    st.sidebar.error(f"❌ Data Error: {e}")

st.sidebar.divider()
st.sidebar.header("🤖 AI News Summaries")
groq_api_key = st.sidebar.text_input(
    "Groq API Key",
    type="password",
    help="Enter your free Groq API key. Get one free at console.groq.com"
)

def extract_news_fields(news_item):
    if 'content' in news_item:
        content = news_item['content']
        headline = content.get('title', '')
        publisher = content.get('provider', {}).get('displayName', '') if isinstance(content.get('provider'), dict) else content.get('provider', '')
        link = ''
        if 'canonicalUrl' in content:
            link = content['canonicalUrl'].get('url', '')
        elif 'clickThroughUrl' in content:
            link = content['clickThroughUrl'].get('url', '')
    else:
        headline = news_item.get('title', '')
        publisher = news_item.get('publisher', '')
        link = news_item.get('link', '')
    return headline or 'No title', publisher or 'Unknown', link or '#'

def get_ai_summary(ticker, headline, publisher, api_key):
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """You are a senior Wall Street analyst writing deep-dive news analysis for institutional investors.
When given a news headline, provide a thorough, structured analysis covering:
1. What exactly happened and why it matters
2. Short-term price impact (bullish/bearish/neutral and why)
3. Long-term implications for the stock
4. Key risks or opportunities this creates
5. What investors should watch for next
Be specific, insightful, and professional. Write in paragraph form, not bullet points. Aim for 150-200 words."""
                },
                {
                    "role": "user",
                    "content": f"Ticker: {ticker}\nPublisher: {publisher}\nHeadline: {headline}\n\nProvide a deep institutional-grade analysis of this news."
                }
            ],
            max_tokens=400,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Could not generate summary: {str(e)}"

def make_annual_chart(data, title, y_label, color="#4c9be8", format_billions=True):
    if data is None or data.empty:
        return None
    data = data.reset_index()
    data.columns = ['Date', 'Value']
    data['Date'] = pd.to_datetime(data['Date']).dt.year.astype(str)
    if format_billions:
        data['Value'] = data['Value'] / 1e9
        label = f"{y_label} (B$)"
    else:
        label = y_label
    return alt.Chart(data).mark_bar(color=color).encode(
        x=alt.X('Date:O', title='Year'),
        y=alt.Y('Value:Q', title=label),
        tooltip=['Date', alt.Tooltip('Value:Q', format='.2f')]
    ).properties(height=220, padding={"top": 10})

def make_quarterly_chart(data, title, y_label, color="#4c9be8", format_billions=True):
    if data is None or data.empty:
        return None
    data = data.reset_index()
    data.columns = ['Date', 'Value']
    data['Date'] = pd.to_datetime(data['Date']).dt.to_period('Q').astype(str)
    if format_billions:
        data['Value'] = data['Value'] / 1e9
        label = f"{y_label} (B$)"
    else:
        label = y_label
    return alt.Chart(data).mark_bar(color=color, opacity=0.85).encode(
        x=alt.X('Date:O', title='Quarter'),
        y=alt.Y('Value:Q', title=label),
        tooltip=['Date', alt.Tooltip('Value:Q', format='.2f')]
    ).properties(height=220, padding={"top": 10})

ticker_input = st.text_input("Enter Ticker (e.g., NVDA, TSLA, AAPL):", "NVDA").upper()

if st.button("Generate Deep Analysis"):
    with st.spinner("Fetching data..."):
        try:
            stock = yf.Ticker(ticker_input)
            info = stock.info

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Price", f"${info.get('currentPrice', 'N/A')}")
            with col2:
                st.metric("Wall St. Target", f"${info.get('targetMeanPrice', 'N/A')}")
            with col3:
                st.metric("Forward P/E", f"{info.get('forwardPE', 'N/A')}")
            with col4:
                inst_pct = info.get('heldPercentInstitutions', 0)
                st.metric("Inst. Ownership", f"{inst_pct * 100:.1f}%" if inst_pct else "N/A")

            st.divider()

            # ── FULL PRICE HISTORY ─────────────────────────────────────────
            # ── FULL PRICE HISTORY ─────────────────────────────────────────
            st.header("📉 Price History")
            try:
                hist_full = stock.history(period="max")
                if not hist_full.empty:
                    hist_full = hist_full.reset_index()
                    hist_full["Date"] = pd.to_datetime(hist_full["Date"].dt.date)

                    # Time range buttons
                    if "price_range" not in st.session_state:
                        st.session_state["price_range"] = "1Y"

                    time_labels = ["1W", "1M", "YTD", "1Y", "5Y", "10Y", "ALL"]
                    btn_cols = st.columns(len(time_labels))
                    for i, label in enumerate(time_labels):
                        with btn_cols[i]:
                            if st.button(label, key=f"btn_{label}", type="primary" if st.session_state["price_range"] == label else "secondary"):
                                st.session_state["price_range"] = label

                    selected = st.session_state["price_range"]
                    today = pd.Timestamp.today().normalize()
                    days_map = {"1W": 7, "1M": 30, "1Y": 365, "5Y": 1825, "10Y": 3650}

                    if selected == "ALL":
                        hist_filtered = hist_full.copy()
                    elif selected == "YTD":
                        hist_filtered = hist_full[hist_full["Date"] >= pd.Timestamp(today.year, 1, 1)]
                    else:
                        hist_filtered = hist_full[hist_full["Date"] >= today - pd.Timedelta(days=days_map[selected])]

                    if hist_filtered.empty:
                        hist_filtered = hist_full.copy()

                    first_close = hist_filtered["Close"].iloc[0]
                    last_close = hist_filtered["Close"].iloc[-1]
                    line_color = "#2ecc71" if last_close >= first_close else "#e74c3c"
                    pct_change = ((last_close - first_close) / first_close) * 100
                    arrow = "▲" if pct_change >= 0 else "▼"
                    st.caption(f"{arrow} {abs(pct_change):.2f}% over selected period  |  Current: ${last_close:.2f}")

                    price_chart = alt.Chart(hist_filtered).mark_line(color=line_color, strokeWidth=1.8).encode(
                        x=alt.X("Date:T", title="Date"),
                        y=alt.Y("Close:Q", title="Price ($)", scale=alt.Scale(zero=False)),
                        tooltip=[
                            alt.Tooltip("Date:T", format="%b %d, %Y"),
                            alt.Tooltip("Close:Q", format="$.2f", title="Price")
                        ]
                    ).properties(height=350).interactive()

                    st.altair_chart(price_chart, use_container_width=True)
                    ipo_year = hist_full["Date"].dt.year.min()
                    st.caption(f"Full history available from {ipo_year} — {len(hist_full):,} trading days")
            except Exception as e:
                st.warning(f"Could not load price history: {e}")

            st.divider()

            # ── FINANCIAL KPIs ─────────────────────────────────────────────
            st.header("📊 Financial KPIs")

            try:
                financials   = stock.financials
                quarterly_fin = stock.quarterly_financials
                cashflow     = stock.cashflow
                quarterly_cf  = stock.quarterly_cashflow

                kpi_tab1, kpi_tab2 = st.tabs(["📅 Annual (4 Years)", "📆 Quarterly (4 Quarters)"])

                with kpi_tab1:
                    c1, c2 = st.columns(2)
                    with c1:
                        if financials is not None and 'Total Revenue' in financials.index:
                            c = make_annual_chart(financials.loc['Total Revenue'].sort_index(), "Annual Revenue", "Revenue", "#2ecc71")
                            if c:
                                st.subheader("Annual Revenue")
                                st.altair_chart(c, use_container_width=True)
                    with c2:
                        if financials is not None and 'Net Income' in financials.index:
                            c = make_annual_chart(financials.loc['Net Income'].sort_index(), "Net Income", "Net Income", "#3498db")
                            if c:
                                st.subheader("Net Income")
                                st.altair_chart(c, use_container_width=True)

                    c3, c4 = st.columns(2)
                    with c3:
                        eps_row = None
                        if financials is not None and 'Basic EPS' in financials.index:
                            eps_row = financials.loc['Basic EPS'].sort_index()
                            eps_label = "Basic EPS"
                        elif financials is not None and 'Diluted EPS' in financials.index:
                            eps_row = financials.loc['Diluted EPS'].sort_index()
                            eps_label = "Diluted EPS"
                        if eps_row is not None:
                            c = make_annual_chart(eps_row, eps_label, "EPS ($)", "#9b59b6", format_billions=False)
                            if c:
                                st.subheader(eps_label)
                                st.altair_chart(c, use_container_width=True)
                    with c4:
                        if cashflow is not None and 'Free Cash Flow' in cashflow.index:
                            c = make_annual_chart(cashflow.loc['Free Cash Flow'].sort_index(), "Free Cash Flow", "FCF", "#e67e22")
                            if c:
                                st.subheader("Free Cash Flow")
                                st.altair_chart(c, use_container_width=True)

                    c5, c6 = st.columns(2)
                    with c5:
                        if financials is not None and 'Gross Profit' in financials.index:
                            c = make_annual_chart(financials.loc['Gross Profit'].sort_index(), "Gross Profit", "Gross Profit", "#1abc9c")
                            if c:
                                st.subheader("Gross Profit")
                                st.altair_chart(c, use_container_width=True)
                    with c6:
                        if financials is not None and 'Operating Income' in financials.index:
                            c = make_annual_chart(financials.loc['Operating Income'].sort_index(), "Operating Income", "Operating Income", "#e74c3c")
                            if c:
                                st.subheader("Operating Income")
                                st.altair_chart(c, use_container_width=True)

                with kpi_tab2:
                    c1, c2 = st.columns(2)
                    with c1:
                        if quarterly_fin is not None and 'Total Revenue' in quarterly_fin.index:
                            c = make_quarterly_chart(quarterly_fin.loc['Total Revenue'].sort_index(), "Quarterly Revenue", "Revenue", "#2ecc71")
                            if c:
                                st.subheader("Quarterly Revenue")
                                st.altair_chart(c, use_container_width=True)
                    with c2:
                        if quarterly_fin is not None and 'Net Income' in quarterly_fin.index:
                            c = make_quarterly_chart(quarterly_fin.loc['Net Income'].sort_index(), "Quarterly Net Income", "Net Income", "#3498db")
                            if c:
                                st.subheader("Quarterly Net Income")
                                st.altair_chart(c, use_container_width=True)

                    c3, c4 = st.columns(2)
                    with c3:
                        eps_row = None
                        if quarterly_fin is not None and 'Basic EPS' in quarterly_fin.index:
                            eps_row = quarterly_fin.loc['Basic EPS'].sort_index()
                            eps_label = "Quarterly Basic EPS"
                        elif quarterly_fin is not None and 'Diluted EPS' in quarterly_fin.index:
                            eps_row = quarterly_fin.loc['Diluted EPS'].sort_index()
                            eps_label = "Quarterly Diluted EPS"
                        if eps_row is not None:
                            c = make_quarterly_chart(eps_row, eps_label, "EPS ($)", "#9b59b6", format_billions=False)
                            if c:
                                st.subheader(eps_label)
                                st.altair_chart(c, use_container_width=True)
                    with c4:
                        if quarterly_cf is not None and 'Free Cash Flow' in quarterly_cf.index:
                            c = make_quarterly_chart(quarterly_cf.loc['Free Cash Flow'].sort_index(), "Quarterly Free Cash Flow", "FCF", "#e67e22")
                            if c:
                                st.subheader("Quarterly Free Cash Flow")
                                st.altair_chart(c, use_container_width=True)

                    c5, c6 = st.columns(2)
                    with c5:
                        if quarterly_fin is not None and 'Gross Profit' in quarterly_fin.index:
                            c = make_quarterly_chart(quarterly_fin.loc['Gross Profit'].sort_index(), "Quarterly Gross Profit", "Gross Profit", "#1abc9c")
                            if c:
                                st.subheader("Quarterly Gross Profit")
                                st.altair_chart(c, use_container_width=True)
                    with c6:
                        if quarterly_fin is not None and 'Operating Income' in quarterly_fin.index:
                            c = make_quarterly_chart(quarterly_fin.loc['Operating Income'].sort_index(), "Quarterly Operating Income", "Operating Income", "#e74c3c")
                            if c:
                                st.subheader("Quarterly Operating Income")
                                st.altair_chart(c, use_container_width=True)

                # ── Key Ratios ──
                st.subheader("📋 Key Ratios & Metrics")
                k1, k2, k3, k4, k5 = st.columns(5)
                with k1:
                    st.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get('marketCap') else "N/A")
                with k2:
                    st.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A'):.1f}" if info.get('trailingPE') else "N/A")
                with k3:
                    st.metric("EV/EBITDA", f"{info.get('enterpriseToEbitda', 'N/A'):.1f}" if info.get('enterpriseToEbitda') else "N/A")
                with k4:
                    st.metric("Profit Margin", f"{info.get('profitMargins', 0)*100:.1f}%" if info.get('profitMargins') else "N/A")
                with k5:
                    st.metric("Debt/Equity", f"{info.get('debtToEquity', 'N/A'):.1f}" if info.get('debtToEquity') else "N/A")

            except Exception as e:
                st.warning(f"Could not load some financial data: {e}")

            st.divider()

            st.header("🏢 Wall Street Analyst Rankings")
            recs = stock.recommendations
            if recs is not None and not recs.empty:
                st.dataframe(recs.tail(10), use_container_width=True)
            else:
                st.info("No recent analyst firm data available for this ticker.")

            st.divider()

            st.header("📈 S&P 500 Historical Recovery Chart")
            st.write("Visualizing the 'Bottom-to-Year-End' bounce. Election years are **Red**.")

            chart_data = df.copy()
            recovery_col = 'Bottom-to-Year-End Return % (from max drawdown low)'
            chart_data = chart_data.rename(columns={recovery_col: 'Recovery'})

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

            st.header("🎙️ CEO Guidance & Earnings News")

            if not groq_api_key:
                st.info("💡 Enter your free Groq API key in the sidebar to get AI-powered deep analysis for each article.")

            news_list = stock.news
            if news_list:
                for news_item in news_list[:5]:
                    headline, publisher, link = extract_news_fields(news_item)
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
                                summary = get_ai_summary(ticker_input, headline, publisher, groq_api_key)
                            st.markdown("### 🤖 AI Deep Analysis")
                            st.markdown(summary)
                        else:
                            st.caption("🔒 Add your Groq API key in the sidebar to unlock AI deep analysis.")
            else:
                st.write("No recent news found.")

        except Exception as e:
            st.error(f"Error fetching data for {ticker_input}: {e}")
