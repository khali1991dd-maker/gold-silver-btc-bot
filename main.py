import os, requests, datetime, yfinance as yf, pandas as pd, json, time

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
    except Exception as e:
        print(f"Send error: {e}")

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
    try:
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

        # فيبو من اخر 100 شمعة
        last100=df.tail(100)
        hi=float(last100["High"].max())
        lo=float(last100["Low"].min())
        diff=hi-lo
        fibs={"0.382":hi-diff*0.382, "0.5":hi-diff*0.5, "0.618":hi-diff*0.618}

        near_fib=None
        closest_dist=999
        closest_label=""
        for k,v in fibs.items():
            d=abs(price-v)
            if d < closest_dist:
                closest_dist=d
                closest_label=f"{k} ({v:.2f})"
            if d < atr*1.5: # موسع من 0.8 الى 1.5
                near_fib=f"{k} ({v:.2f})"
                break

        if not near_fib:
            fib_display=f"{closest_label} بعيد {closest_dist:.1f}$"
        else:
            fib_display=near_fib

        trend="عرضي"
        if last["MA20"]>last["MA50"]>last["MA100"]>last["MA200"]:
            trend="صاعد قوي"
        elif last["MA20"]<last["MA50"]<last["MA100"]<last["MA200"]:
            trend="هابط قوي"

        signal=None
        if near_fib:
            if trend=="صاعد قوي" and 35 <= rsi_now <= 70:
                signal="شراء"
            elif trend=="هابط قوي" and 30 <= rsi_now <= 65:
                signal="بيع"

        return {"price":price,"trend":trend,"signal":signal,"rsi":rsi_now,"atr":atr,"fib":fib_display,"has_fib": near_fib is not None}
    except Exception as e:
        print(f"Error: {e}")
        return None

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
                sl=e+a*2; tp1
