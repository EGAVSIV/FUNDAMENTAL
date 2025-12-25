import streamlit as st
import pandas as pd
import plotly.express as px
import io
import time
from tradingview_screener import Query, Column as col
from typing import Optional
import requests

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="🇮🇳 Indian Fundamental Screener Pro",
    layout="wide",
    page_icon="📊"
)

st.title("📊 Indian Fundamental Screener Pro")
st.caption("Stable • Cloud-safe • TradingView Powered")

# ==================================================
# SIDEBAR CONTROLS
# ==================================================
st.sidebar.header("⚙️ Controls")

PRESETS = {
    "None": None,
    "Top Gainers": "gainers",
    "Biggest Losers": "losers",
    "Large Cap": "large_cap",
    "Small Cap": "small_cap",
    "Highest Revenue": "highest_revenue",
}

preset = PRESETS[st.sidebar.selectbox("Preset", PRESETS.keys())]
limit = st.sidebar.slider("Stocks to Scan", 20, 120, 60)
min_roe = st.sidebar.slider("Min ROE %", 0, 30, 10)
min_pe, max_pe = st.sidebar.slider("PE Range", 0, 80, (5, 40))
max_debt = st.sidebar.number_input("Max Debt (₹ Cr)", value=50000)

run = st.sidebar.button("🚀 Run Screener")

# ==================================================
# SAFE API CALL WRAPPER
# ==================================================
def safe_query(q: Query) -> pd.DataFrame:
    try:
        _, df = q.get_scanner_data(timeout=30)
        return df
    except requests.exceptions.HTTPError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# ==================================================
# STEP 1 — BASE SCREENER (PRESET SAFE)
# ==================================================
def fetch_base(preset: Optional[str], limit: int) -> pd.DataFrame:
    q = (
        Query()
        .set_markets("india")
        .select(
            "name",
            "sector",
            "market_cap_basic",
            "price_earnings_ttm",
            "return_on_equity",
            "close",
            "change",
            "volume",
        )
        .where(
            col("type") == "stock",
            col("typespecs").has("common"),
            col("is_primary") == True,
        )
        .limit(limit)
    )

    if preset:
        q = q.set_property("preset", preset)

    return safe_query(q)

# ==================================================
# STEP 2 — FUNDAMENTAL ENRICHMENT (NO PRESET)
# ==================================================
def enrich_fundamentals(names: list[str]) -> pd.DataFrame:
    q = (
        Query()
        .set_markets("india")
        .select(
            "name",
            "total_revenue_ttm",
            "net_income_ttm",
            "operating_income",
            "total_assets",
            "total_current_liabilities",
            "total_debt",
            "net_debt",
            "free_cash_flow_ttm",
            "book_value_per_share_fq",
            "return_on_assets",
        )
        .where(col("name").isin(names))
        .limit(len(names))
    )

    return safe_query(q)

# ==================================================
# MAIN EXECUTION
# ==================================================
if run:

    with st.spinner("Scanning Indian Markets (Safe Mode)..."):
        base_df = fetch_base(preset, limit)
        time.sleep(1)  # rate-limit safety

    if base_df.empty:
        st.error("TradingView rejected request. Try smaller limit or no preset.")
        st.stop()

    # Apply basic filters locally
    base_df = base_df[
        (base_df["return_on_equity"] >= min_roe)
        & (base_df["price_earnings_ttm"].between(min_pe, max_pe))
    ]

    names = base_df["name"].tolist()

    with st.spinner("Fetching Financial Statements..."):
        fund_df = enrich_fundamentals(names)

    df = base_df.merge(fund_df, on="name", how="left")

    # ==================================================
    # DERIVED METRICS
    # ==================================================
    df["ROCE %"] = (
        df["operating_income"]
        / (df["total_assets"] - df["total_current_liabilities"])
    ) * 100

    df["Market Cap (₹ Cr)"] = df["market_cap_basic"] / 1e7
    df["Revenue (₹ Cr)"] = df["total_revenue_ttm"] / 1e7
    df["Debt (₹ Cr)"] = df["total_debt"] / 1e7

    df = df[df["Debt (₹ Cr)"] <= max_debt]

    # ==================================================
    # FUNDAMENTAL SCORE (0–100)
    # ==================================================
    df["Fundamental Score"] = (
        df["return_on_equity"].rank(pct=True) * 30 +
        df["ROCE %"].rank(pct=True) * 30 +
        (1 / df["price_earnings_ttm"]).rank(pct=True) * 20 +
        df["free_cash_flow_ttm"].rank(pct=True) * 20
    ).round(1)

    # ==================================================
    # TABLE
    # ==================================================
    st.subheader("📋 Screener Results")

    st.dataframe(
        df.sort_values("Fundamental Score", ascending=False)[
            [
                "name", "sector", "Market Cap (₹ Cr)", "Revenue (₹ Cr)",
                "price_earnings_ttm", "return_on_equity",
                "ROCE %", "Debt (₹ Cr)", "Fundamental Score"
            ]
        ].style
        .background_gradient(subset=["Fundamental Score"], cmap="RdYlGn"),
        use_container_width=True
    )

    # ==================================================
    # CHARTS
    # ==================================================
    st.subheader("📊 Visual Intelligence")

    c1, c2 = st.columns(2)

    c1.plotly_chart(
        px.scatter(
            df,
            x="return_on_equity",
            y="ROCE %",
            size="Market Cap (₹ Cr)",
            color="sector",
            hover_name="name",
            title="ROE vs ROCE Efficiency Map",
        ),
        use_container_width=True
    )

    sector_avg = df.groupby("sector")["Fundamental Score"].mean().reset_index()
    c2.plotly_chart(
        px.bar(
            sector_avg,
            x="sector",
            y="Fundamental Score",
            color="Fundamental Score",
            title="Sector-wise Fundamental Strength",
        ),
        use_container_width=True
    )

    st.plotly_chart(
        px.pie(
            df.nlargest(10, "Revenue (₹ Cr)"),
            names="name",
            values="Revenue (₹ Cr)",
            hole=0.45,
            title="Top Revenue Contributors",
        ),
        use_container_width=True
    )

    # ==================================================
    # EXPORT
    # ==================================================
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)

    st.download_button(
        "⬇️ Download Excel",
        buffer.getvalue(),
        "india_fundamental_screener.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.caption("Stable on Streamlit Cloud • Designed for Serious Investors")
