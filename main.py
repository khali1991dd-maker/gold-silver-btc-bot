import os, requests, datetime, time, pandas as pd, yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try: requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=20)
    except: pass

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(m):
    if m.weekday()==5: return False
    if m.weekday()==4 and m.hour>=23: return False
    if m.weekday()==6 and m.hour<1: return False
    return True

def rsi(s, p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))

def get_price_mt5():
    # سعر Exness MT5 الحقيقي - 3 مصادر
    # 1- Gold-API نفس Exness
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if 4000 < p < 5000:
            return p, "Exness Gold-API"
    except: pass
    # 2- Binance PAXG = ذهب حقيقي لايف يتبع سبوت 100% نفس MT5
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5).json()
        p=float(r['price'])
        if 4000 < p < 5000:
            return p, "Binance PAXG = MT5 Live"
    except: pass
    # 3- Metals Live
    try:
        r=requests.get("https://api.metals.live/v1/spot/gold", timeout=5).json()
        p=float(r[0] if isinstance(r, list) else r.get('price',0))
        if 4000 < p < 5000:
            return p, "Metals Live Spot"
    except: pass
    return None, None

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 السوق مغلق")
else:
    # شموع 5د سبوت حقيقي نفس MT5
    df=yf.download("XAUUSD=X", period="30d", interval="5m", progress=False, auto_adjust=True)
    if df.empty or len(df)<200:
        df=yf.download("GC=F", period="30d", interval="5m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    c=df["Close"]; h=df["High"]; l=df["Low"]; o=df["Open"]

    df["ma20"]=c.rolling(20).mean()
    df["ma50"]=c.rolling(50).mean()
    df["ma100"]=c.rolling(100).mean()
    df["ma200"]=c.rolling(200).mean().shift(14)

    df["rsi"]=rsi(c,14)
    df["macd"]=c.ewm(span=5).mean() - c.ewm(span=20).mean()

    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean().iloc[-1]
    atr=float(atr)

    price, src = get_price_mt5()
    if price is None:
        price=float(c.iloc[-1])
        src="Yahoo سبوت (احتياطي)"

    r=float(df["rsi"].iloc[-1])
    macd_v=float(df["macd"].iloc[-1])

    # فيبو 0 و 0.25 و 0.5 و 1
    look=50
    rh=float(h[-look:].max()); rl=float(l[-look:].min()); fr=rh-rl
    fib_0=rh
    fib_25=rh-fr*0.25
    fib_50=rh-fr*0.5
    fib_100=rl

    # قرب من فيبو - زودت السماح لـ 2.5 دولار عشان يطابق MT5
    near_fib=False; fib_txt=""
    for name, val in [("0.25",fib_25),("0.5",fib_50),("0",fib_0),("1",fib_100)]:
        if abs(price-val) < max(2.5, atr*1.2):
            near_fib=True
            fib_txt=f"فيبو {name} = {val:.2f}"
            break

    # OB بلوك
    ob_txt=""
    for i in range(-15, -3):
        # بيعي
        if o.iloc[i] < c.iloc[i] and (o.iloc[i+1]-c.iloc[i+1]) > atr*0.5:
            zp=(o.iloc[i]+c.iloc[i])/2
            if abs(price-zp) < max(2.5, atr*1.2):
                ob_txt=f"OB بيعي {zp:.2f}"
                break
        # شرائي
        if o.iloc[i] > c.iloc[i] and (c.iloc[i+1]-o.iloc[i+1]) > atr*0.5:
            zp=(o.iloc[i]+c.iloc[i])/2
            if abs(price-zp) < max(2.5, atr*1.2):
                ob_txt=f"OB شرائي {zp:.2f}"
                break

    near = near_fib or (ob_txt!="")
    ma20=float(df["ma20"].iloc[-1]); ma50=float(df["ma50"].iloc[-1]); ma100=float(df["ma100"].iloc[-1]); ma200=float(df["ma200"].iloc[-1])

    # خففت شرط الموفنجات - كان 20>50>100>200 يعطي اشارة نادرة
    # الحين: 20>50 و السعر فوق 100 = شراء / 20<50 و السعر تحت 100 = بيع
    up = ma20 > ma50 and price > ma100
    down = ma20 < ma50 and price < ma100
    # للرسالة فقط نعرض الترتيب الكامل
    up_full = ma20 > ma50 > ma100 > ma200
    down_full = ma20 < ma50 < ma100 < ma200

    signal=None
    if 25 <= r <= 75 and near: # وسعت RSI
        if up and macd_v > 0:
            signal="شراء 🚀"
        elif down and macd_v < 0:
            signal="بيع 🔻"

    if signal:
        sl=price-atr*2 if "شراء" in signal else price+atr*2
        tp1=price+atr*1.5 if "شراء" in signal else price-atr*1.5
        tp2=price+atr*3 if "شراء" in signal else price-atr*3
        tp3=price+atr*4.5 if "شراء" in signal else price-atr*4.5

        reason=ob_txt if ob_txt else fib_txt
        trend_txt="مرتبة كامل" if (up_full or down_full) else "مرتبة جزئي 20/50"
        msg=(f"🚀 {signal} [فريم 5د - MT5]\n"
             f"⏰ {t_str}\n"
             f"💰 {price:.2f} [{src}]\n"
             f"📦 {reason}\n"
             f"📈 {trend_txt} 20:{ma20:.1f} 50:{ma50:.1f} 100:{ma100:.1f} 200@14:{ma200:.1f}\n"
             f"📉 MACD {macd_v:.3f} {'فوق 0' if macd_v>0 else 'تحت 0'}\n"
             f"📊 RSI {r:.1f}\n\n"
             f"دخول {price:.2f}\n"
             f"TP1 {tp1:.2f}\n"
             f"TP2 {tp2:.2f}\n"
             f"TP3 {tp3:.2f}\n"
             f"SL {sl:.2f}")

        for _ in range(5):
            send(msg)
            time.sleep(1.2)
    else:
        full = "✅" if (up_full or down_full) else "⚠️ جزئي"
        send(f"⏰ {t_str} [فريم 5د]\n"
             f"🥇 {price:.2f} [{src}]\n"
             f"📈 20:{ma20:.1f} 50:{ma50:.1f} 100:{ma100:.1f} 200@14:{ma200:.1f} {full}\n"
             f"📊 RSI {r:.1f} MACD {macd_v:.3f}\n"
             f"📐 فيبو 0:{fib_0:.1f} 0.25:{fib_25:.1f} 0.5:{fib_50:.1f} 1:{fib_100:.1f}\n"
             f"🚫 لا اشارة - السعر بعيد عن OB/فيبو >2.5$")

print("MT5 price 5m done")
