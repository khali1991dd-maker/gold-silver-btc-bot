import os, requests, datetime, yfinance as yf, pandas as pd, time

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    for _ in range(2): # محاولة ارسال
        try:
            r=requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
            if r.status_code==200: break
        except: time.sleep(1)

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(m):
    wd=m.weekday(); h=m.hour
    if wd==4 and h>=23: return False
    if wd==5: return False
    if wd==6 and h<1: return False
    return True

def rsi(s, p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))

def get_exness_price():
    # 3 مصادر للسعر الحقيقي
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if p>1000: return p, "Exness API"
    except: pass
    try:
        r=requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=5).json()
        p=float(r['items'][0]['xauPrice'])
        if p>1000: return p, "GoldPrice.org"
    except: pass
    return None, None

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 مغلق")
else:
    df=yf.download("GC=F", period="15d", interval="5m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]; h=df["High"]; l=df["Low"]; o=df["Open"]
    df["MA20"]=c.rolling(20).mean(); df["MA50"]=c.rolling(50).mean()
    df["MA100"]=c.rolling(100).mean(); df["MA200"]=c.rolling(200).mean()
    df["RSI"]=rsi(c,14)
    df["MACD"]=c.ewm(span=5).mean() - c.ewm(span=20).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean().iloc[-1]

    last=df.iloc[-1]
    real_price, src = get_exness_price()
    if real_price is None: # fallback اخير
        real_price=float(c.iloc[-1]); src="Yahoo (احتياطي)"

    r=float(last["RSI"]); macd_val=float(last["MACD"])

    # فيبو
    look=50
    rh=float(h[-look:].max()); rl=float(l[-look:].min()); fr=rh-rl
    fib50=rh-fr*0.5; fib618=rh-fr*0.618
    fib50_up=rl+fr*0.5
    near_fib = abs(real_price-fib50)<atr*0.7 or abs(real_price-fib618)<atr*0.7 or abs(real_price-fib50_up)<atr*0.7
    fib_txt = f"{fib618:.1f}"

    # بلوك اوردر
    ob_zone=0; ob_type=""
    for i in range(-12, -4):
        if o.iloc[i] > c.iloc[i] and (c.iloc[i+1]-o.iloc[i+1]) > atr*0.6:
            ob_zone=(o.iloc[i]+c.iloc[i])/2
            if abs(real_price-ob_zone) < atr*1.0:
                ob_type=f"OB شرائي {ob_zone:.1f}"; break
        if o.iloc[i] < c.iloc[i] and (o.iloc[i+1]-c.iloc[i+1]) > atr*0.6:
            ob_zone=(o.iloc[i]+c.iloc[i])/2
            if abs(real_price-ob_zone) < atr*1.0:
                ob_type=f"OB بيعي {ob_zone:.1f}"; break

    near_key = near_fib or (ob_type!="")
    up_trend = last["MA20"] > last["MA50"] > last["MA100"] > last["MA200"]
    down_trend = last["MA20"] < last["MA50"] < last["MA100"] < last["MA200"]

    signal=None; reason_key=""
    if 30 <= r <= 70 and near_key:
        if up_trend and macd_val > 0:
            signal="شراء"; reason_key = ob_type if ob_type else f"فيبو {fib_txt}"
        elif down_trend and macd_val < 0:
            signal="بيع"; reason_key = ob_type if ob_type else f"فيبو {fib_txt}"

    if signal:
        sl=real_price-atr*2 if signal=="شراء" else real_price+atr*2
        tp1=real_price+atr*1.5 if signal=="شراء" else real_price-atr*1.5
        tp2=real_price+atr*3 if signal=="شراء" else real_price-atr*3
        tp3=real_price+atr*4.5 if signal=="شراء" else real_price-atr*4.5

        msg=(f"🚀 {signal} الان [OB/فيبو] [سعر حقيقي {src}]\n"
             f"⏰ {t_str}\n💰 {real_price:.2f}\n"
             f"📦 {reason_key}\n📈 20>50>100>200 مرتبة\n📉 MACD {macd_val:.3f} {'فوق 0' if macd_val>0 else 'تحت 0'}\n📊 RSI {r:.1f}\n\n"
             f"دخول {real_price:.2f}\nهدف1 {tp1:.2f}\nهدف2 {tp2:.2f}\nهدف3 {tp3:.2f}\nوقف {sl:.2f}")

        # === 5 رسائل عند الصفقة ===
        for i in range(5):
            send(msg)
            time.sleep(1.5)
    else:
        send(f"⏰ {t_str}\n🥇 {real_price:.2f} [{src}]\n📊 RSI {r:.1f} MACD {macd_val:.3f}\n🚫 لا يوجد OB/فيبو قريب\n🤖 لا اشارة")

print("Done real price + 5 msgs")
