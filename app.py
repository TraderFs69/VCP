import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

st.title("Minervini VCP Scanner — Advanced")

API_KEY = st.secrets["POLYGON_API_KEY"]

# Charger S&P500
sp500 = pd.read_csv(
    "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
)

tickers = sp500["Symbol"].tolist()

end = datetime.today()
start = end - timedelta(days=400)

results = []

# -----------------------------
# Polygon data
# -----------------------------

def get_data(ticker):

    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start.date()}/{end.date()}?adjusted=true&limit=500&apiKey={API_KEY}"

    try:
        r = requests.get(url)
        data = r.json()
    except:
        return None

    if "results" not in data:
        return None

    df = pd.DataFrame(data["results"])

    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df.set_index("date", inplace=True)

    df.rename(columns={
        "c":"close",
        "h":"high",
        "l":"low",
        "v":"volume"
    }, inplace=True)

    return df[["close","high","low","volume"]]

# -----------------------------
# Trend Template
# -----------------------------

def trend_template(df):

    close = df["close"]

    ma50 = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    ma200 = close.rolling(200).mean()

    price = close.iloc[-1]

    cond1 = price > ma150.iloc[-1] and price > ma200.iloc[-1]
    cond2 = ma150.iloc[-1] > ma200.iloc[-1]
    cond3 = ma200.iloc[-1] > ma200.iloc[-20]
    cond4 = ma50.iloc[-1] > ma150.iloc[-1] and ma50.iloc[-1] > ma200.iloc[-1]
    cond5 = price > ma50.iloc[-1]

    return cond1 and cond2 and cond3 and cond4 and cond5

# -----------------------------
# Pivot detection
# -----------------------------

def find_pivots(df):

    highs = df["high"]
    lows = df["low"]

    pivot_high = highs[
        (highs.shift(1) < highs) &
        (highs.shift(-1) < highs)
    ]

    pivot_low = lows[
        (lows.shift(1) > lows) &
        (lows.shift(-1) > lows)
    ]

    return pivot_high, pivot_low

# -----------------------------
# VCP contraction
# -----------------------------

def vcp_contraction(df):

    pivot_high, pivot_low = find_pivots(df)

    if len(pivot_high) < 3 or len(pivot_low) < 3:
        return False, 0

    highs = pivot_high.tail(3)
    lows = pivot_low.tail(3)

    c1 = (highs.iloc[0] - lows.iloc[0]) / highs.iloc[0]
    c2 = (highs.iloc[1] - lows.iloc[1]) / highs.iloc[1]
    c3 = (highs.iloc[2] - lows.iloc[2]) / highs.iloc[2]

    contraction = c1 > c2 > c3

    score = (c1 + c2 + c3)

    return contraction, score

# -----------------------------
# Volume dry-up
# -----------------------------

def volume_dryup(df):

    vol10 = df["volume"].rolling(10).mean()
    vol50 = df["volume"].rolling(50).mean()

    return vol10.iloc[-1] < 0.7 * vol50.iloc[-1]

# -----------------------------
# Breakout proximity
# -----------------------------

def near_breakout(df):

    resistance = df["close"].rolling(60).max().iloc[-1]
    price = df["close"].iloc[-1]

    return price >= 0.92 * resistance

# -----------------------------
# Relative strength
# -----------------------------

def relative_strength(df):

    close = df["close"]

    return (close.iloc[-1] / close.iloc[0]) - 1

# -----------------------------
# Scanner
# -----------------------------

progress = st.progress(0)

for i, ticker in enumerate(tickers):

    df = get_data(ticker)

    if df is None or len(df) < 200:
        continue

    try:

        if trend_template(df):

            vcp_ok, vcp_score = vcp_contraction(df)

            if vcp_ok and volume_dryup(df) and near_breakout(df):

                price = df["close"].iloc[-1]

                rs = relative_strength(df)

                vol_today = df["volume"].iloc[-1]
                vol_avg = df["volume"].rolling(50).mean().iloc[-1]

                breakout_volume = vol_today > 1.5 * vol_avg

                results.append({
                    "Ticker": ticker,
                    "Price": round(price,2),
                    "RS": round(rs,2),
                    "VCP Score": round(vcp_score,3),
                    "Breakout Volume": breakout_volume
                })

    except:
        continue

    progress.progress((i+1)/len(tickers))

# -----------------------------
# Résultats
# -----------------------------

df_results = pd.DataFrame(results)

st.subheader("Top VCP Setups")

if len(df_results) > 0:

    df_results = df_results.sort_values(
        ["RS","VCP Score"],
        ascending=False
    )

    st.dataframe(df_results, use_container_width=True)

else:

    st.write("No setups detected today.")
