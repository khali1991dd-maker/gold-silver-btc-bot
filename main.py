import os, requests, datetime, yfinance as yf, pandas as pd, numpy as np, json

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

print(f"TOKEN exists: {bool(TOKEN)} len={len(TOKEN) if TOKEN else 0}")
print(f"CHAT exists: {bool(CHAT)} value={CHAT}")

TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
STATE_FILE = "trend_state.json"

def send(text):
    try:
        r = requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
        print(f"Telegram response: {r.status_code} {r.text[:200]}")
        return r
    except Exception as e:
        print(f"Telegram send error: {e}")
        return None

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(symbol, muscat):
    if "BTC" in symbol: return True
    wd = muscat.weekday(); h = muscat.hour
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

def detect_candle(o,h,l,c, prev_o, prev_c):
    body = abs(c-o); rng = h-l
    if rng == 0: return "عادية"
    upper = h - max(o,c); lower = min(o,c) - l
    if body/rng < 0.1: return "دوجي"
    if lower > body*2 and upper < body*0.5 and body/rng < 0.4: return "همر ✅"
    if upper > body*2 and lower < body*0.5 and body/rng < 0.4: return "شهاب ✅"
    if c > o and prev_c < prev_o and c > prev_o and o < prev_c: return "ابتلاعية صاعدة ✅"
    if c < o and prev_c > prev_o and c < prev_o and o > prev_c: return "ابتلاعية هابطة ✅"
    return "عادية"

def get_analysis(symbol):
    try:
        df = yf.download(symbol, period="10d", interval="5m", progress=False, auto_adjust=True)
        if len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close=df["Close"]; high=df["High"]; low=df["Low"]; open_=df["Open"]
        df["MA10"]=close.rolling(10).mean(); df["MA20"]=close.rolling(20).mean()
        df["MA30"]=close.rolling(30).mean(); df["MA50"]=close.rolling(50).mean()
        df["MA70"]=close.rolling(70).mean(); df["MA100"]=close.rolling(100).mean()
        df["MA200"]=close.rolling(200).mean()
        ema12=close.ewm(span=12).mean(); ema26=close.ewm(span=26).mean()
        df["MACD"]=ema12-ema26; df["SIG"]=df["MACD"].ewm(span=9).mean()
        df["RSI"]=rsi(close)
        tr=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
        df["ATR"]=tr.rolling(14).mean()
        last100=df.tail(100)
        hh=last100["High"].max(); ll=last100["Low"].min(); diff=hh-ll
        fib618=hh-diff*0.618; fib50=hh-diff*0.5; fib786=hh-diff*0.786
        last=df.iloc[-1]; prev=df.iloc[-2]
        price=float(last["Close"]); atr=float(last["ATR"])
        trend="عرضي ❌ لا دخول"
        if last["MA10"]>last["MA20"]>last["MA30"]>last["MA50"]>last["MA70"]>last["MA100"]:
            trend="صاعد قوي"
        elif last["MA10"]<last["MA20"]<last["MA30"]<last["MA50"]<last["MA70"]<last["MA100"]:
            trend="هابط قوي"
        candle=detect_candle(float(last["Open"]),float(last["High"]),float(last["Low"]),float(last["Close"]),float(prev["Open"]),float(prev["Close"]))
        rng=float(last["High"]-last["Low"])
        block=rng > atr*1.8
        bullish=float(last["Close"])>float(last["Open"])
        signal=None
        if trend=="صاعد قوي" and price>last["MA10"] and bullish and last["MACD"]>last["SIG"] and last["RSI"]<=75:
            signal="شراء"
        elif trend=="هابط قوي" and price<last["MA10"] and not bullish and last["MACD"]<last["SIG"] and last["RSI"]>=25:
            signal="بيع"
        return {"price":price,"trend":trend,"signal":signal,"rsi":float(last["RSI"]),"atr":atr,"fib618":fib618,"fib50":fib50,"fib786":fib786,"candle":candle,"block":block}
    except Exception as e:
        print(f"Error {symbol}:{e}"); return None

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE,"r") as f: return json.load(f)
    except: pass
    return {}

def save_state(state):
    try:
        with open(STATE_FILE,"w") as f: json.dump(state,f)
    except: pass

muscat=get_muscat_time()
time_str=muscat.strftime("%d-%m %Y %I:%M %p")
print(f"Time Muscat: {time_str}")

symbols={"GC=F":"الذهب","SI=F":"الفضة","BTC-USD":"البيتكوين"}

if muscat.hour==15 and 30 <= muscat.minute < 35:
    send(f"⚠️ تنبيه خبر مهم الساعة 4:30م مسقط\n{time_str}")

state=load_state()
full_report=[]; closed_report=[]; trade_sent=False

for sym,name in symbols.items():
    if not is_market_open(sym,muscat):
        closed_report.append(f"{name}: ⏸️ مغلق")
        continue
    an=get_analysis(sym)
    if not an:
        full_report.append(f"{name}: جلب بيانات...")
        continue
    last_trend=state.get(sym,"")
    if last_trend and last_trend!= an["trend"]:
        send(f"🔄 تغيير ترند {name} من {last_trend} الى {an['trend']}\n{time_str}\nالسعر: {an['price']:.2f}")
    state[sym]=an["trend"]
    if an["signal"]:
        e=an["price"]; a=an["atr"]
        if an["signal"]=="شراء":
            sl=e-a*2; tp1=e+a*1.5; tp2=e+a*3; tp3=e+a*4.5
        else:
            sl=e+a*2; tp1=e-a*1.5; tp2=e-a*3; tp3=e-a*4.5
        msg=f"🚀 ادخل الصفقة الان - {name}\n\nالتاريخ: {time_str}\nالسعر: {e:.2f}\nالترند: {an['trend']}\nالاشارة: {an['signal']}\nRSI: {an['rsi']:.1f}\nالشمعة: {an['candle']}\nبلوك: {'يوجد ✅' if an['block'] else 'لا'}\nفيبو 61.8%: {an['fib618']:.2f}\nفيبو 50%: {an['fib50']:.2f}\nفيبو 78.6%: {an['fib786']:.2f}\n\nالدخول: {e:.2f}\nهدف1: {tp1:.2f}\nهدف2: {tp2:.2f}\nهدف3: {tp3:.2f}\nوقف: {sl:.2f}"
        send(msg)
        trade_sent=True
    full_report.append(f"{name}: {an['price']:.2f} | {an['trend']} | RSI {an['rsi']:.0f} | {an['candle']} | {an['signal'] if an['signal'] else 'انتظار'}")

save_state(state)
msg=f"🤖 GoldSniper - {time_str}\n\n"
if closed_report: msg+="\n".join(closed_report)+"\n\n"
if full_report: msg+="\n".join(full_report)+"\n\n"
if not trade_sent: msg+="✅ البوت شغال كل 5د - لا صفقات قوية (عرضي)\n"
msg+=f"فيبو 61.8/50/78.6 | بلوك اوردر | MA مرتب | فريم 5د مسقط"
send(msg)
print("Done")
