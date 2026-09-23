import os, requests, datetime, time, json, pandas as pd

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
FILE = "exness_prices.json"
STATE_FILE = "last_signal.json"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text, "parse_mode": "Markdown"}, timeout=20)
        time.sleep(1)
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
    try:
        url="https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=15m&limit=100"
        r=requests.get(url, timeout=12).json()
        if isinstance(r, list) and len(r)>10:
            df=pd.DataFrame(r, columns=['o_t','o','h','l','c','v','c_t','q','n','tb','tq','i'])
            for k in ['h','l','o','c']: df[k]=df[k].astype(float)
            return df
    except: pass
    try:
        if os.path.exists(FILE):
            data=json.load(open(FILE))
            prices=[x["price"] for x in data]
            if len(prices)>=30:
                rows=[]
                for i in range(0, len(prices), 15):
                    chunk=prices[i:i+15]
                    if len(chunk)>=3:
                        rows.append({"o":chunk[0],"h":max(chunk),"l":min(chunk),"c":chunk[-1]})
                df=pd.DataFrame(rows)
                if len(df)>=5: return df
    except: pass
    return None

def calc_fib_and_ob(df15):
    if df15 is None or len(df15)<5: return None
    last10=df15.tail(10)
    swing_high=last10['h'].max()
    swing_low=last10['l'].min()
    diff=swing_high-swing_low
    if diff < 0.5: diff = 5.0
    fibs={"high":swing_high,"low":swing_low,"0":swing_high,"25":swing_high-diff*0.25,"50":swing_high-diff*0.50,"100":swing_low}
    bullish_ob=None; bearish_ob=None
    for i in range(len(df15)-2, 2, -1):
        if df15.iloc[i]['c'] < df15.iloc[i]['o'] and df15.iloc[i+1]['c'] > df15.iloc[i+1]['o']:
            bullish_ob=(df15.iloc[i]['l'], df15.iloc[i]['h']); break
    for i in range(len(df15)-2, 2, -1):
        if df15.iloc[i]['c'] > df15.iloc[i]['o'] and df15.iloc[i+1]['c'] < df15.iloc[i+1]['o']:
            bearish_ob=(df15.iloc[i]['l'], df15.iloc[i]['h']); break
    return fibs, bullish_ob, bearish_ob

def calc_m1():
    try:
        if not os.path.exists(FILE): return None,0
        data=json.load(open(FILE))
        if len(data)<30: return None,len(data)
        prices=pd.Series([x["price"] for x in data])
        ma20=prices.ewm(span=20, adjust=False).mean()
        ma50=prices.ewm(span=50, adjust=False).mean()
        ma100=prices.ewm(span=100, adjust=False).mean()
        ma200=prices.ewm(span=200, adjust=False).mean()
        return (ma20.iloc[-1], ma50.iloc[-1], ma100.iloc[-1], ma200.shift(14).iloc[-1], rsi_func(prices,14).iloc[-1], prices, ma20.iloc[-5], ma50.iloc[-5]), len(data)
    except: return None,0

def load_state():
    try: return json.load(open(STATE_FILE))
    except: return {"last_signal":""}

def save_state(s):
    json.dump(s, open(STATE_FILE,"w"))

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

ma20,ma50,ma100,ma200_14,rsi,prices,ma20_5,ma50_5=calc
if fib_data is None:
    send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 لايف: {live_price:.2f}\n📈 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f}\n📊 RSI: {rsi:.2f}"); exit()

fibs,bull_ob,bear_ob=fib_data

# فلاتر الترند الجديدة
buy_order = ma20>ma50>ma100
sell_order = ma20<ma50<ma100
ma20_down = ma20 < ma20_5
ma20_up = ma20 > ma20_5
below_all = live_price < ma20 and live_price < ma50 and live_price < ma100
above_all = live_price > ma20 and live_price > ma50 and live_price > ma100
strong_down = sell_order and ma20_down and below_all and live_price < ma200_14
strong_up = buy_order and ma20_up and above_all and live_price > ma200_14

near_fib25 = abs(live_price-fibs["25"])<4
near_fib50 = abs(live_price-fibs["50"])<4
in_bull_ob = bull_ob and bull_ob[0] <= live_price <= bull_ob[1]
in_bear_ob = bear_ob and bear_ob[0] <= live_price <= bear_ob[1]
golden_zone = near_fib25 or near_fib50 or in_bull_ob or in_bear_ob

# منطق الإشارة مع احترام الترند
if strong_down:
    if rsi >= 60 and golden_zone:
        signal="SELL_STRONG"; signal_txt="🔴🔴 بيع مع الترند الهابط 🔥 ارتداد للموفنج"
    elif rsi >= 50:
        signal="SELL"; signal_txt="🔴 بيع - ترند هابط قوي"
    elif rsi <= 20:
        signal="WAIT"; signal_txt="⚠️ هبوط قوي - لا تشتري رغم تشبع RSI - انتظر"
    else:
        signal="WAIT"; signal_txt="⚪ انتظار - هبوط قوي"
elif strong_up:
    if rsi <= 40 and golden_zone:
        signal="BUY_STRONG"; signal_txt="🟢🟢 شراء مع الترند الصاعد 🔥"
    elif rsi <= 50:
        signal="BUY"; signal_txt="🟢 شراء - ترند صاعد قوي"
    elif rsi >= 80:
        signal="WAIT"; signal_txt="⚠️ صعود قوي - لا تبيع رغم التشبع"
    else:
        signal="WAIT"; signal_txt="⚪ انتظار - صعود قوي"
else:
    # سوق جانبي - نستخدم RSI والذهبية
    if rsi <= 15 and golden_zone and not sell_order:
        signal="BUY_STRONG"; signal_txt="🟢🟢 شراء قوي جدا 🔥 قاع"
    elif rsi <= 25 and golden_zone and not sell_order:
        signal="BUY_STRONG"; signal_txt="🟢 شراء قوي 🔥 RSI + ذهبية"
    elif rsi >= 85 and golden_zone and not buy_order:
        signal="SELL_STRONG"; signal_txt="🔴🔴 بيع قوي جدا 🔥 قمة"
    elif rsi >= 75 and golden_zone and not buy_order:
        signal="SELL_STRONG"; signal_txt="🔴 بيع قوي 🔥"
    elif rsi <= 30 and buy_order:
        signal="BUY"; signal_txt="🟢 شراء"
    elif rsi >= 70 and sell_order:
        signal="SELL"; signal_txt="🔴 بيع"
    else:
        signal="WAIT"; signal_txt="⚪ انتظار - سوق جانبي"

state=load_state()
fib_txt=f"0%={fibs['high']:.1f} | 25%={fibs['25']:.1f} | 50%={fibs['50']:.1f} | 100%={fibs['low']:.1f}"
trend_txt="🔴 هبوط قوي" if strong_down else "🟢 صعود قوي" if strong_up else "↔️ جانبي"

msg=f"""⏰ {w_time} - M1 إكسنس ✅
🥇 لايف: {live_price:.2f}
📈 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f} | 200={ma200_14:.2f}
📊 RSI: {rsi:.2f} | ترند: {trend_txt}
📐 فيبو: {fib_txt}
🎯 {signal_txt}
✅ {count}
"""
send(msg)

if signal in ["BUY_STRONG","SELL_STRONG"] and state.get("last_signal")!= signal+f"{int(live_price)}":
    if "BUY" in signal:
        entry=live_price; sl=fibs["low"]-3.0; tp1=fibs["50"]; tp2=fibs["25"]; tp3=fibs["high"]
        send(f"🚨 1️⃣ دخول شراء\n⏰ {w_time}\n🥇 دخول: {entry:.2f}\n📍 {trend_txt} + RSI {rsi:.1f}\n🔥 منطقة ذهبية")
        send(f"🎯 2️⃣ الأهداف\n🥇 دخول: {entry:.2f}\n🎯 هدف 1: {tp1:.2f} (50%)\n🎯 هدف 2: {tp2:.2f} (25%)\n🎯 هدف 3: {tp3:.2f} (0% القمة)\n💰 حرك الستوب للدخول بعد هدف1")
        send(f"🛑 3️⃣ وقف الخسارة\n🛑 ستوب: {sl:.2f}\n⚠️ المخاطرة: {abs(entry-sl):.2f}$")
    else:
        entry=live_price; sl=fibs["high"]+3.0; tp1=fibs["50"]; tp2=fibs["25"]; tp3=fibs["low"]
        send(f"🚨 1️⃣ دخول بيع\n⏰ {w_time}\n🥇 دخول: {entry:.2f}\n📍 {trend_txt} + RSI {rsi:.1f}\n🔥 منطقة ذهبية")
        send(f"🎯 2️⃣ الأهداف\n🥇 دخول: {entry:.2f}\n🎯 هدف 1: {tp1:.2f} (50%)\n🎯 هدف 2: {tp2:.2f} (25%)\n🎯 هدف 3: {tp3:.2f} (100% القاع)")
        send(f"🛑 3️⃣ وقف الخسارة\n🛑 ستوب: {sl:.2f}\n⚠️ المخاطرة: {abs(sl-entry):.2f}$")
    save_state({"last_signal": signal+f"{int(live_price)}"})
