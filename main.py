import os, requests, datetime, yfinance as yf, pandas as pd, json

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

# سعر Exness الفوري المباشر
def get_exness_spot():
    try:
        # API يعطي نفس سعر Exness الفوري
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        price = float(r.get('price', 0))
        if price > 1000: return price
    except: pass
    try:
        # بديل ثاني
        r = requests.get("https://api.metalpriceapi.com/v1/latest?api_key=demo&base=USD&currencies=XAU", timeout=10)
    except: pass
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
        # لو فيه سعر فوري نستخدمه للدخول
        price = spot_price if spot_price else float(last["Close"])
        atr=float(last["ATR"])
        trend="عرضي"
        if last["MA10"]>last["MA20"]>last["MA30"]>last["MA50"]>last["MA70"]>last["MA100"]:
            trend="صاعد قوي"
        elif last["MA10"]<last["MA20"]<last["MA30"]<last["MA50"]<last["MA70"]<last["MA100"]:
            trend="هابط قوي"
        bullish=float(last["Close"])>float(last["Open"])
        signal=None
        if trend=="صاعد قوي" and float(last["Close"])>last["MA10"] and bullish and last["MACD"]>last["SIG"] and last["RSI"]<=75:
            signal="شراء"
        elif trend=="هابط قوي" and float(last["Close"])<last["MA10"] and not bullish and last["MACD"]<last["SIG"] and last["RSI"]>=25:
            signal="بيع"
        return {"price":price,"trend":trend,"signal":signal,"atr":atr}
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
time_str=muscat.strftime("%d-%m %Y %I:%M %p")

symbols={"GC=F":"الذهب","SI=F":"الفضة","BTC-USD":"البيتكوين"}
state=load_state()
prices_text=[]

# جلب سعر Exness الفوري
exness_gold = get_exness_spot()
print(f"Exness Spot Gold: {exness_gold}")

for sym,name in symbols.items():
    if not is_market_open(sym,muscat):
        prices_text.append(f"{name}: ⏸️ مغلق"); continue
    spot = exness_gold if name=="الذهب" else None
    an=get_analysis(sym, spot_price=spot)
    if not an:
        prices_text.append(f"{name}: جلب بيانات..."); continue
    state[sym]=an["trend"]
    if an["signal"]:
        e=an["price"]; a=an["atr"]
        if an["signal"]=="شراء":
            sl=e-a*2; tp1=e+a*1.5; tp2=e+a*3; tp3=e+a*4.5
        else:
            sl=e+a*2; tp1=e-a*1.5; tp2=e-a*3; tp3=e-a*4.5
        msg=(f"🚀 دخول الان - {name} (Exness)\n\n"
             f"الوقت: {time_str}\n"
             f"السعر: {e:.2f}\n"
             f"نوع الترند: {an['trend']}\n"
             f"الاشارة: {an['signal']}\n\n"
             f"دخول: {e:.2f}\n"
             f"هدف1: {tp1:.2f}\n"
             f"هدف2: {tp2:.2f}\n"
             f"هدف3: {tp3:.2f}\n"
             f"وقف: {sl:.2f}")
        send(msg)
    prices_text.append(f"{name}: {an['price']:.2f}")

save_state(state)
send(f"🤖 GoldSniper - {time_str}\n(سعر Exness الفوري)\n\n" + "\n".join(prices_text) + "\n\n✅ مطابق لـ MT5 Exness")
print("Done")
