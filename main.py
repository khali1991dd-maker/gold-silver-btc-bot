import os, requests, datetime, time, json, pandas as pd
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
    for _ in range(5):
        try:
            r=requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            p=float(r.get('price',0))
            if 4200 < p < 4500: return p
        except: time.sleep(1)
    return None

def fill_fast(current_price):
    # يحاول من Binance، اذا فشل يعبيه من السعر الحالي مباشرة = سريع
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=1m&limit=215"
        r = requests.get(url, timeout=10).json()
        if isinstance(r, list) and len(r) >= 100:
            data = [{"price": float(x[4])} for x in r]
            json.dump(data, open(FILE,"w"))
            return len(data), "binance"
    except: pass

    # الخطة B: عبيه 215 مرة من نفس سعر اكسنس - يشتغل فورا
    data = [{"price": current_price} for _ in range(215)]
    json.dump(data, open(FILE,"w"))
    return 215, "local"

def calc_m1():
    try:
        if not os.path.exists(FILE): return None, 0
        data=json.load(open(FILE))
        if len(data) < 215: return None, len(data)
        prices=pd.Series([x["price"] for x in data])
        ma20=prices.ewm(span=20, adjust=False).mean().iloc[-1]
        ma50=prices.ewm(span=50, adjust=False).mean().iloc[-1]
        ma100=prices.ewm(span=100, adjust=False).mean().iloc[-1]
        ma200_14=prices.ewm(span=200, adjust=False).mean().shift(14).iloc[-1]
        rsi=rsi_func(prices,14).iloc[-1]
        return (ma20,ma50,ma100,ma200_14,rsi), len(data)
    except: return None, 0

now=get_time()
w_time=now.strftime("%d-%m-%Y %I:%M %p")
if not is_open(now):
    send(f"⏰ {w_time} - M1\n🥇 السوق مغلق"); exit()

price=get_exness_price()
if price is None: exit()

# انشاء سريع اذا مافي ملف
if not os.path.exists(FILE):
    n, src = fill_fast(price)
    send(f"⚡️ تم تجميع {n}/215 فورا [{src}]")

# اضافة السعر الجديد
try:
    data=json.load(open(FILE))
except:
    data=[{"price": price} for _ in range(215)]

data.append({"price":price})
data=data[-1500:]
json.dump(data, open(FILE,"w"))

calc, count = calc_m1()
if calc is None:
    send(f"⏰ {w_time} - M1\n🥇 {price:.2f}\n⏳ {count}/215"); exit()

ma20,ma50,ma100,ma200_14,rsi = calc
send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 الذهب: {price:.2f}\n📈 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f}\n📈 200 ش14={ma200_14:.2f}\n📊 RSI: {rsi:.2f}\n✅ {count}/215 مكتمل")
