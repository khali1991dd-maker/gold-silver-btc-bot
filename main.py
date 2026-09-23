import os, requests, datetime, time, json, pandas as pd

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
FILE = "exness_prices.json"

def send(text):
    try: requests.post(TG_URL, data={"chat_id": CHAT, "text": text, "parse_mode": "Markdown"}, timeout=20)
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
    for _ in range(3):
        try:
            r=requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            p=float(r.get('price',0))
            if 4000 < p < 5000: return p
        except: time.sleep(1)
    return None

def get_15m_data():
    # سوق عالمي مباشر - PAXGUSDT = الذهب
    try:
        url="https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=15m&limit=100"
        r=requests.get(url, timeout=15).json()
        if not isinstance(r, list): return None
        df=pd.DataFrame(r, columns=['o_t','o','h','l','c','v','c_t','q','n','tb','tq','i'])
        df['h']=df['h'].astype(float); df['l']=df['l'].astype(float)
        df['o']=df['o'].astype(float); df['c']=df['c'].astype(float)
        return df
    except: return None

def calc_fib_and_ob(df15):
    if df15 is None or len(df15)<20: return None
    last20=df15.tail(20)
    swing_high=last20['h'].max()
    swing_low=last20['l'].min()
    diff=swing_high-swing_low
    fib25 = swing_high - diff*0.25
    fib50 = swing_high - diff*0.50
    fibs={"high":swing_high,"low":swing_low,"25":fib25,"50":fib50,"0":swing_high,"100":swing_low}

    # أوردر بلوك مبسط 15د
    bullish_ob=None; bearish_ob=None
    for i in range(len(df15)-3, 10, -1):
        # بلوك شرائي: شمعة هابطة قوية بعدها صاعدة
        if df15.iloc[i]['c'] < df15.iloc[i]['o'] and df15.iloc[i+1]['c'] > df15.iloc[i+1]['o']:
            bullish_ob=(df15.iloc[i]['l'], df15.iloc[i]['h'])
            break
    for i in range(len(df15)-3, 10, -1):
        if df15.iloc[i]['c'] > df15.iloc[i]['o'] and df15.iloc[i+1]['c'] < df15.iloc[i+1]['o']:
            bearish_ob=(df15.iloc[i]['l'], df15.iloc[i]['h'])
            break

    return fibs, bullish_ob, bearish_ob

def calc_m1():
    try:
        if not os.path.exists(FILE): return None,0
        data=json.load(open(FILE))
        if len(data)<50: return None,len(data)
        prices=pd.Series([x["price"] for x in data])
        ma20=prices.ewm(span=20, adjust=False).mean().iloc[-1]
        ma50=prices.ewm(span=50, adjust=False).mean().iloc[-1]
        ma100=prices.ewm(span=100, adjust=False).mean().iloc[-1]
        ma200_14=prices.ewm(span=200, adjust=False).mean().shift(14).iloc[-1] if len(prices)>214 else ma100
        rsi=rsi_func(prices,14).iloc[-1]
        return (ma20,ma50,ma100,ma200_14,rsi,prices), len(data)
    except: return None,0

# ----- START -----
now=get_time()
w_time=now.strftime("%d-%m-%Y %I:%M %p")
if not is_open(now):
    send(f"⏰ {w_time} - السوق مغلق"); exit()

live_price=get_exness_price()
if not live_price: exit()

# حفظ السعر
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

if calc is None or fib_data is None:
    send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 {live_price:.2f}\n⏳ يجمع {count}/50"); exit()

ma20,ma50,ma100,ma200_14,rsi,prices=calc
fibs,bull_ob,bear_ob=fib_data

# الترتيب
buy_order = ma20>ma50>ma100 and live_price>ma200_14
sell_order = ma20<ma50<ma100 and live_price<ma200_14

# فيبو قريب؟
near_fib25 = abs(live_price-fibs["25"])<5
near_fib50 = abs(live_price-fibs["50"])<5
golden_fib = near_fib25 or near_fib50

# أوردر بلوك
in_bull_ob = bull_ob and bull_ob[0] <= live_price <= bull_ob[1]
in_bear_ob = bear_ob and bear_ob[0] <= live_price <= bear_ob[1]

golden_zone = golden_fib or in_bull_ob or in_bear_ob

# RSI
rsi_buy = rsi<=30
rsi_sell = rsi>=70

# القرار
signal="⚪ انتظار"
if buy_order and (rsi_buy or golden_zone):
    signal="🟢 شراء قوي" if golden_zone and rsi_buy else "🟢 شراء"
elif sell_order and (rsi_sell or golden_zone):
    signal="🔴 بيع قوي" if golden_zone and rsi_sell else "🔴 بيع"

# رسالة
fib_txt=f"0%={fibs['high']:.1f} | 25%={fibs['25']:.1f} | 50%={fibs['50']:.1f} | 100%={fibs['low']:.1f}"
ob_txt=""
if bull_ob: ob_txt+=f"\n🟩 بلوك شرائي: {bull_ob[0]:.1f}-{bull_ob[1]:.1f} {'✅ داخل' if in_bull_ob else ''}"
if bear_ob: ob_txt+=f"\n🟥 بلوك بيعي: {bear_ob[0]:.1f}-{bear_ob[1]:.1f} {'✅ داخل' if in_bear_ob else ''}"

gold_txt="🔥 منطقة ذهبية" if golden_zone else "منطقة عادية"

msg=f"""⏰ {w_time} - M1 إكسنس ✅
🥇 لايف: {live_price:.2f}

📈 موفنجات:
ش0=20:{ma20:.2f} | 50:{ma50:.2f} | 100:{ma100:.2f}
ش14=200:{ma200_14:.2f}

📊 RSI14: {rsi:.2f} {'🟢 تشبع بيعي' if rsi_buy else '🔴 تشبع شرائي' if rsi_sell else ''}

📐 فيبو 15د:
{fib_txt}

🏦 أوردر بلوك 15د:{ob_txt}

{gold_txt}
📋 ترتيب: {'20>50>100 ✅' if ma20>ma50>ma100 else '20<50<100 ✅' if ma20<ma50<ma100 else 'غير مرتب'}

🎯 الإشارة: {signal}
"""

send(msg)
