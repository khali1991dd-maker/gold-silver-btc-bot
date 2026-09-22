import os, requests, datetime, time, pandas as pd, numpy as np, yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try: requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=20)
    except: pass

def get_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_open(m):
    if m.weekday()==5: return False
    if m.weekday()==4 and m.hour>=23: return False
    if m.weekday()==6 and m.hour<1: return False
    return True

def rsi(s, p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    rs=g/l; return 100-(100/(1+rs))

def atr(h,l,c,p=14):
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/p).mean()

def get_gold_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if 4000 < p < 5000: return p, "سعر إكسنس المباشر"
    except: pass
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5).json()
        p=float(r['price'])
        if 4000 < p < 5000: return p, "سعر إكسنس"
    except: pass
    return None, None

now=get_time()
وقت=now.strftime("%d-%m-%Y %I:%M %p")

if not is_open(now):
    send(f"⏰ الوقت: {وقت} - فريم 5 دقائق\n🥇 السوق مغلق")
    exit()

df=yf.download("XAUUSD=X", period="10d", interval="5m", progress=False, auto_adjust=True)
if df.empty or len(df)<200:
    df=yf.download("GC=F", period="10d", interval="5m", progress=False, auto_adjust=True)
if isinstance(df.columns, pd.MultiIndex):
    df.columns=df.columns.get_level_values(0)

c,h,l=df["Close"],df["High"],df["Low"]
df["ema20"]=c.ewm(span=20).mean()
df["ema50"]=c.ewm(span=50).mean()
df["ema100"]=c.ewm(span=100).mean()
df["ema200"]=c.ewm(span=200).mean()
df["rsi"]=rsi(c,14)
df["macd"]=c.ewm(span=12).mean()-c.ewm(span=26).mean()
df["atr"]=atr(h,l,c,14)

price, src = get_gold_price()
if price is None:
    price=float(c.iloc[-1]); src="احتياطي"

ema20=float(df["ema20"].iloc[-1]); ema50=float(df["ema50"].iloc[-1]); ema100=float(df["ema100"].iloc[-1]); ema200=float(df["ema200"].iloc[-1])
r=float(df["rsi"].iloc[-1]); macd=float(df["macd"].iloc[-1]); atr_v=float(df["atr"].iloc[-1])

# فيبو
recent_high=float(h.tail(50).max()); recent_low=float(l.tail(50).min())
diff=recent_high-recent_low
f0=recent_high; f25=recent_high-diff*0.25; f50=recent_high-diff*0.5; f100=recent_low

# اهم تغيير: مسافة 5 دولار
مسافة_قريبة=5.0

اشارة=None; دخول=0; سبب=""

# منطق الدخول
if abs(price-f50) <= مسافة_قريبة and price > ema20 and r < 65:
    اشارة="شراء"; دخول=f50; سبب=f"قريب من فيبو 50% ({f50:.1f}) + فوق متوسط 20"
elif abs(price-f25) <= مسافة_قريبة and price > ema50:
    اشارة="شراء"; دخول=f25; سبب=f"قريب من فيبو 25% ({f25:.1f})"
elif abs(price-f100) <= مسافة_قريبة and price < ema20 and r > 35:
    اشارة="بيع"; دخول=f100; سبب=f"قريب من فيبو 100% ({f100:.1f}) + تحت متوسط 20"
elif abs(price-f0) <= مسافة_قريبة and price < ema50:
    اشارة="بيع"; دخول=f0; سبب=f"قريب من فيبو 0% ({f0:.1f})"

if اشارة:
    if اشارة=="شراء":
        هدف1=dخول+atr_v*1.5; هدف2=dخول+atr_v*3; وقف=dخول-atr_v*2
    else:
        هدف1=dخول-atr_v*1.5; هدف2=dخول-atr_v*3; وقف=dخول+atr_v*2

    رسالة=(f"⚡️ اشارة {اشارة} - فريم 5 دقائق\n"
           f"⏰ الوقت: {وقت}\n"
           f"🥇 سعر الذهب: {price:.2f} دولار [{src}]\n"
           f"📦 السبب: {سبب}\n"
           f"📈 المتوسطات: 20={ema20:.1f} | 50={ema50:.1f} | 100={ema100:.1f} | 200={ema200:.1f}\n"
           f"📊 القوة النسبية: {r:.1f} | الماكد: {macd:.3f} | ATR: {atr_v:.2f}\n\n"
           f"💵 دخول: {دخول:.2f}\n"
           f"🎯 هدف1: {هدف1:.2f}\n"
           f"🎯 هدف2: {هدف2:.2f}\n"
           f"🛑 وقف: {وقف:.2f}")
    for _ in range(3): send(رسالة); time.sleep(1)
else:
    # حساب اقرب مسافة
    d0=abs(price-f0); d25=abs(price-f25); d50=abs(price-f50); d100=abs(price-f100)
    اقرب=min(d0,d25,d50,d100)
    
    send(f"⏰ الوقت: {وقت} - فريم 5 دقائق\n"
         f"🥇 سعر الذهب: {price:.2f} دولار [{src}]\n"
         f"📈 المتوسطات: 20={ema20:.1f} | 50={ema50:.1f} | 100={ema100:.1f} | 200={ema200:.1f} - متذبذب ⚠️\n"
         f"📊 القوة النسبية: {r:.1f} | الماكد: {macd:.3f}\n"
         f"📐 فيبو: 0%={f0:.1f} | 25%={f25:.1f} | 50%={f50:.1f} | 100%={f100:.1f}\n"
         f"🚫 لا توجد اشارة حالياً - السعر بعيد عن مناطق فيبو والطلب بأكثر من {مسافة_قريبة} دولار (اقرب مسافة {اقرب:.1f}$) - ننتظر رجوع السعر")
