import os
import requests
import datetime
import time
import pandas as pd
import yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=20)
    except:
        pass

def get_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_open(m):
    if m.weekday() == 5:
        return False
    if m.weekday() == 4 and m.hour >= 23:
        return False
    if m.weekday() == 6 and m.hour < 1:
        return False
    return True

def rsi_func(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1/p).mean()
    l = -d.clip(upper=0).ewm(alpha=1/p).mean()
    rs = g / l
    return 100 - (100 / (1 + rs))

def get_exness_price():
    for i in range(5):
        try:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            p = float(r.get('price', 0))
            if 4200 < p < 4500:
                return p
        except:
            time.sleep(1)
        try:
            r = requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=10).json()
            p = float(r['items'][0]['xauPrice'])
            if 4200 < p < 4500:
                return p
        except:
            time.sleep(1)
    return None

now = get_time()
w_time = now.strftime("%d-%m-%Y %I:%M %p")

if not is_open(now):
    send(f"⏰ الوقت: {w_time} - فريم دقيقة M1\n🥇 السوق مغلق")
    exit()

# فريم دقيقة M1
df = yf.download("GC=F", period="2d", interval="1m", progress=False, auto_adjust=True)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

if df.empty or len(df) < 220:
    send(f"⏰ {w_time}\n⚠️ لا توجد بيانات")
    exit()

c = df["Close"]

# موفنجات شمعة 0
df["ema20"] = c.ewm(span=20).mean()
df["ema50"] = c.ewm(span=50).mean()
df["ema100"] = c.ewm(span=100).mean()

# موفنج 200 شمعة 0 + مزاح 14
df["ema200"] = c.ewm(span=200).mean()
df["ema200_14"] = df["ema200"].shift(14)

# RSI 14
df["rsi"] = rsi_func(c, 14)

price = get_exness_price()
if price is None:
    send(f"⏰ {w_time}\n⚠️ فشل جلب سعر إكسنس - M1")
    exit()

ema20 = float(df["ema20"].iloc[-1])
ema50 = float(df["ema50"].iloc[-1])
ema100 = float(df["ema100"].iloc[-1])
ema200_0 = float(df["ema200"].iloc[-1])
ema200_14 = float(df["ema200_14"].iloc[-1])
r = float(df["rsi"].iloc[-1])

signal = None
reason = ""

up_filter = price > ema200_14
down_filter = price < ema200_14

up_order = ema20 > ema50 and ema50 > ema100
down_order = ema20 < ema50 and ema50 < ema100

# شروط RSI 30/70
if r <= 30 and up_filter and up_order:
    signal = "شراء"
    reason = f"تشبع بيعي RSI={r:.1f} <=30 + فوق EMA200(14)={ema200_14:.1f} + ترتيب صاعد 20>50>100"
elif r <= 35 and up_filter and price > ema20:
    signal = "شراء"
    reason = f"RSI={r:.1f} قريب من 30 + فوق EMA200(14)={ema200_14:.1f} + فوق EMA20"

elif r >= 70 and down_filter and down_order:
    signal = "بيع"
    reason = f"تشبع شرائي RSI={r:.1f} >=70 + تحت EMA200(14)={ema200_14:.1f} + ترتيب هابط 20<50<100"
elif r >= 65 and down_filter and price < ema20:
    signal = "بيع"
    reason = f"RSI={r:.1f} قريب من 70 + تحت EMA200(14)={ema200_14:.1f} + تحت EMA20"

if signal:
    if signal == "شراء":
        tp1 = price + 3
        tp2 = price + 6
        sl = price - 4
    else:
        tp1 = price - 3
        tp2 = price - 6
        sl = price + 4

    msg = (f"⚡️ اشارة {signal} - فريم دقيقة M1\n"
           f"⏰ الوقت: {w_time}\n"
           f"🥇 سعر الذهب: {price:.2f} دولار [إكسنس ✅]\n"
           f"📦 السبب: {reason}\n"
           f"📈 موفنج 0: 20={ema20:.1f} | 50={ema50:.1f} | 100={ema100:.1f}\n"
           f"📈 موفنج 200: حالي={ema200_0:.1f} | مزاح14={ema200_14:.1f}\n"
           f"📊 RSI: {r:.1f} (30 شراء / 70 بيع)\n\n"
           f"💵 دخول: {price:.2f}\n"
           f"🎯 هدف1: {tp1:.2f}\n"
           f"🎯 هدف2: {tp2:.2f}\n"
           f"🛑 وقف: {sl:.2f}")
    for _ in range(3):
        send(msg)
        time.sleep(1)
else:
    trend = "صاعد - فوق 200(14)" if up_filter else "هابط - تحت 200(14)"
    order_txt = "20>50>100" if up_order else "20<50<100" if down_order else "عرضي"
    send(f"⏰ الوقت: {w_time} - فريم دقيقة M1\n"
         f"🥇 سعر الذهب: {price:.2f} دولار [إكسنس ✅]\n"
         f"📈 موفنج 0: 20={ema20:.1f} | 50={ema50:.1f} | 100={ema100:.1f} - {order_txt}\n"
         f"📈 موفنج 200(14): {ema200_14:.1f} - {trend}\n"
         f"📊 RSI: {r:.1f} (30/70)\n"
         f"🚫 لا توجد اشارة - RSI في الوسط")
