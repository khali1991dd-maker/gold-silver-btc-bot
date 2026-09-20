import requests, pytz, json, os
from datetime import datetime
import yfinance as yf
import pandas as pd

# ====== الاعدادات ======
MUSCAT = pytz.timezone('Asia/Muscat')
PHONE = "96897134774" # رقمك
APIKEY = "4515814"
TELEGRAM_TOKEN = "8790670622:AAEOebGJBY4Gu9rGXU-1TwAPZXb6lws19Lg"
TELEGRAM_CHAT = "8581872878"
STATE_FILE = "last_state.json"

def send_all(text):
    # تصليح مشكلة التكرار والرموز - نستخدم params بدون quote مرتين
    for i in range(0, len(text), 3500):
        chunk = text[i:i+3500]
        try:
            requests.get("https://api.callmebot.com/whatsapp.php",
                         params={"phone": PHONE, "text": chunk, "apikey": APIKEY}, timeout=20)
        except: pass
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                         params={"chat_id": TELEGRAM_CHAT, "text": chunk}, timeout=20)
        except: pass
    print(text)

def is_gold_closed():
    now = datetime.now(MUSCAT)
    wd = now.weekday() # الاثنين 0... الجمعة 4... الاحد 6
    # الذهب يغلق الجمعة 11 مساء ويفتح الاثنين 1 صباحا بتوقيت عمان
    if wd == 4 and now.hour >= 23: return True
    if wd == 5: return True
    if wd == 6: return True
    if wd == 0 and now.hour < 1: return True
    return False

def get_news_alert():
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        data = r.json()
        now = datetime.now(MUSCAT)
        for ev in data:
            if ev.get('impact')=='High' and 'USD' in ev.get('currency',''):
                t = pytz.utc.localize(datetime.fromtimestamp(int(ev['timestamp']))).astimezone(MUSCAT)
                diff = (t - now).total_seconds()/3600
                if 0.9 < diff < 1.1: # قبل الخبر بساعة
                    return f"⚠️ تنبيه خبر قوي بعد ساعة\n{ev['title']}\nالوقت: {t.strftime('%A %I:%M %p')} بتوقيت عمان"
    except: pass
    return None

def get_df(sym):
    try:
        df = yf.download(sym, period="5d", interval="5m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df if len(df) >= 210 else None
    except: return None

def analyze_candle(o,h,l,c):
    o0=float(o.iloc[-1]); c0=float(c.iloc[-1]); h0=float(h.iloc[-1]); l0=float(l.iloc[-1])
    o1=float(o.iloc[-2]); c1=float(c.iloc[-2])
    body=abs(c0-o0); rng=h0-l0
    if c0>o0 and c1<o1 and c0>o1 and o0<c1: return "ابتلاع شرائي قوي"
    if c0<o0 and c1>o1 and c0<o1 and o0>c1: return "ابتلاع بيعي قوي"
    if rng>0 and body < rng*0.1: return "دوجي"
    if (min(o0,c0)-l0) > body*2: return "همر شرائي قوي"
    if (h0-max(o0,c0)) > body*2: return "شهاب بيعي قوي"
    return "شمعة شرائية قوية" if c0>o0 and body>rng*0.6 else "شمعة بيعية قوية" if c0<o0 and body>rng*0.6 else "شمعة شرائية" if c0>o0 else "شمعة بيعية"

def analyze(df):
    c=df['Close']; h=df['High']; l=df['Low']; o=df['Open']
    # موفنجات 10/20/30/50/70/100/200
    ma={p:float(c.rolling(p).mean().iloc[-1]) for p in [10,20,30,50,70,100,200]}
    # RSI
    d=c.diff(); g=d.where(d>0,0).rolling(14).mean(); lo=-d.where(d<0,0).rolling(14).mean()
    rsi=float((100-(100/(1+g/lo))).iloc[-1])
    # MACD
    e12=c.ewm(span=12).mean(); e26=c.ewm(span=26).mean(); macd=e12-e26; sig=macd.ewm(span=9).mean()
    mv=float(macd.iloc[-1]); sv=float(sig.iloc[-1])
    # Moving True Average ATR
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.rolling(14).mean().iloc[-1])
    # فيبوناتشي
    hh=float(h.tail(50).max()); ll=float(l.tail(50).min()); pr=float(c.iloc[-1])
    fib=min([("23%",hh-(hh-ll)*0.236),("38%",hh-(hh-ll)*0.382),("50%",hh-(hh-ll)*0.5),("61%",hh-(hh-ll)*0.618),("78%",hh-(hh-ll)*0.786)], key=lambda x:abs(x[1]-pr))
    # ترند من الموفنجات
    if ma[10]>ma[20]>ma[30]>ma[50]>ma[70]: trend="صاعد قوي جدا"
    elif ma[10]>ma[20]>ma[30]>ma[50]: trend="صاعد قوي"
    elif ma[10]>ma[20]>ma[30]: trend="صاعد"
    elif ma[10]<ma[20]<ma[30]<ma[50]<ma[70]: trend="هابط قوي جدا"
    elif ma[10]<ma[20]<ma[30]<ma[50]: trend="هابط قوي"
    elif ma[10]<ma[20]<ma[30]: trend="هابط"
    else: trend="عرضي"
    candle=analyze_candle(o,h,l,c)
    # بلوك اوردر
    ob="بلوك شرائي" if float(c.iloc[-1])>float(o.iloc[-1]) and (c.iloc[-1]-l.iloc[-1])> (h.iloc[-1]-l.iloc[-1])*0.6 else "بلوك بيعي" if float(c.iloc[-1])<float(o.iloc[-1]) and (h.iloc[-1]-c.iloc[-1])> (h.iloc[-1]-l.iloc[-1])*0.6 else "بدون بلوك واضح"

    buy_score=(ma[10]>ma[20])+(ma[20]>ma[30])+(ma[30]>ma[50])+(mv>sv)+(rsi>50)
    sell_score=(ma[10]<ma[20])+(ma[20]<ma[30])+(ma[30]<ma[50])+(mv<sv)+(rsi<50)

    final="WAIT"
    if buy_score>=3:
        if rsi>75: final="WAIT" # شرطك: ما يشتري اذا فوق 75
        elif "بيعي" in candle or "شهاب" in candle: final="WAIT" # شمعة لا توافق الترند
        else: final="BUY"
    elif sell_score>=3:
        if rsi<25: final="WAIT" # شرطك: ما يبيع اذا تحت 25
        elif "شرائي" in candle or "همر" in candle: final="WAIT"
        else: final="SELL"

    return {"p":pr,"ma":ma,"rsi":rsi,"macd":mv,"sig":sv,"atr":atr,"fib":fib,"candle":candle,"trend":trend,"final":final,"ob":ob}

def load_state(): return json.loads(open(STATE_FILE).read()) if os.path.exists(STATE_FILE) else {}
def save_state(s): open(STATE_FILE,'w').write(json.dumps(s))

NOW=datetime.now(MUSCAT)
TIME_FULL=NOW.strftime("%A %Y-%m-%d %I:%M:%S %p توقيت عمان")
GOLD_CLOSED=is_gold_closed()
state=load_state()

# 1- رسالة تفعيل فورية اول ما يشتغل
if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or NOW.minute % 5 == 0:
    if state.get("last_activation_hour")!= NOW.hour or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        send_all(f"✅ البوت مفعل {TIME_FULL}\nفريم 5 دقايق\nالذهب/الفضة: {'مغلق الجمعة 11م - الاثنين 1ص' if GOLD_CLOSED else 'مفتوح'}\nالبيتكوين: مفتوح 24س\nواتس+تليجرام شغال")
        state["last_activation_hour"]=NOW.hour
        save_state(state)

# 2- تنبيه اخبار
n=get_news_alert()
if n: send_all(n)

# 3- تحليل وتقرير
report=f"📊 تقرير السوق {TIME_FULL}\nفريم 5د\n"; signals=[]
for sym,name in [("GC=F","ذهب"),("SI=F","فضة"),("BTC-USD","بيتكوين")]:
    if name in ["ذهب","فضة"] and GOLD_CLOSED:
        report+=f"🔒 {name}: مغلق حتى الاثنين 1ص\n"; continue
    df=get_df(sym)
    if df is None: continue
    a=analyze(df)
    report+=f"{name}:{a['p']:.2f} | {a['trend']} | RSI:{a['rsi']:.0f} | {a['candle']} => {a['final']}\nMA:{a['ma'][10]:.1f}/{a['ma'][20]:.1f}/{a['ma'][50]:.1f}\n"
    if a['final']!="WAIT":
        signals.append((name,a))
        # تنبيه تغيير
        if state.get(f"{name}_final") and state.get(f"{name}_final")!=a['final']:
            send_all(f"🔄 تغيير اتجاه {name}\n⏰ {TIME_FULL}\nمن {state.get(f'{name}_final')} الى {a['final']}\nالسعر:{a['p']:.2f} RSI:{a['rsi']:.0f}")

for name,a in signals: state[f"{name}_final"]=a['final']

# يرسل كل ساعة مرة واحدة فقط - بدون تكرار
if NOW.minute < 5:
    send_all(report)

save_state(state)

# 4- صفقات كل 5 دقايق
for name,a in signals:
    buy=a['final']=="BUY"; atr=a['atr']; p=a['p']
    # ما نكرر نفس الصفقة بنفس الساعة
    key=f"{name}_{NOW.strftime('%Y%m%d%H')}_{a['final']}"
    if state.get(key): continue

    sl=p-atr*2.2 if buy else p+atr*2.2
    tp1=p+atr*1.1 if buy else p-atr*1.1
    tp2=p+atr*2.2 if buy else p-atr*2.2
    tp3=p+atr*3.5 if buy else p-atr*3.5

    send_all(f"🚨 ادخل الصفقة الان 🚨\n"
             f"⏰ الوقت: {TIME_FULL}\n"
             f"📈 {name} - {a['final']}\n"
             f"💰 السعر الحالي: {p:.2f}\n"
             f"📊 نوع الترند: {a['trend']}\n"
             f"{'🟢 شراء' if buy else '🔴 بيع'} الدخول: {p:.2f}\n"
             f"🎯 هدف1: {tp1:.2f}\n"
             f"🎯 هدف2: {tp2:.2f}\n"
             f"🎯 هدف3: {tp3:.2f}\n"
             f"⛔ وقف الخسارة: {sl:.2f}\n"
             f"RSI:{a['rsi']:.0f} MACD:{a['macd']:.2f}\n"
             f"فيبو:{a['fib'][0]} {a['fib'][1]:.2f} | {a['ob']}\n"
             f"الشمعة: {a['candle']}\n"
             f"MA10/20/30:{a['ma'][10]:.1f}/{a['ma'][20]:.1f}/{a['ma'][30]:.1f}")

    state[key]=True
    save_state(state)
