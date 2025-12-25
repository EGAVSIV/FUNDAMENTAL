import streamlit as st
import pandas as pd
from tradingview_screener import Query, Column as col
from typing import Optional
import io
import requests

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="🇮🇳 Indian Fundamental Stock Screener",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Indian Stock Fundamental Screener")
st.caption("Powered by TradingView Screener | NSE + BSE")

# ==================================================
# SIDEBAR – PRESETS
# ==================================================
PRESETS = {
    "None": None,
    "Top Gainers": "gainers",
    "Biggest Losers": "losers",
    "Large Cap": "large_cap",
    "Small Cap": "small_cap",
    "Highest Revenue": "highest_revenue",
    "Highest Net Income": "highest_net_income",
    "High Dividend": "high_dividend",
    "Most Active": "most_active",
    "Unusual Volume": "unusual_volume",
}

st.sidebar.header("📌 Preset Filters")
preset_label = st.sidebar.selectbox("Select Preset", PRESETS.keys())
preset_value = PRESETS[preset_label]

# ==================================================
# FUNDAMENTAL FILTERS
# ==================================================
st.sidebar.header("📈 Fundamental Filters")

min_mcap = st.sidebar.number_input("Min Market Cap (₹ Cr)", min_value=0, value=500)
max_pe = st.sidebar.number_input("Max PE Ratio", min_value=0.0, value=40.0)
min_roe = st.sidebar.number_input("Min ROE (%)", min_value=0.0, value=10.0)
min_roa = st.sidebar.number_input("Min ROA (%)", min_value=0.0, value=5.0)
min_dividend = st.sidebar.number_input("Min Dividend Yield (%)", min_value=0.0, value=0.0)
min_revenue = st.sidebar.number_input("Min Revenue (₹ Cr)", min_value=0, value=1000)

limit = st.sidebar.slider("Number of Stocks", 10, 200, 50)

run_scan = st.sidebar.button("🚀 Run Screener")

# ==================================================
# SAFE SCREENER FUNCTION
# ==================================================
def run_fundamental_scan(preset: Optional[str]) -> pd.DataFrame:
    try:
        q = (
            Query()
            .set_markets("india")
            .select(
                "name",
                "sector",
                "market_cap_basic",
                "total_revenue_ttm",
                "net_income_ttm",
                "price_earnings_ttm",
                "return_on_equity",
                "return_on_assets",
                "dividends_yield_current",
                "close",
                "change",
                "volume",
            )
            .where(
                col("type") == "stock",
                col("typespecs").has("common"),
                col("is_primary") == True,
                col("market_cap_basic") >= min_mcap * 1e7,
                col("total_revenue_ttm") >= min_revenue * 1e7,
                col("price_earnings_ttm") <= max_pe,
                col("return_on_equity") >= min_roe,
                col("return_on_assets") >= min_roa,
                col("dividends_yield_current") >= min_dividend,
            )
            .order_by("market_cap_basic", ascending=False)
            .limit(limit)
        )

        if preset:
            q = q.set_property("preset", preset)

        _, df = q.get_scanner_data(timeout=30)
        return df

    except requests.exceptions.HTTPError:
        st.error("TradingView rejected the request. Reduce filters or stock count.")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return pd.DataFrame()

# ==================================================
# MAIN OUTPUT
# ==================================================
if run_scan:

    with st.spinner("Scanning Indian Markets..."):
        df = run_fundamental_scan(preset_value)

    if df.empty:
        st.warning("No stocks matched the criteria.")
    else:
        # =========================
        # DATA FORMATTING
        # =========================
        df["Market Cap (₹ Cr)"] = df["market_cap_basic"] / 1e7
        df["Revenue (₹ Cr)"] = df["total_revenue_ttm"] / 1e7

        display_cols = [
            "name",
            "sector",
            "Market Cap (₹ Cr)",
            "Revenue (₹ Cr)",
            "net_income_ttm",
            "price_earnings_ttm",
            "return_on_equity",
            "return_on_assets",
            "dividends_yield_current",
            "close",
            "change",
            "volume",
        ]

        st.subheader(f"📋 Screener Results ({len(df)} stocks)")

        st.dataframe(
            df[display_cols].sort_values("Market Cap (₹ Cr)", ascending=False),
            use_container_width=True
        )

        # =========================
        # EXPORT TO EXCEL
        # =========================
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Fundamentals")

        st.download_button(
            label="⬇️ Download Excel",
            data=output.getvalue(),
            file_name="india_fundamental_screener.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ==================================================
# FOOTER
# ==================================================
st.markdown("---")
st.markdown(
    """
**Designed by Gaurav**  
📊 Fundamental • Quant • Market Intelligence  
Built with ❤️ using TradingView data
"""
)
