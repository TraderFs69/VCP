import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

st.title("Minervini VCP Scanner")

API_KEY = st.secrets["POLYGON_API_KEY"]

# Charger les tickers S&P500
sp500 = pd.read_csv(
    "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
)

tickers = sp500["Symbol"].tolist()

end = datetime.today()
start = end - timedelta(days=400)

results = []

# -----------------------------
# Télécharger les données Polygon
# -----------------------------

def get_polygon_data(ticker):

    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start.date()}/{end.date()}?adjusted=true&limit=500&apiKey={API_KEY}"

    r = requests.get(url)

    if r.status_code != 200:
        return None

    data = r.json()

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
# Détection VCP
# -----------------------------

def detect_vcp(df):

    close = df["close"]
    volume = df["volume"]

    range60 = (close.rolling(60).max() - close.rolling(60).min()) / close.rolling(60).max()
    range30 = (close.rolling(30).max() - close.rolling(30).min()) / close.rolling(30).max()
    range15 = (close.rolling(15).max() - close.rolling(15).min()) / close.rolling(15).max()

    contraction = (
        range60.iloc[-1] > range30.iloc[-1] and
        range30.iloc[-1] > range15.iloc[-1]
    )

    vol10 = volume.rolling(10).mean()
    vol30 = volume.rolling(30).mean()

    volume_dry = vol10.iloc[-1] < vol30.iloc[-1]

    resistance = close.rolling(60).max().iloc[-1]
    price = close.iloc[-1]

    near_breakout = price >= 0.9 * resistance

    return contraction and volume_dry and near_breakout

# -----------------------------
# Scanner
# -----------------------------

progress = st.progress(0)

for i, ticker in enumerate(tickers):

    df = get_polygon_data(ticker)

    if df is None or len(df) < 200:
        continue

    if trend_template(df) and detect_vcp(df):

        price = df["close"].iloc[-1]

        results.append({
            "Ticker": ticker,
            "Price": round(price,2)
        })

    progress.progress((i+1)/len(tickers))

# -----------------------------
# Résultats
# -----------------------------

df_results = pd.DataFrame(results)

st.subheader("Minervini VCP Candidates")

if len(df_results) > 0:

    st.dataframe(df_results)

else:

    st.write("No VCP setups found today.")
