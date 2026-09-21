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
    # تصليح: يقفل جمعة 11 بالليل والسبت كامل فقط
    if wd==4 and h>=23: return False
    if wd==5: return False
    if wd==6 and h<1: return False
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
    if lower > body*1.5 and is_bull:
        return "مطرقة شرائية 🔨"
    if upper > body*1.5 and not is_bull:
        return "شهاب بيعي ☄️"
    return None

def get_analysis(symbol, spot_price=None):
    try:
        df=yf.download(symbol, period="10d", interval="5m", progress=False, auto_adjust=True)
        if len(df)<100: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        close=df["Close"]; high=df["High"]; low=df["Low"]; open_=df["Open"]
        df["MA10"]=close.rolling(10).mean(); df["MA20"]=close.rolling(20).mean()
        df["MA30"]=close.rolling(30).mean()
        ema12=close.ewm(span=12).mean(); ema26=close.ewm(span=26).mean()
        df["MACD"]=ema12-ema26; df["SIG"]=df["MACD"].ewm(span=9).mean()
        df["RSI"]=rsi(close)
        tr=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
        df["ATR"]=tr.rolling(14).mean()
        last=df.iloc[-1]
        price = spot_price if spot_price else float(last["Close"])
        atr=float(last["ATR"])

        trend="عرضي"
        if last["MA10"]>last["MA20"]>last["MA30"]:
            trend="صاعد"
        elif last["MA10"]<last["MA20"]<last["MA30"]:
            trend="هابط"

        candle = detect_candle(float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"]))
        bullish=float(last["Close"])>float(last["Open"])
        signal=None
        
        if trend=="صاعد" and float(last["Close"])>last["MA10"] and last["MACD"]>last["SIG"] and last["RSI"]<75 and bullish:
            signal="شراء"
        elif trend=="هابط" and float(last["Close"])<last["MA10"] and last["MACD"]<last["SIG"] and last["RSI"]>20 and not bullish:
            signal="بيع"

        return {"price":price,"trend":trend,"signal":signal,"atr":atr,"candle":candle if candle else "زخم"}
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

for sym,name in symbols.items():
    if not is_market_open(sym,muscat): continue
    spot = exness_gold if name=="الذهب" else None
    an=get_analysis(sym, spot_price=spot)
    if not an: continue
    
    if an["signal"]:
        e=an["price"]; a=an["atr"]
        if an["signal"]=="شراء":
            sl=e-a*1.5; tp1=e+a*1; tp2=e+a*2; tp3=e+a*3
        else:
            sl=e+a*1.5; tp1=e-a*1; tp2=e-a*2; tp3=e-a*3

        msg=(f"🚀🚀🚀 ادخل الان - {name} 🚀🚀🚀\n\n"
             f"⏰ {time_str}\n"
             f"💰 {e:.2f}\n"
             f"📈 {an['trend']} - {an['candle']}\n\n"
             f"اشارة: {an['signal']}\n"
             f"دخول: {e:.2f}\n"
             f"هدف1: {tp1:.2f}\n"
             f"هدف2: {tp2:.2f}\n"
             f"هدف3: {tp3:.2f}\n"
             f"وقف: {sl:.2f}\n\n"
             f"⚠️ عدواني - ادارة راس مال صارمة")
        
        for i in range(3):
            send(msg)
            time.sleep(1.5)

save_state(state)
send(f"⏰ {time_str}\n🤖 عدواني شغال - يرن 3x - تم تصليح الاحد\nالذهب {exness_gold if exness_gold else '...'}")
print("Done aggressive fixed")
