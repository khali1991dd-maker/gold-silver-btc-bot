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

def get_m1_data():
    try:
        url="https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=1m&limit=250"
        r=requests.get(url, timeout=15).json()
        if isinstance(r, list) and len(r)>50:
            df=pd.DataFrame(r, columns=['o_t','o','h','l','c','v','c_t','q','n','tb','tq','i'])
            for k in ['h','l','o','c']: df[k]=df[k].astype(float)
            return df
    except: pass
    try:
        url="https://api.bybit.com/v5/market/kline?category=spot&symbol=PAXGUSDT&interval=1&limit=200"
        r=requests.get(url, timeout=15).json()
        data=r.get('result',{}).get('list',[])
        if len(data)>50:
            data.reverse()
            df=pd.DataFrame(data, columns=['start','o','h','l','c','v','turn'])
            for k in ['h','l','o','c']: df[k]=df[k].astype(float)
            return df
    except: pass
    return None

def get_15m_data():
    try:
        url="https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=15m&limit=100"
        r=requests.get(url, timeout=15).json()
        if isinstance(r, list) and len(r)>10:
            df=pd.DataFrame(r, columns=['o_t','o','h','l','c','v','c_t','q','n','tb','tq','i'])
            for k in ['h','l','o','c']: df[k]=df[k].astype(float)
            return df
    except: pass
    try:
        url="https://api.bybit.com/v5/market/kline?category=spot&symbol=PAXGUSDT&interval=15&limit=100"
        r=requests.get(url, timeout=15).json()
        data=r.get('result',{}).get('list',[])
        if len(data)>10:
            data.reverse()
            df=pd.DataFrame(data, columns=['start','o','h','l','c','v','turn'])
            for k in ['h','l','o','c']: df[k]=df[k].astype(float)
            return df
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

try: data=json.load(open(FILE))
except: data=[]
data.append({"price":live_price})
data=data[-1500:]
json.dump(data, open(FILE,"w"))

df_m1=get_m1_data()
df_15=get_15m_data()

# فولباك اذا M1 فشل
if df_m1 is None or len(df_m1)<50:
    try:
        if len(data)>=60:
            prices=pd.Series([x["price"] for x in data])
            df_m1=pd.DataFrame({"c":prices,"h":prices,"l":prices,"o":prices})
        else:
            send(f"⏰ {w_time}\n🥇 لايف إكسنس: {live_price:.2f}\n⏳ يجمع M1 {len(data)}/60"); exit()
    except:
        send(f"⏰ {w_time}\n🥇 لايف إكسنس: {live_price:.2f}\n⏳ M1 غير جاهز"); exit()

if df_15 is None:
    if len(data)>=30:
        prices=[x["price"] for x in data]
        rows=[]
        for i in range(0, len(prices), 15):
            chunk=prices[i:i+15]
            if len(chunk)>=3:
                rows.append({"o":chunk[0],"h":max(chunk),"l":min(chunk),"c":chunk[-1]})
        df_15=pd.DataFrame(rows)
        if len(df_15)<5:
            send(f"⏰ {w_time}\n🥇 لايف: {live_price:.2f}\n⏳ 15د غير جاهز"); exit()
    else:
        send(f"⏰ {w_time}\n🥇 لايف: {live_price:.2f}\n⏳ 15د غير جاهز"); exit()

closes=df_m1['c']
ma20=closes.ewm(span=20, adjust=False).mean().iloc[-1]
ma50=closes.ewm(span=50, adjust=False).mean().iloc[-1]
ma100=closes.ewm(span=100, adjust=False).mean().iloc[-1]
ma200=closes.ewm(span=200, adjust=False).mean().iloc[-1]
ma200_14=closes.ewm(span=200, adjust=False).mean().shift(14).iloc[-1] if len(closes)>214 else ma200
rsi=rsi_func(closes,14).iloc[-1]
ma20_prev=closes.ewm(span=20, adjust=False).mean().iloc[-6] if len(closes)>6 else ma20

fibs,bull_ob,bear_ob=calc_fib_and_ob(df_15)

buy_order = ma20>ma50>ma100
sell_order = ma20<ma50<ma100
ma20_down = ma20 < ma20_prev
ma20_up = ma20 > ma20_prev
below_all = live_price < ma20 and live_price < ma50
above_all = live_price > ma20 and live_price > ma50
strong_down = sell_order and ma20_down and below_all and live_price < ma200_14
strong_up = buy_order and ma20_up and above_all and live_price > ma200_14

near_fib25 = abs(live_price-fibs["25"])<4
near_fib50 = abs(live_price-fibs["50"])<4
in_bull_ob = bull_ob and bull_ob[0] <= live_price <= bull_ob[1]
in_bear_ob = bear_ob and bear_ob[0] <= live_price <= bear_ob[1]
golden_zone = near_fib25 or near_fib50 or in_bull_ob or in_bear_ob

if strong_down:
    if rsi >= 55 and golden_zone:
        signal="SELL_STRONG"; txt="🔴🔴 بيع M1 مع ترند هابط + 15د 🔥"
    elif rsi >= 45:
        signal="SELL"; txt="🔴 بيع M1 - ترند هابط"
    else:
        signal="WAIT"; txt="⚪ انتظار - هبوط M1 قوي"
elif strong_up:
    if rsi <= 45 and golden_zone:
        signal="BUY_STRONG"; txt="🟢🟢 شراء M1 مع ترند صاعد + 15د 🔥"
    elif rsi <= 55:
        signal="BUY"; txt="🟢 شراء M1 - ترند صاعد"
    else:
        signal="WAIT"; txt="⚪ انتظار - صعود M1 قوي"
else:
    if rsi <= 20 and golden_zone and not sell_order:
        signal="BUY_STRONG"; txt="🟢🟢 شراء M1 قوي + 15د ذهبية 🔥"
    elif rsi >= 80 and golden_zone and not buy_order:
        signal="SELL_STRONG"; txt="🔴🔴 بيع M1 قوي + 15د ذهبية 🔥"
    elif rsi <= 30 and buy_order:
        signal="BUY"; txt="🟢 شراء M1"
    elif rsi >= 70 and sell_order:
        signal="SELL"; txt="🔴 بيع M1"
    else:
        signal="WAIT"; txt="⚪ انتظار M1"

state=load_state()
fib_txt=f"0%={fibs['high']:.1f} | 25%={fibs['25']:.1f} | 50%={fibs['50']:.1f} | 100%={fibs['low']:.1f}"
trend_txt="🔴 هبوط M1 قوي" if strong_down else "🟢 صعود M1 قوي" if strong_up else "↔️ جانبي"

msg=f"""⏰ {w_time} - M1 دخول ✅ 15د تأكيد ✅
🥇 لايف إكسنس: {live_price:.2f}
📈 M1: 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f} | 200={ma200_14:.2f}
📊 RSI M1: {rsi:.2f} | {trend_txt}
📐 فيبو 15د: {fib_txt}
🎯 {txt}
"""
send(msg)

if signal in ["BUY_STRONG","SELL_STRONG"] and state.get("last_signal")!= signal+f"{int(live_price)}":
    if "BUY" in signal:
        entry=live_price; sl=fibs["low"]-3.0; tp1=fibs["50"]; tp2=fibs["25"]; tp3=fibs["high"]
        send(f"🚨 1️⃣ دخول شراء M1\n⏰ {w_time}\n🥇 دخول: {entry:.2f} | RSI M1: {rsi:.1f}\n📍 تأكيد 15د: {fib_txt}\n🔥 {trend_txt}")
        send(f"🎯 2️⃣ أهداف 15د\n🎯 1: {tp1:.2f} (50%)\n🎯 2: {tp2:.2f} (25%)\n🎯 3: {tp3:.2f} (0%)")
        send(f"🛑 3️⃣ ستوب 15د\n🛑 {sl:.2f} | مخاطرة {abs(entry-sl):.2f}$")
    else:
        entry=live_price; sl=fibs["high"]+3.0; tp1=fibs["50"]; tp2=fibs["25"]; tp3=fibs["low"]
        send(f"🚨 1️⃣ دخول بيع M1\n⏰ {w_time}\n🥇 دخول: {entry:.2f} | RSI M1: {rsi:.1f}\n📍 تأكيد 15د: {fib_txt}\n🔥 {trend_txt}")
        send(f"🎯 2️⃣ أهداف 15د\n🎯 1: {tp1:.2f} (50%)\n🎯 2: {tp2:.2f} (25%)\n🎯 3: {tp3:.2f} (100%)")
        send(f"🛑 3️⃣ ستوب 15د\n🛑 {sl:.2f} | مخاطرة {abs(sl-entry):.2f}$")
    save_state({"last_signal": signal+f"{int(live_price)}"})
