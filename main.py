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
        try:
            r=requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=10).json()
            p=float(r['items'][0]['xauPrice'])
            if 4200 < p < 4500: return p
        except: time.sleep(1)
    return None

def calc_m1():
    try:
        data=json.load(open(FILE))
        if len(data) < 215: return None
        prices=pd.Series([x["price"] for x in data])
        ma20=prices.ewm(span=20, adjust=False).mean().iloc[-1] # ش0=MA20
        ma50=prices.ewm(span=50, adjust=False).mean().iloc[-1] # ش0=MA50
        ma100=prices.ewm(span=100, adjust=False).mean().iloc[-1] # ش0=MA100
        ma200_14=prices.ewm(span=200, adjust=False).mean().shift(14).iloc[-1] # ش14=MA200
        rsi=rsi_func(prices,14).iloc[-1]
        return ma20,ma50,ma100,ma200_14,rsi,prices
    except: return None

def calc_fibo_orderblock(prices):
    try:
        if len(prices) < 100: return None
        # بناء شموع 15 دقيقة من اسعار اكسنس الحقيقية
        candles=[]
        for i in range(0, len(prices), 15):
            chunk=prices[i:i+15]
            if len(chunk)>=5:
                candles.append({"Open":chunk[0],"High":max(chunk),"Low":min(chunk),"Close":chunk[-1]})
        df=pd.DataFrame(candles)
        if len(df)<20: return None

        high=df["High"].tail(50).max()
        low=df["Low"].tail(50).min()
        diff=high-low
        fib_0=high
        fib_25=high-diff*0.25
        fib_50=high-diff*0.5
        fib_100=low

        bullish_ob=None; bearish_ob=None
        for i in range(len(df)-5, 5, -1):
            if df["Close"].iloc[i] < df["Open"].iloc[i] and df["Close"].iloc[i+1] > df["Open"].iloc[i+1]:
                bullish_ob=(float(df["Low"].iloc[i]), float(df["High"].iloc[i])); break
        for i in range(len(df)-5, 5, -1):
            if df["Close"].iloc[i] > df["Open"].iloc[i] and df["Close"].iloc[i+1] < df["Open"].iloc[i+1]:
                bearish_ob=(float(df["Low"].iloc[i]), float(df["High"].iloc[i])); break
        return {"high":high,"low":low,"fib_0":fib_0,"fib_25":fib_25,"fib_50":fib_50,"fib_100":fib_100,"bull_ob":bullish_ob,"bear_ob":bearish_ob,"df":df}
    except: return None

now=get_time()
w_time=now.strftime("%d-%m-%Y %I:%M %p")
if not is_open(now):
    send(f"⏰ {w_time} - M1\n🥇 السوق مغلق"); exit()

price=get_exness_price()
if price is None: exit()

# حفظ السعر
try:
    if os.path.exists(FILE): data=json.load(open(FILE))
    else: data=[]
    data.append({"price":price})
    data=data[-1500:] # نحتفظ ب 1500 شمعة
    json.dump(data, open(FILE,"w"))
except: pass

calc = calc_m1()
if calc is None:
    send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 الذهب: {price:.2f}\n⏳ جاري تجميع الشموع {len(data) if 'data' in locals() else 0}/215\n(يحتاج 3 ساعات ونص ليطابق الميتا 100%)")
    exit()

ma20,ma50,ma100,ma200_14,rsi,prices = calc
fibo = calc_fibo_orderblock(prices.tolist())

if fibo:
    fib_txt=f"📐 فيبو 15دق [0-0.25-0.5-1]:\n0%={fibo['fib_0']:.1f} | 25%={fibo['fib_25']:.1f}\n50%={fibo['fib_50']:.1f} | 100%={fibo['fib_100']:.1f}"
    ob_txt=""
    if fibo['bull_ob']: ob_txt+=f"🟩 بلوك شرائي: {fibo['bull_ob'][0]:.1f}-{fibo['bull_ob'][1]:.1f}\n"
    else: ob_txt+="🟩 بلوك شرائي: لا يوجد\n"
    if fibo['bear_ob']: ob_txt+=f"🟥 بلوك بيعي: {fibo['bear_ob'][0]:.1f}-{fibo['bear_ob'][1]:.1f}"
    else: ob_txt+="🟥 بلوك بيعي: لا يوجد"
else:
    fib_txt="📐 فيبو 15دق: جاري التجميع"; ob_txt=""

up_filter=price>ma200_14; down_filter=price<ma200_14
up_order=ma20>ma50 and ma50>ma100
down_order=ma20<ma50 and ma50<ma100

near_50 = fibo and abs(price - fibo['fib_50']) < 5 if fibo else False
near_25 = fibo and abs(price - fibo['fib_25']) < 5 if fibo else False
near_bull_ob = fibo and fibo['bull_ob'] and fibo['bull_ob'][0]-4 <= price <= fibo['bull_ob'][1]+4 if fibo else False
near_bear_ob = fibo and fibo['bear_ob'] and fibo['bear_ob'][0]-4 <= price <= fibo['bear_ob'][1]+4 if fibo else False

signal=None; reason=""
if rsi <= 30 and up_filter and up_order:
    signal="شراء"; reason=f"RSI={rsi:.1f} <=30 + فوق MA200 ش14={ma200_14:.1f} + 20>50>100"
    if near_50 or near_25 or near_bull_ob: reason+=" 🔥 ذهبية"
elif rsi <= 30 and up_filter and (near_50 or near_25 or near_bull_ob):
    signal="شراء"; reason=f"RSI={rsi:.1f} <=30 + فوق MA200 ش14 + منطقة ذهبية"
elif rsi >= 70 and down_filter and down_order:
    signal="بيع"; reason=f"RSI={rsi:.1f} >=70 + تحت MA200 ش14={ma200_14:.1f} + 20<50<100"
    if near_50 or near_25 or near_bear_ob: reason+=" 🔥 ذهبية"
elif rsi >= 70 and down_filter and (near_50 or near_25 or near_bear_ob):
    signal="بيع"; reason=f"RSI={rsi:.1f} >=70 + تحت MA200 ش14 + منطقة ذهبية"

if signal:
    tp1=price+3 if signal=="شراء" else price-3
    tp2=price+6 if signal=="شراء" else price-6
    sl=price-4 if signal=="شراء" else price+4
    msg=(f"⚡️ اشارة {signal} - M1 إكسنس\n⏰ {w_time}\n🥇 الذهب: {price:.2f} [إكسنس ✅]\n📦 {reason}\n"
         f"📈 ش0: 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f}\n"
         f"📈 ش14: 200={ma200_14:.2f} - {'فوق' if up_filter else 'تحت'}\n"
         f"📊 RSI14: {rsi:.2f} [30/70]\n{fib_txt}\n{ob_txt}\n\n"
         f"💵 دخول: {price:.2f}\n🎯1: {tp1:.2f} 🎯2: {tp2:.2f} 🛑: {sl:.2f}")
    for _ in range(3): send(msg); time.sleep(1)
else:
    send(f"⏰ {w_time} - M1 إكسنس ✅\n🥇 الذهب: {price:.2f}\n"
         f"📈 ش0: 20={ma20:.2f} | 50={ma50:.2f} | 100={ma100:.2f}\n"
         f"📈 ش14: 200={ma200_14:.2f} - {'فوق' if up_filter else 'تحت'}\n"
         f"📊 RSI14: {rsi:.2f} [30/70]\n{fib_txt}\n{ob_txt}\n🚫 لا توجد اشارة")
