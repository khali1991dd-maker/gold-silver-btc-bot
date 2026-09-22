import os, requests, datetime, yfinance as yf, pandas as pd, json, time

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(m):
    wd=m.weekday(); h=m.hour
    if wd==4 and h>=23: return False
    if wd==5: return False
    if wd==6 and h<1: return False
    return True

def rsi(s, p=14):
    d=s.diff()
    g=d.clip(lower=0).ewm(alpha=1/p).mean()
    l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))

def get_exness():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if p>1000: return p
    except: pass
    return None

def get_analysis(spot=None):
    df=yf.download("GC=F", period="2d", interval="1m", progress=False, auto_adjust=True)
    if len(df)<210: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]; h=df["High"]; l=df["Low"]

    df["MA20"]=c.rolling(20).mean()
    df["MA50"]=c.rolling(50).mean()
    df["MA100"]=c.rolling(100).mean()
    df["MA200"]=c.rolling(200).mean()
    df["RSI"]=rsi(c)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df["ATR"]=tr.rolling(14).mean()

    last=df.iloc[-1]
    price=spot if spot else float(last["Close"])
    atr=float(last["ATR"])
    rsi_now=float(last["RSI"])

    # فيبو من اخر 50 شمعة
    last50=df.tail(50)
    hi=float(last50["High"].max())
    lo=float(last50["Low"].min())
    diff=hi-lo
    fibs={"0.382":hi-diff*0.382, "0.5":hi-diff*0.5, "0.618":hi-diff*0.618}

    near_fib=None
    for k,v in fibs.items():
        if abs(price-v) < atr*0.8:
            near_fib=f"{k} ({v:.2f})"
            break

    # ترند بـ 20/50/100/200
    trend="عرضي"
    if last["MA20"]>last["MA50"]>last["MA100"]>last["MA200"]:
        trend="صاعد قوي"
    elif last["MA20"]<last["MA50"]<last["MA100"]<last["MA200"]:
        trend="هابط قوي"

    # اشارة
    signal=None
    if near_fib: # لازم فيبو
        if trend=="صاعد قوي" and rsi_now<=70 and rsi_now>=40:
            signal="شراء"
        elif trend=="هابط قوي" and rsi_now>=30 and rsi_now<=60:
            signal="بيع"

    return {"price":price,"trend":trend,"signal":signal,"rsi":rsi_now,"atr":atr,"fib":near_fib}

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")
ex=get_exness()

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 الذهب مغلق")
else:
    an=get_analysis(ex)
    if an:
        if an["signal"]:
            e=an["price"]; a=an["atr"]
            if an["signal"]=="شراء":
                sl=e-a*2; tp1=e+a*1.5; tp2=e+a*3; tp3=e+a*4.5
            else:
                sl=e+a*2; tp1=e-a*1.5; tp2=e-a*3; tp3=e-a*4.5

            msg=(f"🚀🚀🚀 ادخل الان - 1M 🚀🚀🚀\n\n"
                 f"⏰ {t_str}\n"
                 f"💰 {e:.2f}\n"
                 f"📈 {an['trend']} (20>50>100>200)\n"
                 f"📊 RSI: {an['rsi']:.1f}\n"
                 f"📐 فيبو: {an['fib']}\n\n"
                 f"اشارة: {an['signal']}\n"
                 f"دخول: {e:.2f}\n"
                 f"هدف1: {tp1:.2f}\n"
                 f"هدف2: {tp2:.2f}\n"
                 f"هدف3: {tp3:.2f}\n"
                 f"وقف: {sl:.2f}")

            for i in range(3):
                send(msg)
                time.sleep(1.5)
        else:
            send(f"⏰ {t_str}\n🥇 {an['price']:.2f} [1M]\n📈 {an['trend']}\n📊 RSI {an['rsi']:.1f}\n📐 {an['fib']}\n🤖 لا اشارة - 20/50/100/200")

print("Done 1M 20-50-100-200")
