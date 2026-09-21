import os, requests, datetime, yfinance as yf, pandas as pd, numpy as np

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
        print(f"Sent: {text[:50]}")
    except Exception as e:
        print(f"Send error: {e}")

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(symbol, muscat):
    if "BTC" in symbol: return True
    wd = muscat.weekday()
    h = muscat.hour
    if wd == 4 and h >= 23: return False
    if wd == 5: return False
    if wd == 6: return False
    if wd == 0 and h < 1: return False
    return True

def rsi(series, p=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/p).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/p).mean()
    rs = gain / loss
    return 100 - (100/(1+rs))

def get_analysis(symbol):
    try:
        df = yf.download(symbol, period="10d", interval="5m", progress=False, auto_adjust=True)
        if len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close = df['Close']; high = df['High']; low = df['Low']
        df['MA10']=close.rolling(10).mean(); df['MA20']=close.rolling(20).mean()
        df['MA30']=close.rolling(30).mean(); df['MA50']=close.rolling(50).mean()
        df['MA70']=close.rolling(70).mean(); df['MA100']=close.rolling(100).mean()
        df['MA200']=close.rolling(200).mean()
        ema12=close.ewm(span=12).mean(); ema26=close.ewm(span=26).mean()
        df['MACD']=ema12-ema26; df['SIG']=df['MACD'].ewm(span=9).mean()
        df['RSI']=rsi(close)
        tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
        df['ATR']=tr.rolling(14).mean()
        last100 = df.tail(100)
        hh=last100['High
