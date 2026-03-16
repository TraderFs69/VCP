import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

st.title("Minervini VCP Scanner")

API_KEY = st.secrets["POLYGON_API_KEY"]

# Charger la liste du S&P500
sp500 = pd.read_csv(
    "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
)

tickers = sp500["Symbol"].tolist()

end = datetime.today()
start = end - timedelta(days=400)

results = []

# -----------------------------
# Télécharger données Polygon
# -----------------------------

def get_polygon_data(ticker):

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
# Trend Template (Minervini)
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
# Détection des pivots
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
# Contraction VCP
# -----------------------------

def vcp_contraction(df):

    pivot_high, pivot_low = find_pivots(df)

    if len(pivot_high) < 3 or len(pivot_low) < 3:
        return False

    highs = pivot_high.tail(3)
    lows = pivot_low.tail(3)

    contraction1 = (highs.iloc[0] - lows.iloc[0]) / highs.iloc[0]
    contraction2 = (highs.iloc[1] - lows.iloc[1]) / highs.iloc[1]
    contraction3 = (highs.iloc[2] - lows.iloc[2]) / highs.iloc[2]

    return contraction1 > contraction2 > contraction3

# -----------------------------
# Volume dry-up
# -----------------------------

def volume_dryup(df):

    vol10 = df["volume"].rolling(10).mean()
    vol50 = df["volume"].rolling(50).mean()

    return vol10.iloc[-1] < 0.7 * vol50.iloc[-1]

# -----------------------------
# Prix proche breakout
# -----------------------------

def near_breakout(df):

    resistance = df["close"].rolling(60).max().iloc[-1]
    price = df["close"].iloc[-1]

    return price >= 0.92 * resistance

# -----------------------------
# Détection finale VCP
# -----------------------------

def detect_vcp(df):

    return (
        vcp_contraction(df)
        and volume_dryup(df)
        and near_breakout(df)
    )

# -----------------------------
# Scanner principal
# -----------------------------

progress = st.progress(0)

for i, ticker in enumerate(tickers):

    df = get_polygon_data(ticker)

    if df is None or len(df) < 200:
        continue

    try:

        if trend_template(df) and detect_vcp(df):

            price = df["close"].iloc[-1]

            results.append({
                "Ticker": ticker,
                "Price": round(price,2)
            })

    except:
        continue

    progress.progress((i+1)/len(tickers))

# -----------------------------
# Résultats
# -----------------------------

df_results = pd.DataFrame(results)

st.subheader("Minervini VCP Candidates")

if len(df_results) > 0:

    st.dataframe(
        df_results.sort_values("Price", ascending=False),
        use_container_width=True
    )

else:

    st.write("No VCP setups detected today.")
