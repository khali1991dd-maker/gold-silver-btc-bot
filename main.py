import os, requests, datetime, yfinance as yf, pandas as pd, numpy as np

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
    except Exception as e:
        print(e)

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(symbol, muscat):
    if "BTC" in symbol:
        return True
    wd = muscat.weekday()
    h = muscat.hour
    if wd == 4 and h >= 23:
        return False
    if wd == 5:
        return False
    if wd == 6:
        return False
    if wd == 0 and h < 1:
        return False
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
        if len(df) < 200:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        df["MA10"] = close.rolling(10).mean()
        df["MA20"] = close.rolling(20).mean()
        df["MA30"] = close.rolling(30).mean()
        df["MA50"] = close.rolling(50).mean()
        df["MA70"] = close.rolling(70).mean()
        df["MA100"] = close.rolling(100).mean()
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        df["MACD"] = ema12 - ema26
        df["SIG"] = df["MACD"].ewm(span=9).mean()
        df["RSI"] = rsi(close)
        tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean()
        last100 = df.tail(100)
        hh = last100["High"].max()
        diff = hh - last100["Low"].min()
        fib618 = hh - diff*0.618
        last = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(last["Close"])
        atr = float(last["ATR"])
        trend = "عرضي"
        if last["MA10"] > last["MA20"] > last["MA30"] > last["MA50"] > last["MA70"] > last["MA100"]:
            trend = "صاعد قوي"
        elif last["MA10"] < last["MA20"] < last["MA30"] < last["MA50"] < last["MA70"] < last["MA100"]:
            trend = "هابط قوي"
        bullish = float(last["Close"]) > float(last["Open"])
        candle = "عادية"
        body = abs(float(last["Close"]-last["Open"]))
        rng = float(last["High"]-last["Low"])
        if rng>0 and body/rng < 0.1:
            candle = "دوجي"
        block = rng > atr*1.8
        signal = None
        if trend == "صاعد قوي" and price > last["MA10"] and bullish and last["MACD"] > last["SIG"] and last["RSI"] <= 75:
            signal = "شراء"
        elif trend == "هابط قوي" and price < last["MA10"] and not bullish and last["MACD"] < last["SIG"] and last["RSI"] >= 25:
            signal = "بيع"
        return {"price": price, "trend": trend, "signal": signal, "rsi": float(last["RSI"]), "atr": atr, "fib618": fib618, "candle": candle, "block": block}
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return None

muscat = get_muscat_time()
time_str = muscat.strftime("%d-%m %Y %I:%M %p")
print(f"Time Muscat: {time_str}")

symbols = {"GC=F": "الذهب", "SI=F": "الفضة", "BTC-USD": "البيتكوين"}

if muscat.hour == 15 and 30 <= muscat.minute < 35:
    send(f"تنبيه خبر مهم الساعة 4:30م مسقط\n{time_str}")

full_report = []
closed_report = []
trade_sent = False

for sym, name in symbols.items():
    if not is_market_open(sym, muscat):
        closed_report.append(f"{name}: مغلق")
        continue
    an = get_analysis(sym)
    if not an:
        full_report.append(f"{name}: جاري جلب البيانات...")
        continue
    if an["signal"]:
        entry = an["price"]
        atr = an["atr"]
        if an["signal"] == "شراء":
            sl = entry - atr*2
            tp1 = entry + atr*1.5
            tp2 = entry + atr*3
            tp3 = entry + atr*4.5
        else:
            sl = entry + atr*2
            tp1 = entry - atr*1.5
            tp2 = entry - atr*3
            tp3 = entry - atr*4.5
        msg = f"🚀 ادخل الصفقة الان - {name}\n\nالتاريخ: {time_str}\nالسعر: {entry:.2f}\nالترند: {an['trend']}\nالاشارة: {an['signal']}\nRSI: {an['rsi']:.1f}\nالدخول: {entry:.2f}\nهدف1: {tp1:.2f}\nهدف2: {tp2:.2f}\nهدف3: {tp3:.2f}\nوقف: {sl:.2f}"
        send(msg)
        trade_sent = True
    status = an["signal"] if an["signal"] else "انتظار"
    full_report.append(f"{name}: {an['price']:.2f} | {an['trend']} | RSI {an['rsi']:.0f} | {status}")

message = f"GoldSniper - {time_str}\n\n"
if closed_report:
    message += "\n".join(closed_report) + "\n\n"
if full_report:
    message += "\n".join(full_report) + "\n\n"
if not trade_sent:
    message += "البوت شغال - يفحص كل 5 دقايق\nلا توجد صفقات قوية الان"
message += "\n\nفريم 5د | توقيت مسقط"
send(message)
print("Done")
