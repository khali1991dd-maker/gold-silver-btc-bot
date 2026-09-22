import os, requests, datetime, time, pandas as pd, yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
def send(t):
    try: requests.post(TG_URL, data={"chat_id": CHAT, "text": t}, timeout=20)
    except: pass

def get_muscat_time(): return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)
def is_market_open(m):
    return not (m.weekday()==5 or (m.weekday()==4 and m.hour>=23) or (m.weekday()==6 and m.hour<1))
def rsi(s,p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))
def get_exness_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=6).json()
        p=float(r.get('price',0))
        if p>1000: return p,"Exness مباشر"
    except: pass
    return None,None

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 مغلق")
else:
    # === فريم 5 دقايق مثبت ===
    df=yf.download("XAUUSD=X", period="30d", interval="5m", progress=False, auto_adjust=True)
    if df.empty: df=yf.download("GC=F", period="30d", interval="5m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c,h,l,o=df["Close"],df["High"],df["Low"],df["Open"]

    df["ma20"]=c.rolling(20).mean() # 0 شمعة
    df["ma50"]=c.rolling(50).mean() # 0 شمعة
    df["ma100"]=c.rolling(100).mean() # 0 شمعة
    df["ma200"]=c.rolling(200).mean().shift(14) # 14 شمعة

    df["rsi"]=rsi(c,14)
    df["macd"]=c.ewm(span=5).mean()-c.ewm(span=20).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean().iloc[-1]

    price,src=get_exness_price()
    if price is None: price=float(c.iloc[-1]); src="سبوت"

    r=float(df["rsi"].iloc[-1]); macd_val=float(df["macd"].iloc[-1])
    rh,rl=float(h[-50:].max()),float(l[-50:].min()); fr=rh-rl
    fib_25,fib_50=rh-fr*0.25,rh-fr*0.5
    near_fib=abs(price-fib_25)<atr*0.7 or abs(price-fib_50)<atr*0.7

    ob_txt=""
    for i in range(-12,-4):
        if o.iloc[i]>c.iloc[i] and (c.iloc[i+1]-o.iloc[i+1])>atr*0.6:
            zp=(o.iloc[i]+c.iloc[i])/2
            if abs(price-zp)<atr*1.0: ob_txt=f"OB شرائي {zp:.1f}"; break
        if o.iloc[i]<c.iloc[i] and (o.iloc[i+1]-c.iloc[i+1])>atr*0.6:
            zp=(o.iloc[i]+c.iloc[i])/2
            if abs(price-zp)<atr*1.0: ob_txt=f"OB بيعي {zp:.1f}"; break

    near=near_fib or ob_txt!=""
    ma20,ma50,ma100,ma200=df["ma20"].iloc[-1],df["ma50"].iloc[-1],df["ma100"].iloc[-1],df["ma200"].iloc[-1]
    up=ma20>ma50>ma100>ma200; down=ma20<ma50<ma100<ma200

    sig=None
    if 30<=r<=70 and near:
        if up and macd_val>0: sig="شراء"
        elif down and macd_val<0: sig="بيع"

    if sig:
        sl=price-atr*2 if sig=="شراء" else price+atr*2
        tp1=price+atr*1.5 if sig=="شراء" else price-atr*1.5
        tp2=price+atr*3 if sig=="شراء" else price-atr*3
        tp3=price+atr*4.5 if sig=="شراء" else price-atr*4.5
        reason=ob_txt if ob_txt else f"فيبو 0.5 {fib_50:.1f}"
        msg=(f"🚀 {sig} [فريم 5د]\n⏰ {t_str}\n💰 {price:.2f} [{src}]\n📦 {reason}\n📈 20/50/100@0 + 200@14\n📉 MACD {macd_val:.3f} {'فوق 0' if macd_val>0 else 'تحت 0'}\n📊 RSI {r:.1f}\n\nدخول {price:.2f}\nTP1 {tp1:.2f}\nTP2 {tp2:.2f}\nTP3 {tp3:.2f}\nSL {sl:.2f}")
        for _ in range(5): send(msg); time.sleep(1.2)
    else:
        send(f"⏰ {t_str} [فريم 5د]\n🥇 {price:.2f} [{src}]\n📈 20:{ma20:.1f} 50:{ma50:.1f} 100:{ma100:.1f} 200@14:{ma200:.1f}\n📊 RSI {r:.1f} MACD {macd_val:.3f}\n📐 فيبو 0.25:{fib_25:.1f} 0.5:{fib_50:.1f}\n🚫 لا اشارة")

print("5m done")
