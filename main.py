import os, requests, datetime, time, json, pandas as pd

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
FILE = "exness_prices.json"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text, "parse_mode": "Markdown"}, timeout=20)
    except: pass

def get_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_open(m):
    if m.weekday()==5: return False
    if m.weekday()==4 and m.hour>=23: return False
    if m.weekday()==6 and m.hour<1: return False
    return True

def rsi_func(s, p=14):
    d=s.diff()
    g=d.clip(lower=0).ewm(alpha=1/p, min_periods=p).mean()
    l=-d.clip(upper=0).ewm(alpha=1/p, min_periods=p).mean()
    rs=g/l
    rsi=100-(100/(1+rs))
    return rsi.fillna(50)

def get_exness_price():
    for _ in range(5):
        try:
            r=requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            p=float(r.get('price',0))
            if 3000 < p < 6000: return p
        except: time.sleep(1)
    return None

def get_15m_data():
    # 1- يحاول من السوق العالمي
    try:
        url="https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=15m&limit=100"
        r=requests.get(url, timeout=12).json()
        if isinstance(r, list) and len(r)>20:
            df=pd.DataFrame(r, columns=['o_t','o','h','l','c','v','c_t','q','n','tb','tq','i'])
            for k in ['h','l','o','c']: df[k]=df[k].astype(float)
            return df
    except: pass
    # 2- خطة B من ملفك نفسه
    try:
        if os.path.exists(FILE):
            data=json.load(open(FILE))
            prices=[x["price"] for x in data]
            if len(prices)>=60:
                rows=[]
                for i in range(0, len(prices), 15):
                    chunk=prices[i:i+15]
                    if len(chunk)>=5:
                        rows.append({"o":chunk[0],"h":max(chunk),"l":min(chunk),"c":chunk[-1]})
                df=pd.DataFrame(rows)
                return df
    except: pass
    return None

def calc_fib_and_ob(df15):
    if df15 is None or len(df15)<20: return None
    last20=df15.tail(20)
    swing_high=last20['h'].max()
    swing_low=last20['l'].min()
    diff=swing_high-swing_low
    if diff==0: return None
    fibs={
        "high":swing_high, "low":swing_low,
        "0":swing_high, "25":swing_high-diff*0.25,
        "50":swing_high-diff*0.50, "100":swing_low
    }
    bullish_ob=None; bearish_ob=None
    # بلوك شرائي: اخر شمعة هابطة قبل صعود
    for i in range(len(df15)-3, 5, -1):
        if df15.iloc[i]['c'] < df15.iloc[i]['o'] and df15.iloc[i+1]['c'] > df15.iloc[i+1]['o']:
            bullish_ob=(df15.iloc[i]['l'], df15.iloc[i]['h']); break
    for i in range(len(df15)-3, 5, -1):
        if df15.iloc[i]['c'] > df15.iloc[i]['o'] and df15.iloc[i+1]['c'] < df15.iloc[i+1]['o']:
            bearish_ob=(df15.iloc[i]['l'], df15.iloc[i]['h']); break
    return fibs, bullish_ob, bearish_ob

def calc_m1():
    try:
        if not os.path.exists(FILE): return None,0
        data=json.load(open(FILE))
        if len(data)<30: return None,len(data)
        prices=pd.Series([x["price"] for x in data])
        ma20=prices.ewm(span=20, adjust=False).mean().iloc[-1]
        ma50=prices.ewm(span=50, adjust=False).mean().iloc[-1]
        ma100=prices.ewm(span=100, adjust=False).mean().iloc[-1]
        ma200_14=prices.ewm(span=200, adjust=False).mean().shift(14).iloc[-1] if len(prices)>214 else prices.ewm(span=200, adjust=False).mean().iloc[-1]
        rsi=rsi_func(prices,14).iloc[-1]
        return (ma20,ma50,ma100,ma200_14,rsi,prices), len(data)
    except Exception as e:
        print(e); return None,0

# ---------- START ----------
now=get_time()
w_time=now.strftime("%d-%m-%Y %I:%M %p")

if not is_open(now):
    send(f"⏰ {w_time} - السوق مغلق"); exit()

live_price=get_exness_price()
if not live_price: exit()

if not os.path.exists(FILE):
    json.dump([{"price":live_price} for _ in range(215)], open(FILE,"w"))

try: data=json.load(open(FILE))
except: data=[]

data.append({"price":live_price})
data=data[-1500:]
json.dump(data, open(FILE,"w"))

calc,count=calc_m1()
df15=get_15m_data()
fib_data=calc_fib_and_ob(df15)

if calc is None:
    send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 {live_price:.2f}\n⏳ يجمع {count}/215"); exit()

ma20,ma50,ma100,ma200_14,rsi,prices=calc

# اذا فيبو فشل - ارسل موفنجات فقط
if fib_data is None:
    send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 لايف: {live_price:.2f}\n📈 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f}\n📈 200 ش14={ma200_14:.2f}\n📊 RSI: {rsi:.2f}\n⏳ فيبو 15د قيد التجميع")
    exit()

fibs,bull_ob,bear_ob=fib_data

buy_order = ma20>ma50>ma100 and live_price>ma200_14
sell_order = ma20<ma50<ma100 and live_price<ma200_14

near_fib25 = abs(live_price-fibs["25"])<3
near_fib50 = abs(live_price-fibs["50"])<3
in_bull_ob = bull_ob and bull_ob[0] <= live_price <= bull_ob[1]
in_bear_ob = bear_ob and bear_ob[0] <= live_price <= bear_ob[1]

golden_zone = near_fib25 or near_fib50 or in_bull_ob or in_bear_ob
rsi_buy = rsi<=30
rsi_sell = rsi>=70

signal="⚪ انتظار"
if buy_order and (rsi_buy or golden_zone):
    signal="🟢 شراء قوي 🔥" if golden_zone and rsi_buy else "🟢 شراء"
elif sell_order and (rsi_sell or golden_zone):
    signal="🔴 بيع قوي 🔥" if golden_zone and rsi_sell else "🔴 بيع"

fib_txt=f"0%={fibs['high']:.1f} | 25%={fibs['25']:.1f} | 50%={fibs['50']:.1f} | 100%={fibs['low']:.1f}"
ob_txt=""
if bull_ob: ob_txt+=f"\n🟩 شرائي: {bull_ob[0]:.1f}-{bull_ob[1]:.1f} {'✅ داخل' if in_bull_ob else ''}"
if bear_ob: ob_txt+=f"\n🟥 بيعي: {bear_ob[0]:.1f}-{bear_ob[1]:.1f} {'✅ داخل' if in_bear_ob else ''}"
if not ob_txt: ob_txt="\nلا يوجد بلوك واضح"

gold_txt="🔥 منطقة ذهبية" if golden_zone else "منطقة عادية"
order_txt='20>50>100 ✅' if ma20>ma50>ma100 else '20<50<100 ✅' if ma20<ma50<ma100 else 'غير مرتب ❌'

msg=f"""⏰ {w_time} - M1 إكسنس ✅
🥇 لايف: {live_price:.2f}

📈 موفنجات:
ش0: 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f}
ش14: 200={ma200_14:.2f}

📊 RSI14: {rsi:.2f} {'🟢 تشبع بيعي' if rsi_buy else '🔴 تشبع شرائي' if rsi_sell else ''}

📐 فيبو 15د:
{fib_txt}

🏦 أوردر بلوك 15د:{ob_txt}

{gold_txt}
📋 ترتيب: {order_txt}

🎯 الإشارة: {signal}
✅ {count}/215
"""
send(msg)
