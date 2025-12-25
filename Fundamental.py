import streamlit as st
import pandas as pd
import plotly.express as px
import io
from tradingview_screener import Query, Column as col
from typing import Optional

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="🇮🇳 Indian Fundamental Intelligence",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Indian Stock Fundamental Intelligence Dashboard")
st.caption("Income Statement • Balance Sheet • Cash Flow • Smart Scoring")

# =============================
# SIDEBAR CONTROLS
# =============================
st.sidebar.header("⚙️ Controls")

PRESETS = {
    "None": None,
    "Top Gainers": "gainers",
    "Biggest Losers": "losers",
    "Large Cap": "large_cap",
    "Small Cap": "small_cap",
    "Highest Revenue": "highest_revenue",
    "High Dividend": "high_dividend",
}

preset = PRESETS[st.sidebar.selectbox("TradingView Preset", PRESETS.keys())]

period = st.sidebar.radio("Financial Period", ["TTM", "Quarterly"])

min_pe, max_pe = st.sidebar.slider("PE Range", 0, 80, (5, 40))
min_roe = st.sidebar.slider("Min ROE %", 0, 30, 10)
max_debt = st.sidebar.number_input("Max Total Debt (₹ Cr)", value=50000)
limit = st.sidebar.slider("No. of Stocks", 20, 300, 100)

run = st.sidebar.button("🚀 Run Screener")

# =============================
# DATA FETCH
# =============================
def fetch_data(preset: Optional[str]) -> pd.DataFrame:

    q = (
        Query()
        .set_markets("india")
        .select(
            "name",
            "sector",
            "market_cap_basic",
            "total_revenue_ttm",
            "net_income_ttm",
            "operating_income",
            "price_earnings_ttm",
            "return_on_equity",
            "return_on_assets",
            "total_assets",
            "total_current_liabilities",
            "total_debt",
            "net_debt",
            "free_cash_flow_ttm",
            "book_value_per_share_fq",
            "close",
            "change",
            "volume",
        )
        .where(
            col("type") == "stock",
            col("typespecs").has("common"),
            col("is_primary") == True,
            col("price_earnings_ttm").between(min_pe, max_pe),
            col("return_on_equity") >= min_roe,
            col("total_debt") <= max_debt * 1e7,
        )
        .limit(limit)
    )

    if preset:
        q = q.set_property("preset", preset)

    _, df = q.get_scanner_data()
    return df

# =============================
# MAIN LOGIC
# =============================
if run:

    with st.spinner("Fetching & Processing Data..."):
        df = fetch_data(preset)

    if df.empty:
        st.warning("No stocks matched criteria.")
        st.stop()

    # =============================
    # DERIVED METRICS
    # =============================
    df["ROCE %"] = (
        df["operating_income"]
        / (df["total_assets"] - df["total_current_liabilities"])
    ) * 100

    df["Market Cap (₹ Cr)"] = df["market_cap_basic"] / 1e7
    df["Revenue (₹ Cr)"] = df["total_revenue_ttm"] / 1e7

    # =============================
    # FUNDAMENTAL SCORE (0–100)
    # =============================
    df["Fundamental Score"] = (
        df["return_on_equity"].rank(pct=True) * 30 +
        df["ROCE %"].rank(pct=True) * 30 +
        (1 / df["price_earnings_ttm"]).rank(pct=True) * 20 +
        df["free_cash_flow_ttm"].rank(pct=True) * 20
    ).round(1)

    # =============================
    # MAIN TABLE
    # =============================
    st.subheader("📋 Screener Results")

    styled = df[
        [
            "name", "sector", "Market Cap (₹ Cr)", "Revenue (₹ Cr)",
            "price_earnings_ttm", "return_on_equity", "ROCE %",
            "total_debt", "Fundamental Score"
        ]
    ].sort_values("Fundamental Score", ascending=False)

    st.dataframe(
        styled.style
        .background_gradient(subset=["Fundamental Score"], cmap="RdYlGn")
        .background_gradient(subset=["return_on_equity", "ROCE %"], cmap="Greens"),
        use_container_width=True
    )

    # =============================
    # CHARTS
    # =============================
    st.subheader("📊 Visual Intelligence")

    c1, c2 = st.columns(2)

    # ROE vs ROCE Scatter
    fig_scatter = px.scatter(
        df,
        x="return_on_equity",
        y="ROCE %",
        size="Market Cap (₹ Cr)",
        color="sector",
        hover_name="name",
        title="ROE vs ROCE (Efficiency Map)",
    )
    c1.plotly_chart(fig_scatter, use_container_width=True)

    # Sector Comparison
    sector_df = df.groupby("sector")["Fundamental Score"].mean().reset_index()
    fig_sector = px.bar(
        sector_df,
        x="sector",
        y="Fundamental Score",
        title="Sector-wise Average Fundamental Score",
        color="Fundamental Score",
        color_continuous_scale="Viridis",
    )
    c2.plotly_chart(fig_sector, use_container_width=True)

    # Debt vs Market Cap
    fig_debt = px.scatter(
        df,
        x="Market Cap (₹ Cr)",
        y="total_debt",
        color="Fundamental Score",
        hover_name="name",
        title="Debt vs Market Cap",
    )
    st.plotly_chart(fig_debt, use_container_width=True)

    # Donut Chart – Revenue Share
    top_rev = df.nlargest(10, "Revenue (₹ Cr)")
    fig_donut = px.pie(
        top_rev,
        names="name",
        values="Revenue (₹ Cr)",
        hole=0.5,
        title="Top 10 Revenue Contribution",
    )
    st.plotly_chart(fig_donut, use_container_width=True)

    # =============================
    # STOCK DEEP DIVE
    # =============================
    st.subheader("🔍 Stock Deep Dive")

    selected = st.selectbox("Select Stock", df["name"].unique())
    s = df[df["name"] == selected].iloc[0]

    d1, d2, d3 = st.columns(3)

    d1.metric("Market Cap (₹ Cr)", round(s["Market Cap (₹ Cr)"], 2))
    d1.metric("PE Ratio", round(s.price_earnings_ttm, 2))
    d1.metric("Book Value / Share", round(s.book_value_per_share_fq, 2))

    d2.metric("ROE %", round(s.return_on_equity, 2))
    d2.metric("ROCE %", round(s["ROCE %"], 2))
    d2.metric("ROA %", round(s.return_on_assets, 2))

    d3.metric("Total Debt (₹ Cr)", round(s.total_debt / 1e7, 2))
    d3.metric("Net Debt (₹ Cr)", round(s.net_debt / 1e7, 2))
    d3.metric("Fundamental Score", round(s["Fundamental Score"], 1))

    # =============================
    # EXPORT
    # =============================
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Fundamentals")

    st.download_button(
        "⬇️ Download Excel",
        data=buffer.getvalue(),
        file_name="india_fundamental_intelligence.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("---")
    st.caption("Built for serious investors • Data via TradingView • Python + Streamlit")
