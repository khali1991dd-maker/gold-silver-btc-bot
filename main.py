import os, requests, datetime, yfinance as yf, pandas as pd, json, time

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
STATE_FILE = "trend_state.json"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
    except Exception as e:
        print(f"Send error: {e}")

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(symbol, muscat):
    if "BTC" in symbol: return True
    wd=muscat.weekday(); h=muscat.hour
    if wd==4 and h>=23: return False
    if wd==5: return False
    if wd==6: return False
    if wd==0 and h<1: return False
    return True

def rsi(series, p=14):
    delta=series.diff()
    gain=delta.clip(lower=0).ewm(alpha=1/p).mean()
    loss=-delta.clip(upper=0).ewm(alpha=1/p).mean()
    rs=gain/loss
    return 100-(100/(1+rs))

def get_exness_spot():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        price = float(r.get('price', 0))
        if price > 1000: return price
    except: pass
    return None

def detect_candle(open_, high, low, close):
    body = abs(close - open_)
    upper = high - max(close, open_)
    lower = min(close, open_) - low
    is_bull = close > open_
    if body==0: return None
    if lower > body*2 and upper < body*0.5 and is_bull:
        return "مطرقة شرائية 🔨"
    if upper > body*2 and lower < body*0.5 and not is_bull:
        return "شهاب بيعي ☄️"
    return None

def detect_engulfing(df):
    if len(df) < 2: return None
    o1, c1 = float(df.iloc[-2]["Open"]), float(df.iloc[-2]["Close"])
    o2, c2 = float(df.iloc[-1]["Open"]), float(df.iloc[-1]["Close"])
    if c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1:
        return "ابتلاع شرائي ✅"
    if c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1:
        return "ابتلاع بيعي ❌"
    return None

def get_analysis(symbol, spot_price=None):
    try:
        df=yf.download(symbol, period="10d", interval="5m", progress=False, auto_adjust=True)
        if len(df)<200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        close=df["Close"]; high=df["High"]; low=df["Low"]; open_=df["Open"]
        df["MA10"]=close.rolling(10).mean(); df["MA20"]=close.rolling(20).mean()
        df["MA30"]=close.rolling(30).mean(); df["MA50"]=close.rolling(50).mean()
        df["MA70"]=close.rolling(70).mean(); df["MA100"]=close.rolling(100).mean()
        ema12=close.ewm(span=12).mean(); ema26=close.ewm(span=26).mean()
        df["MACD"]=ema12-ema26; df["SIG"]=df["MACD"].ewm(span=9).mean()
        df["RSI"]=rsi(close)
        tr=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
        df["ATR"]=tr.rolling(14).mean()
        last=df.iloc[-1]
        price = spot_price if spot_price else float(last["Close"])
        atr=float(last["ATR"])

        last50 = df.tail(50)
        swing_high = float(last50["High"].max())
        swing_low = float(last50["Low"].min())
        diff = swing_high - swing_low
        fib_levels = {"0.382": swing_high - diff*0.382, "0.5": swing_high - diff*0.5, "0.618": swing_high - diff*0.618}

        near_fib = None
        for k,v in fib_levels.items():
            if abs(price - v) < atr*0.8:
                near_fib = f"{k} ({v:.2f})"
                break

        trend="عرضي"
        if last["MA10"]>last["MA20"]>last["MA30"]>last["MA50"]>last["MA70"]>last["MA100"]:
            trend="صاعد قوي"
        elif last["MA10"]<last["MA20"]<last["MA30"]<last["MA50"]<last["MA70"]<last["MA100"]:
            trend="هابط قوي"

        candle = detect_candle(float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"]))
        engulf = detect_engulfing(df)
        candle_pattern = engulf if engulf else candle
        is_bull_candle = candle_pattern in ["مطرقة شرائية 🔨", "ابتلاع شرائي ✅"]
        is_bear_candle = candle_pattern in ["شهاب بيعي ☄️", "ابتلاع بيعي ❌"]

        bullish=float(last["Close"])>float(last["Open"])
        signal=None
        
        if (near_fib or candle_pattern):
            if trend=="صاعد قوي" and float(last["Close"])>last["MA10"] and bullish and last["MACD"]>last["SIG"] and last["RSI"]<=70 and (is_bull_candle or near_fib):
                signal="شراء"
            elif trend=="هابط قوي" and float(last["Close"])<last["MA10"] and not bullish and last["MACD"]<last["SIG"] and last["RSI"]>=30 and (is_bear_candle or near_fib):
                signal="بيع"

        return {"price":price,"trend":trend,"signal":signal,"atr":atr,"fib":fib_levels,"near_fib":near_fib,"candle":candle_pattern,"high":swing_high,"low":swing_low}
    except Exception as e:
        print(f"Error {symbol}:{e}"); return None

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE,"r") as f: return json.load(f)
    except: pass
    return {}
def save_state(s):
    try:
        with open(STATE_FILE,"w") as f: json.dump(s,f)
    except: pass

muscat=get_muscat_time()
time_str=muscat.strftime("%d-%m-%Y %I:%M %p")
symbols={"GC=F":"الذهب","SI=F":"الفضة","BTC-USD":"البيتكوين"}
state=load_state()
exness_gold = get_exness_spot()
gold_p = silver_p = btc_p = "جلب..."

for sym,name in symbols.items():
    if not is_market_open(sym,muscat):
        if name=="الذهب": gold_p="مغلق"
        elif name=="الفضة": silver_p="مغلق"
        else: btc_p="مغلق"
        continue
    spot = exness_gold if name=="الذهب" else None
    an=get_analysis(sym, spot_price=spot)
    if not an: continue
    
    if name=="الذهب": gold_p=f"{an['price']:.2f}"
    elif name=="الفضة": silver_p=f"{an['price']:.2f}"
    else: btc_p=f"{an['price']:.2f}"

    if an["signal"]:
        e=an["price"]; a=an["atr"]
        if an["signal"]=="شراء":
            sl=e-a*2; tp1=e+a*1.5; tp2=e+a*3; tp3=e+a*4.5
        else:
            sl=e+a*2; tp1=e-a*1.5; tp2=e-a*3; tp3=e-a*4.5

        msg=(f"🚀🚀🚀 ادخل الان - {name} 🚀🚀🚀\n\n"
             f"⏰ الوقت والتاريخ: {time_str}\n"
             f"💰 السعر: {e:.2f} (Exness)\n"
             f"📈 نوع الترند: {an['trend']}\n"
             f"🕯️ الشمعة: {an['candle']}\n"
             f"📐 فيبو: {an['near_fib']}\n\n"
             f"اشارة: {an['signal']}\n"
             f"سعر الدخول: {e:.2f}\n"
             f"الهدف 1: {tp1:.2f}\n"
             f"الهدف 2: {tp2:.2f}\n"
             f"الهدف 3: {tp3:.2f}\n"
             f"وقف الخسارة: {sl:.2f}")
        
        # يرن 3 مرات
        for i in range(3):
            send(msg)
            time.sleep(1.5)

save_state(state)

status_msg = (
    f"⏰ الوقت والتاريخ: {time_str}\n"
    f"🥇 سعر الذهب: {gold_p}\n"
    f"🥈 سعر الفضة: {silver_p}\n"
    f"₿ سعر البيتكوين: {btc_p}\n\n"
    f"🤖 البوت شغال ✅ - RSI 30/70 - يرن 3x"
)
send(status_msg)
print("Done")
