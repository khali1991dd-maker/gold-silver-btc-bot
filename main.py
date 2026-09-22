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

def rsi_func(s, p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    rs=g/l; return 100-(100/(1+rs))

def atr_func(h,l,c,p=14):
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/p).mean()

def get_exness_price():
    for i in range(5):
        try:
            r=requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            p=float(r.get('price',0))
            if 4200 < p < 4500: return p
        except: time.sleep(1)
        try:
            r=requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=10).json()
            p=float(r['items'][0]['xauPrice'])
            if 4200 < p < 4500: return p
        except: time.sleep(1)
    return None

now=get_time()
w_time=now.strftime("%d-%m-%Y %I:%M %p")

if not is_open(now):
    send(f"⏰ الوقت: {w_time} - فريم دقيقة M1\n🥇 السوق مغلق")
    exit()

df = yf.download("GC=F", period="3d", interval="1m", progress=False, auto_adjust=True)
if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)

if df.empty or len(df)<200:
    send(f"⏰ {w_time}\n⚠️ لا توجد بيانات")
    exit()

c,h,l=df["Close"],df["High"],df["Low"]
df["ema20"]=c.ewm(span=20).mean()
df["ema50"]=c.ewm(span=50).mean()
df["ema100"]=c.ewm(span=100).mean()
df["ema200"]=c.ewm(span=200).mean()
df["rsi"]=rsi_func(c,14)
df["macd"]=c.ewm(span=12).mean()-c.ewm(span=26).mean()
df["atr"]=atr_func(h,l,c,14)

price = get_exness_price()
if price is None:
    send(f"⏰ {w_time}\n⚠️ فشل جلب سعر إكسنس")
    exit()

ema20=float(df["ema20"].iloc[-1]); ema50=float(df["ema50"].iloc[-1]); ema100=float(df["ema100"].iloc[-1]); ema200=float(df["ema200"].iloc[-1])
r=float(df["rsi"].iloc[-1]); macd=float(df["macd"].iloc[-1]); atr_v=float(df["atr"].iloc[-1])

recent_high=float(h.tail(100).max()); recent_low=float(l.tail(100).min())
diff=recent_high-recent_low
f0=recent_high; f25=recent_high-diff*0.25; f50=recent_high-diff*0.5; f100=recent_low

distance=3.0
signal=None; entry=0; reason=""

trend_up = ema20 > ema50 and ema50 > ema100 and macd > 0 and r > 50 and price > ema20
trend_down = ema20 < ema50 and ema50 < ema100 and macd < 0 and r < 50 and price < ema20
trend_down_strong = ema20 < ema50 and macd < -0.5 and r < 40
trend_up_strong = ema20 > ema50 and macd > 0.5 and r > 60

# 1- اشارات فيبو
if abs(price-f50) <= distance and trend_up:
    signal="شراء"; entry=f50; reason=f"فيبو 50% ({f50:.1f}) + ترند صاعد"
elif abs(price-f25) <= distance and trend_up:
    signal="شراء"; entry=f25; reason=f"فيبو 25% ({f25:.1f}) + ترند صاعد"
elif abs(price-f100) <= distance and trend_down:
    signal="بيع"; entry=f100; reason=f"فيبو 100% ({f100:.1f}) + ترند هابط"
elif abs(price-f0) <= distance and trend_down:
    signal="بيع"; entry=f0; reason=f"فيبو 0% ({f0:.1f}) + ترند هابط"
# 2- اشارات ترند قوي مباشر - زي حالتك الحين
elif trend_down_strong and price < ema20:
    signal="بيع"; entry=price; reason=f"هبوط قوي مباشر RSI={r:.1f} MACD={macd:.2f} تحت EMA20"
elif trend_up_strong and price > ema20:
    signal="شراء"; entry=price; reason=f"صعود قوي مباشر RSI={r:.1f} MACD={macd:.2f} فوق EMA20"

if signal:
    if signal=="شراء":
        tp1=entry+atr_v*1.5; tp2=entry+atr_v*3; sl=entry-atr_v*2
    else:
        tp1=entry-atr_v*1.5; tp2=entry-atr_v*3; sl=entry+atr_v*2
    msg=(f"⚡️ اشارة {signal} - فريم دقيقة M1\n"
           f"⏰ الوقت: {w_time}\n"
           f"🥇 سعر الذهب: {price:.2f} دولار [إكسنس ✅]\n"
           f"📦 السبب: {reason}\n"
           f"📈 متوسطات: 20={ema20:.1f} | 50={ema50:.1f} | 100={ema100:.1f} | 200={ema200:.1f}\n"
           f"📊 RSI: {r:.1f} | MACD: {macd:.3f} | ATR: {atr_v:.2f}\n\n"
           f"💵 دخول: {entry:.2f}\n"
           f"🎯 هدف1: {tp1:.2f}\n"
           f"🎯 هدف2: {tp2:.2f}\n"
           f"🛑 وقف: {sl:.2f}")
    for _ in range(5):
        send(msg); time.sleep(2)
else:
    d0=abs(price-f0); d25=abs(price-f25); d50=abs(price-f50); d100=abs(price-f100)
    nearest=min(d0,d25,d50,d100)
    trend_txt = "صاعد" if ema20>ema50 else "هابط"
    send(f"⏰ الوقت: {w_time} - فريم دقيقة M1\n"
         f"🥇 سعر الذهب: {price:.2f} دولار [إكسنس ✅]\n"
         f"📈 متوسطات: 20={ema20:.1f} | 50={ema50:.1f} | 100={ema100:.1f} | 200={ema200:.1f} - ترند {trend_txt}\n"
         f"📊 RSI: {r:.1f} | MACD: {macd:.3f}\n"
         f"📐 فيبو: 0%={f0:.1f} | 25%={f25:.1f} | 50%={f50:.1f} | 100%={f100:.1f}\n"
         f"🚫 لا توجد اشارة - اقرب مسافة {nearest:.1f}$")
