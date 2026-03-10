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
    help="Enter your free Groq API key to enable AI news summaries. Get one free at console.groq.com"
)

def get_ai_summary(ticker, headline, publisher, api_key):
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise financial analyst. Summarize news headlines in 2-3 sentences from an investor's perspective. Focus on potential stock price impact, earnings implications, or sentiment shifts. Be factual and professional."
                },
                {
                    "role": "user",
                    "content": f"Ticker: {ticker}\nPublisher: {publisher}\nHeadline: {headline}\n\nProvide a brief investor-focused summary in under 60 words."
                }
            ],
            max_tokens=150,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Could not generate summary: {str(e)}"

ticker = st.text_input("Enter Ticker (e.g., NVDA, TSLA, AAPL):", "NVDA").upper()

if st.button("Generate Deep Analysis"):
    with st.spinner("Fetching data..."):
        try:
            stock = yf.Ticker(ticker)
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
                st.info("💡 Enter your free Groq API key in the sidebar to get AI-powered summaries for each article.")

            news_list = stock.news
            if news_list:
                for news in news_list[:5]:
                    headline = news.get('title', 'Article')
                    publisher = news.get('publisher', 'News')
                    link = news.get('link', '#')

                    with st.expander(f"📰 {publisher} — {headline}"):
                        st.markdown(f"🔗 [Read Full Article]({link})")
                        st.divider()

                        if groq_api_key:
                            with st.spinner("🤖 Generating AI summary..."):
                                summary = get_ai_summary(ticker, headline, publisher, groq_api_key)
                            st.markdown("**🤖 AI Investor Summary:**")
                            st.info(summary)
                        else:
                            st.caption("🔒 Add your Groq API key in the sidebar to unlock AI summaries.")

                        st.caption("💡 Nerd Note: Scan for phrases like 'Quarterly Outlook' or 'CEO Comments'.")
            else:
                st.write("No recent news found.")

        except Exception as e:
            st.error(f"Error fetching data for {ticker}: {e}")
