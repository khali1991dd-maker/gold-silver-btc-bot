import os, requests, datetime, time, json, pandas as pd, yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
FILE = "exness_prices.json"

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

def fast_fill_exness():
    # جيب 250 شمعة من ياهو وعدلها لسعر إكسنس
    ex_price = get_exness_price()
    if ex_price is None: return False
    try:
        df = yf.download("GC=F", period="1d", interval="1m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        if df.empty or len(df)<200: return False
        yahoo_last = float(df["Close"].iloc[-1])
        diff = ex_price - yahoo_last # فرق إكسنس وياهو

        # عدل كل الاسعار بفرق إكسنس
        prices = (df["Close"] + diff).tail(250).tolist()
        data = [{"price": float(p)} for p in prices]
        # اضف السعر الحالي
        data.append({"price": ex_price})
        data = data[-250:]
        with open(FILE,"w") as f: json.dump(data,f)
        return True
    except:
        return False

def calc_from_exness():
    if not os.path.exists(FILE): return None
    try:
        data=json.load(open(FILE))
        if len(data) < 200: return None
        prices=pd.Series([x["price"] for x in data])
        ema20=prices.ewm(span=20).mean().iloc[-1]
        ema50=prices.ewm(span=50).mean().iloc[-1]
        ema100=prices.ewm(span=100).mean().iloc[-1]
        ema200=prices.ewm(span=200).mean().iloc[-1]
        ema200_14=prices.ewm(span=200).mean().shift(14).iloc[-1]
        rsi=rsi_func(prices,14).iloc[-1]
        return ema20,ema50,ema100,ema200,ema200_14,rsi,len(data)
    except:
        return None

now=get_time()
w_time=now.strftime("%d-%m-%Y %I:%M %p")

if not is_open(now):
    send(f"⏰ {w_time} - M1\n🥇 السوق مغلق"); exit()

# اذا الملف فاضي - عبيه بسرعة
if not os.path.exists(FILE) or os.path.getsize(FILE) < 100:
    ok = fast_fill_exness()
    if not ok:
        send(f"⏰ {w_time}\n⚠️ فشل التعبئة السريعة"); exit()

price = get_exness_price()
if price is None: exit()

# حدث الملف بسعر جديد
try:
    data=json.load(open(FILE))
    data.append({"price": price})
    data=data[-250:]
    json.dump(data, open(FILE,"w"))
except: pass

result = calc_from_exness()
if result is None:
    send(f"⏰ {w_time}\n⚠️ لسه يجمع"); exit()

ema20,ema50,ema100,ema200_0,ema200_14,r,count=result
source=f"إكسنس ✅ سريع {count}/250"

up_filter=price>ema200_14; down_filter=price<ema200_14
up_order=ema20>ema50 and ema50>ema100
down_order=ema20<ema50 and ema50<ema100

signal=None; reason=""
if r <= 30 and up_filter and up_order:
    signal="شراء"; reason=f"تشبع بيعي RSI={r:.1f} <=30 + فوق 200(14)={ema200_14:.1f}"
elif r <= 35 and up_filter and price>ema20:
    signal="شراء"; reason=f"RSI={r:.1f} قريب 30 + فوق 200(14)"
elif r >= 70 and down_filter and down_order:
    signal="بيع"; reason=f"تشبع شرائي RSI={r:.1f} >=70 + تحت 200(14)={ema200_14:.1f}"
elif r >= 65 and down_filter and price<ema20:
    signal="بيع"; reason=f"RSI={r:.1f} قريب 70 + تحت 200(14)"

if signal:
    tp1=price+3 if signal=="شراء" else price-3
    tp2=price+6 if signal=="شراء" else price-6
    sl=price-4 if signal=="شراء" else price+4
    msg=(f"⚡️ اشارة {signal} - M1 إكسنس سريع\n"
         f"⏰ {w_time}\n"
         f"🥇 سعر الذهب: {price:.2f} [{source}]\n"
         f"📦 {reason}\n"
         f"📈 0: 20={ema20:.2f} | 50={ema50:.2f} | 100={ema100:.2f}\n"
         f"📈 200: حالي={ema200_0:.2f} | مزاح14={ema200_14:.2f}\n"
         f"📊 RSI: {r:.2f} (30/70)\n\n"
         f"💵 دخول: {price:.2f}\n🎯1: {tp1:.2f} 🎯2: {tp2:.2f} 🛑: {sl:.2f}")
    for _ in range(3): send(msg); time.sleep(1)
else:
    trend="فوق 200(14)" if up_filter else "تحت 200(14)"
    order_txt="20>50>100" if up_order else "20<50<100" if down_order else "عرضي"
    send(f"⏰ {w_time} - M1 [{source}]\n"
         f"🥇 سعر الذهب: {price:.2f}\n"
         f"📈 0: 20={ema20:.2f} | 50={ema50:.2f} | 100={ema100:.2f} - {order_txt}\n"
         f"📈 200(14): {ema200_14:.2f} - {trend}\n"
         f"📊 RSI: {r:.2f} (30/70)\n"
         f"🚫 لا توجد اشارة")
