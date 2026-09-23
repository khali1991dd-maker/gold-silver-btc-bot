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
    if m.weekday() == 5: return False
    if m.weekday() == 4 and m.hour >= 23: return False
    if m.weekday() == 6 and m.hour < 1: return False
    return True

def rsi_func(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1/p, min_periods=p).mean()
    l = -d.clip(upper=0).ewm(alpha=1/p, min_periods=p).mean()
    rs = g / l
    return (100 - (100 / (1 + rs))).fillna(50)

def get_exness():
    for _ in range(5):
        try:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            p = float(r.get('price', 0))
            if 1500 < p < 6000: return p
        except: time.sleep(1)
    return None

def build_15m(data):
    if len(data) < 10: return None
    try:
        df = pd.DataFrame(data)
        df['dt'] = pd.to_datetime(df['time'])
        df.set_index('dt', inplace=True)
        resampled = df['price'].resample('15min').ohlc().dropna()
        if len(resampled) < 3: return None
        resampled.rename(columns={'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c'}, inplace=True)
        return resampled.reset_index()
    except Exception as e:
        return None

def load_state():
    try: return json.load(open(STATE_FILE))
    except: return {"last_signal": "", "time": ""}

def save_state(s):
    json.dump(s, open(STATE_FILE, "w"))

now = get_time()
w = now.strftime("%d-%m-%Y %I:%M %p")
if not is_open(now):
    send(f"⏰ {w} - السوق مغلق")
    exit()

live = get_exness()
if not live: exit()

try: data = json.load(open(FILE))
except: data = []
data.append({"price": live, "time": now.isoformat()})
data = data[-1500:]
json.dump(data, open(FILE, "w"))

prices = pd.Series([x["price"] for x in data])
ma20 = prices.ewm(span=min(20, len(prices)), adjust=False).mean().iloc[-1]
ma50 = prices.ewm(span=min(50, len(prices)), adjust=False).mean().iloc[-1]
ma100 = prices.ewm(span=min(100, len(prices)), adjust=False).mean().iloc[-1]
ma200 = prices.ewm(span=min(200, len(prices)), adjust=False).mean().iloc[-1]
ma200_14 = prices.ewm(span=200, adjust=False).mean().shift(14).iloc[-1] if len(prices) > 214 else ma200
ma20_prev = prices.ewm(span=20, adjust=False).mean().iloc[-6] if len(prices) > 6 else ma20
rsi = rsi_func(prices, 14).iloc[-1] if len(prices) > 14 else 50

df15 = build_15m(data)
if df15 is not None and len(df15) >= 3:
    last10 = df15.tail(10)
    hi = last10['h'].max(); lo = last10['l'].min()
    diff = max(hi - lo, 2.0)
    fibs = {"high": hi, "low": lo, "0": hi, "25": hi - diff * 0.25, "50": hi - diff * 0.50, "100": lo}
    bull = None; bear = None
    for i in range(len(df15) - 2, 0, -1):
        if df15.iloc[i]['c'] < df15.iloc[i]['o'] and df15.iloc[i+1]['c'] > df15.iloc[i+1]['o']:
            bull = (df15.iloc[i]['l'], df15.iloc[i]['h']); break
    for i in range(len(df15) - 2, 0, -1):
        if df15.iloc[i]['c'] > df15.iloc[i]['o'] and df15.iloc[i+1]['c'] < df15.iloc[i+1]['o']:
            bear = (df15.iloc[i]['l'], df15.iloc[i]['h']); break
    fib_txt = f"0%={fibs['high']:.2f} | 25%={fibs['25']:.2f} | 50%={fibs['50']:.2f} | 100%={fibs['low']:.2f}"
    ob_txt = ""
    if bull: ob_txt += f"🟩 شرائي {bull[0]:.2f}-{bull[1]:.2f} "
    if bear: ob_txt += f"🟥 بيعي {bear[0]:.2f}-{bear[1]:.2f}"
    if not ob_txt: ob_txt = "لا يوجد"
    src15 = f"{len(df15)} شمعة ✅"
else:
    fibs = {"high": live + 3, "low": live - 3, "0": live + 3, "25": live + 1.5, "50": live, "100": live - 3}
    bull = bear = None; fib_txt = f"يجمع {len(data)}/15"; ob_txt = "يجمع"; src15 = "يجمع"

# --- الترند ---
buy_order = ma20 > ma50 > ma100 if len(prices) >= 100 else ma20 > ma50
sell_order = ma20 < ma50 < ma100 if len(prices) >= 100 else ma20 < ma50
ma20_down = ma20 < ma20_prev
ma20_up = ma20 > ma20_prev
below_all = live < ma20 and live < ma50
above_all = live > ma20 and live > ma50
strong_down = sell_order and ma20_down and below_all
strong_up = buy_order and ma20_up and above_all
if len(prices) >= 200:
    strong_down = strong_down and live < ma200_14
    strong_up = strong_up and live > ma200_14

trend_txt = "🔴 ترند هابط قوي M1" if strong_down else "🟢 ترند صاعد قوي M1" if strong_up else "↔️ ترند جانبي"

near_fib25 = abs(live - fibs["25"]) < 3
near_fib50 = abs(live - fibs["50"]) < 3
in_bull = bull and bull[0] <= live <= bull[1]
in_bear = bear and bear[0] <= live <= bear[1]
golden = near_fib25 or near_fib50 or in_bull or in_bear

# --- إشارات ---
if strong_down:
    if rsi >= 55 and golden: signal = "SELL_STRONG"; sig_txt = "🔴🔴 بيع قوي M1 + 15د 🔥"
    elif rsi >= 48: signal = "SELL"; sig_txt = "🔴 بيع M1"
    else: signal = "WAIT"; sig_txt = "⚪ هبوط قوي - انتظار"
elif strong_up:
    if rsi <= 45 and golden: signal = "BUY_STRONG"; sig_txt = "🟢🟢 شراء قوي M1 + 15د 🔥"
    elif rsi <= 52: signal = "BUY"; sig_txt = "🟢 شراء M1"
    else: signal = "WAIT"; sig_txt = "⚪ صعود قوي - انتظار"
else:
    if rsi <= 30 and golden and not sell_order: signal = "BUY_STRONG"; sig_txt = "🟢🟢 شراء M1 ذهبي + 15د 🔥"
    elif rsi >= 70 and golden and not buy_order: signal = "SELL_STRONG"; sig_txt = "🔴🔴 بيع M1 ذهبي + 15د 🔥"
    elif rsi <= 35: signal = "BUY"; sig_txt = "🟢 شراء M1"
    elif rsi >= 65: signal = "SELL"; sig_txt = "🔴 بيع M1"
    else: signal = "WAIT"; sig_txt = "⚪ انتظار"

status = "إكسنس ✅ 100% مثل الميتا" if len(data) >= 60 else f"يجمع M1 {len(data)}/60"

# --- رسالة اللايف كل دقيقة ---
msg = f"""⏰ {w} - {status}
━━━━━━━━━━━━━━━
🥇 لايف M1: {live:.2f}

📈 موفنجات M1 إكسنس:
20 = {ma20:.2f}
50 = {ma50:.2f}
100 = {ma100:.2f}
200 = {ma200:.2f}

📊 RSI M1: {rsi:.2f}

📈 الترند M1: {trend_txt}
━━━━━━━━━━━━━━━
⏰ 15د إكسنس {src15}:

📐 فيبو 15د:
{fib_txt}

🧱 بلوك أوردر:
{ob_txt}
━━━━━━━━━━━━━━━
🎯 إشارة: {sig_txt}
"""
send(msg)

# --- صفقات بيع وشراء - 3 رسائل ---
state = load_state()
last_sig_key = f"{signal}_{int(live)}"

if signal in ["BUY_STRONG", "SELL_STRONG"] and state.get("last_signal") != last_sig_key:
    if "BUY" in signal:
        entry = live; sl = fibs["low"] - 3; tp1 = fibs["50"]; tp2 = fibs["25"]; tp3 = fibs["high"]
        send(f"🚨 1️⃣ دخول شراء إكسنس\n⏰ {w}\n🥇 دخول: {entry:.2f}\n📊 RSI: {rsi:.1f}\n📈 {trend_txt}\n📐 فيبو: {fib_txt}\n🧱 {ob_txt}\n💰 مخاطرة: {abs(entry-sl):.2f}$")
        send(f"🎯 2️⃣ أهداف الشراء\n🎯 1: {tp1:.2f} (50% فيبو)\n🎯 2: {tp2:.2f} (25% فيبو)\n🎯 3: {tp3:.2f} (0% قمة)")
        send(f"🛑 3️⃣ ستوب الشراء\n🛑 {sl:.2f}\n📍 تحت 100% فيبو ب 3$")
    else:
        entry = live; sl = fibs["high"] + 3; tp1 = fibs["50"]; tp2 = fibs["25"]; tp3 = fibs["low"]
        send(f"🚨 1️⃣ دخول بيع إكسنس\n⏰ {w}\n🥇 دخول: {entry:.2f}\n📊 RSI: {rsi:.1f}\n📈 {trend_txt}\n📐 فيبو: {fib_txt}\n🧱 {ob_txt}\n💰 مخاطرة: {abs(sl-entry):.2f}$")
        send(f"🎯 2️⃣ أهداف البيع\n🎯 1: {tp1:.2f} (50% فيبو)\n🎯 2: {tp2:.2f} (25% فيبو)\n🎯 3: {tp3:.2f} (100% قاع)")
        send(f"🛑 3️⃣ ستوب البيع\n🛑 {sl:.2f}\n📍 فوق 0% فيبو ب 3$")
    save_state({"last_signal": last_sig_key, "time": now.isoformat()})
