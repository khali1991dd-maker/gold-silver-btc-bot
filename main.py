import requests, pytz, json, os
from datetime import datetime
import yfinance as yf
import pandas as pd

MUSCAT = pytz.timezone('Asia/Muscat')
PHONE = "96897134774"
APIKEY = "4515814"
STATE_FILE = "last_state.json"

def send_whatsapp(text):
    for i in range(0, len(text), 2800):
        chunk = text[i:i+2800]
        try:
            url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={requests.utils.quote(chunk)}&apikey={APIKEY}"
            requests.get(url, timeout=20)
        except: pass
    print(text)

def is_gold_closed():
    now = datetime.now(MUSCAT)
    wd = now.weekday()
    if wd == 4 and now.hour >= 22: return True
    if wd == 5: return True
    if wd == 6: return True
    if wd == 0 and now.hour < 22: return True
    return False

def get_news_alert():
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        data = r.json()
        now = datetime.now(MUSCAT)
        for ev in data:
            if ev.get('impact') == 'High' and 'USD' in ev.get('currency',''):
                t = datetime.fromtimestamp(int(ev['timestamp']))
                t = pytz.utc.localize(t).astimezone(MUSCAT)
                diff = (t - now).total_seconds() / 3600
                if 0.9 < diff < 1.1:
                    return f"⚠️ تنبيه خبر قوي بعد ساعة: {ev['title']} {t.strftime('%I:%M %p')}"
    except: pass
    return None

def get_df(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="5m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df if len(df) >= 210 else None
    except: return None

def analyze_candle(o,h,l,c):
    o0=float(o.iloc[-1]); h0=float(h.iloc[-1]); l0=float(l.iloc[-1]); c0=float(c.iloc[-1])
    o1=float(o.iloc[-2]); c1=float(c.iloc[-2])
    body = abs(c0-o0); upper = h0-max(o0,c0); lower = min(o0,c0)-l0
    if c0>o0 and c1<o1 and c0>o1 and o0<c1: return "ابتلاع شرائي قوي"
    if c0<o0 and c1>o1 and c0<o1 and o0>c1: return "ابتلاع بيعي قوي"
    if body < (h0-l0)*0.1: return "دوجي - تردد"
    if lower > body*2 and upper < body*0.5: return "همر شرائي قوي"
    if upper > body*2 and lower < body*0.5: return "شهاب بيعي قوي"
    if c0>o0: return "شمعة شرائية"
    if c0<o0: return "شمعة بيعية"
    return "عادية"

def analyze(df):
    c=df['Close']; h=df['High']; l=df['Low']; o=df['Open']
    ma = {p: float(c.rolling(p).mean().iloc[-1]) for p in [10,20,30,50,70,100,200]}
    d=c.diff(); g=d.where(d>0,0).rolling(14).mean(); lo=-d.where(d<0,0).rolling(14).mean()
    rsi = float((100-(100/(1+g/lo))).iloc[-1])
    e12=c.ewm(span=12).mean(); e26=c.ewm(span=26).mean(); macd=e12-e26; sig=macd.ewm(span=9).mean()
    mv=float(macd.iloc[-1]); sv=float(sig.iloc[-1]); hist=mv-sv
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.rolling(14).mean().iloc[-1])
    hh=float(h.tail(50).max()); ll=float(l.tail(50).min()); diff=hh-ll
    fib_levels = {"23%":hh-diff*0.236,"38%":hh-diff*0.382,"50%":hh-diff*0.5,"61%":hh-diff*0.618}
    pr=float(c.iloc[-1]); near=min(fib_levels.items(),key=lambda x:abs(x[1]-pr))
    body = abs(float(c.iloc[-1])-float(o.iloc[-1]))
    ob = "بلوك شرائي قوي" if float(c.iloc[-1])>float(o.iloc[-1]) and body>atr*0.8 else "بلوك بيعي قوي" if float(c.iloc[-1])<float(o.iloc[-1]) and body>atr*0.8 else "بلوك شرائي" if float(c.iloc[-1])>float(o.iloc[-1]) else "بلوك بيعي"
    if ma[10]>ma[20]>ma[30]>ma[50]: trend="صاعد قوي 📈📈"
    elif ma[10]>ma[20]>ma[30]: trend="صاعد 📈"
    elif ma[10]<ma[20]<ma[30]<ma[50]: trend="هابط قوي 📉📉"
    elif ma[10]<ma[20]<ma[30]: trend="هابط 📉"
    else: trend="عرضي"
    candle = analyze_candle(o,h,l,c)

    # القرار مع فلتر RSI + الشمعة
    buy_score = (ma[10]>ma[20]) + (ma[20]>ma[30]) + (mv>sv) + (hist>0) + (rsi>50)
    sell_score = (ma[10]<ma[20]) + (ma[20]<ma[30]) + (mv<sv) + (hist<0) + (rsi<50)

    is_bull_candle = "شرائي" in candle
    is_bear_candle = "بيعي" in candle

    final = "WAIT"
    reason = ""
    if buy_score >=3:
        if rsi > 75:
            final="WAIT"; reason=f"RSI عالي {rsi:.0f} فوق 75 - ممنوع الشراء"
        elif not is_bull_candle:
            final="WAIT"; reason=f"الشمعة {candle} لا توافق الشراء"
        else:
            final="BUY"
    elif sell_score >=3:
        if rsi < 25:
            final="WAIT"; reason=f"RSI منخفض {rsi:.0f} تحت 25 - ممنوع البيع"
        elif not is_bear_candle:
            final="WAIT"; reason=f"الشمعة {candle} لا توافق البيع"
        else:
            final="SELL"

    return {"p":pr,"ma":ma,"rsi":rsi,"macd":mv,"sig":sv,"atr":atr,"fib":near,"ob":ob,"candle":candle,"trend":trend,"final":final,"reason":reason,"buy":buy_score,"sell":sell_score}

def load_state():
    if os.path.exists(STATE_FILE):
        try: return json.loads(open(STATE_FILE).read())
        except: return {}
    return {}
def save_state(s): open(STATE_FILE,'w').write(json.dumps(s))

NOW = datetime.now(MUSCAT)
TIME_FULL = NOW.strftime("%A %Y-%m-%d %I:%M:%S %p توقيت عمان")
GOLD_CLOSED = is_gold_closed()

send_whatsapp(f"✅ تم تفعيل البوت {TIME_FULL}\nالذهب: {'مغلق حتى الاثنين 10م' if GOLD_CLOSED else 'مفتوح'} | الفضة: {'مغلقة' if GOLD_CLOSED else 'مفتوحة'} | بيتكوين: مفتوح\nفلتر جديد: لا بيع تحت RSI 25 ولا شراء فوق 75 + الشمعة توافق")

news = get_news_alert()
if news: send_whatsapp(news)

state = load_state()
report = f"📊 تقرير {TIME_FULL} - فريم 5د\n"
signals = []

for sym,name in [("GC=F","ذهب"),("SI=F","فضة"),("BTC-USD","بيتكوين")]:
    if name in ["ذهب","فضة"] and GOLD_CLOSED:
        df=get_df(sym)
        if df is not None:
            a=analyze(df)
            report+=f"{name}:{a['p']:.2f} مغلق {a['trend']} RSI:{a['rsi']:.0f} =>{a['final']}\n"
        continue
    df=get_df(sym)
    if df is None: continue
    a=analyze(df)
    report+=f"{name}:{a['p']:.2f} {a['trend']} RSI:{a['rsi']:.0f} =>{a['final']} {a['reason']}\n"
    if a['final']!="WAIT":
        signals.append((name,a))
        key=f"{name}_final"
        if state.get(key) and state.get(key)!=a['final']:
            send_whatsapp(f"🔄 صار تغيير {name} {TIME_FULL}\nمن {state.get(key)} الى {a['final']}\nالسعر:{a['p']:.2f} ترند:{a['trend']}")

for name,a in signals: state[f"{name}_final"]=a['final']
save_state(state)

if NOW.minute < 5:
    send_whatsapp(report)

for name,a in signals:
    is_buy = a['final']=="BUY"
    sl = a['p']-a['atr']*2.2 if is_buy else a['p']+a['atr']*2.2
    tp1 = a['p']+a['atr']*1.1 if is_buy else a['p']-a['atr']*1.1
    tp2 = a['p']+a['atr']*2.2 if is_buy else a['p']-a['atr']*2.2
    tp3 = a['p']+a['atr']*3.5 if is_buy else a['p']-a['atr']*3.5
    msg = f"""🚨 ادخل الصفقة الان 🚨
*________________________*
⏰ {TIME_FULL}
💰 {name} - {a['final']}
💵 السعر الحالي:{a['p']:.2f}
📈 نوع الترند:{a['trend']}
{'🟢 شراء' if is_buy else '🔴 بيع'}: {a['final']}
🎯 الدخول:{a['p']:.2f}
هدف1:{tp1:.2f}
هدف2:{tp2:.2f}
هدف3:{tp3:.2f}
⛔ وقف:{sl:.2f}
📊 RSI:{a['rsi']:.0f} | MACD:{a['macd']:.2f}
📐 فيبو:{a['fib'][0]} عند {a['fib'][1]:.2f}
🧱 {a['ob']}
🕯️ {a['candle']}
📏 ATR:{a['atr']:.2f}
MA10:{a['ma'][10]:.2f} MA20:{a['ma'][20]:.2f} MA200:{a['ma'][200]:.2f}
*________________________*"""
    send_whatsapp(msg)

if not signals and NOW.minute <5:
    send_whatsapp(f"⏳ لا توجد صفقات موثوقة الان {TIME_FULL}\nالسبب: فلتر RSI 25/75 + توافق الشمعة")
