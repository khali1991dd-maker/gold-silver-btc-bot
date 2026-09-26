import os
import requests
import datetime
import time
import json
import pandas as pd

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
FILE = "exness_prices.json"
STATE_FILE = "last_signal.json"

def send(text):
    if not TOKEN or not CHAT:
        print("BOT_TOKEN or CHAT_ID environment variables are missing.")
        return
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
        time.sleep(1)
    except Exception as e:
        print(f"Telegram send error: {e}")

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
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
            p = float(r.get('price', 0))
            if 1500 < p < 6000: return p
        except Exception: 
            time.sleep(1)
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
    except Exception: 
        return None

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception: pass
    return {"last_signal": "", "time": ""}

def save_state(s):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except Exception: pass

now = get_time()
w = now.strftime("%d-%m-%Y %I:%M %p")

# إذا كان السوق مغلقاً لا يتم إرسال شيء
if not is_open(now):
    exit()

live = get_exness()
if not live: exit()

# إدارة قراءة وحفظ بيانات الأسعار
data = []
if os.path.exists(FILE):
    try:
        with open(FILE, "r") as f:
            data = json.load(f)
    except Exception: data = []

data.append({"price": live, "time": now.isoformat()})
data = data[-1500:]

with open(FILE, "w") as f:
    json.dump(data, f)

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
    fibs = {"high": hi, "low": lo, "0": hi, "25": hi - diff * 0.25, "50": hi - diff * 0.50, "75": hi - diff * 0.75, "100": lo}
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
else:
    fibs = {"high": live + 5, "low": live - 5, "0": live + 5, "25": live + 2.5, "50": live, "75": live - 2.5, "100": live - 5}
    bull = bear = None; fib_txt = f"يجمع {len(data)}/15"; ob_txt = "يجمع"

# --- تحديد الترند ---
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

# استبعاد التداول عند القمم والقيعان
not_at_peaks = (live > fibs["low"] + 1.5) and (live < fibs["high"] - 1.5)

# --- شروط الإشارات ---
signal = "WAIT"

if strong_up and rsi <= 30 and not_at_peaks:
    signal = "BUY_STRONG"
elif strong_down and rsi >= 70 and not_at_peaks:
    signal = "SELL_STRONG"

# --- إرسال الرسائل الثلاث فقط عند وجود صفقة حقيقية ---
state = load_state()
last_sig_key = f"{signal}_{int(live/2)}"

if signal in ["BUY_STRONG", "SELL_STRONG"] and state.get("last_signal") != last_sig_key:
    if signal == "BUY_STRONG":
        entry = live
        sl = fibs["low"] - 2
        tp1 = fibs["50"]
        tp2 = fibs["25"]
        tp3 = fibs["high"]
        
        # الرسالة 1: تفاصيل الدخول
        send(f"🚨 1️⃣ دخول شراء إكسنس\n⏰ {w}\n🥇 دخول: {entry:.2f}\n📊 RSI: {rsi:.1f}\n📈 الترند: {trend_txt}\n📐 فيبو: {fib_txt}\n🧱 {ob_txt}\n💰 مخاطرة: {abs(entry-sl):.2f}$")
        # الرسالة 2: الأهداف
        send(f"🎯 2️⃣ أهداف الشراء\n🎯 1: {tp1:.2f} (50% فيبو)\n🎯 2: {tp2:.2f} (25% فيبو)\n🎯 3: {tp3:.2f} (0% قمة)")
        # الرسالة 3: الستوب
        send(f"🛑 3️⃣ ستوب الشراء\n🛑 {sl:.2f}\n📍 تحت القاع ب 2$")
        
    else:
        entry = live
        sl = fibs["high"] + 2
        tp1 = fibs["50"]
        tp2 = fibs["75"]
        tp3 = fibs["low"]
        
        # الرسالة 1: تفاصيل الدخول
        send(f"🚨 1️⃣ دخول بيع إكسنس\n⏰ {w}\n🥇 دخول: {entry:.2f}\n📊 RSI: {rsi:.1f}\n📈 الترند: {trend_txt}\n📐 فيبو: {fib_txt}\n🧱 {ob_txt}\n💰 مخاطرة: {abs(sl-entry):.2f}$")
        # الرسالة 2: الأهداف
        send(f"🎯 2️⃣ أهداف البيع\n🎯 1: {tp1:.2f} (50% فيبو)\n🎯 2: {tp2:.2f} (75% فيبو)\n🎯 3: {tp3:.2f} (100% قاع)")
        # الرسالة 3: الستوب
        send(f"🛑 3️⃣ ستوب البيع\n🛑 {sl:.2f}\n📍 فوق القمة ب 2$")
        
    save_state({"last_signal": last_sig_key, "time": now.isoformat()})
