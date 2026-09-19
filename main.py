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
        try:
            url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={requests.utils.quote(text[i:i+2800])}&apikey={APIKEY}"
            requests.get(url, timeout=20)
        except: pass

def is_gold_closed():
    now = datetime.now(MUSCAT)
    wd = now.weekday()
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
                if 0.9 < (t-now).total_seconds()/3600 < 1.1:
                    return f"⚠️ تنبيه خبر بعد ساعة: {ev['title']} {t.strftime('%I:%M %p')}"
    except: pass
    return None

def get_df(sym):
    try:
        df = yf.download(sym, period="5d", interval="5m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df if len(df)>=210 else None
    except: return None

def analyze_candle(o,h,l,c):
    o0=float(o.iloc[-1]); c0=float(c.iloc[-1]); h0=float(h.iloc[-1]); l0=float(l.iloc[-1])
    o1=float(o.iloc[-2]); c1=float(c.iloc[-2])
    body=abs(c0-o0); upper=h0-max(o0,c0); lower=min(o0,c0)-l0
    if c0>o0 and c1<o1 and c0>o1 and o0<c1: return "ابتلاع شرائي قوي"
    if c0<o0 and c1>o1 and c0<o1 and o0>c1: return "ابتلاع بيعي قوي"
    if body < (h0-l0)*0.1: return "دوجي"
    if lower>body*2: return "همر شرائي قوي"
    if upper>body*2: return "شهاب بيعي قوي"
    return "شمعة شرائية" if c0>o0 else "شمعة بيعية"

def analyze(df):
    c=df['Close']; h=df['High']; l=df['Low']; o=df['Open']
    ma={p:float(c.rolling(p).mean().iloc[-1]) for p in [10,20,30,50,70,100,200]}
    d=c.diff(); g=d.where(d>0,0).rolling(14).mean(); lo=-d.where(d<0,0).rolling(14).mean()
    rsi=float((100-(100/(1+g/lo))).iloc[-1])
    e12=c.ewm(span=12).mean(); e26=c.ewm(span=26).mean(); macd=e12-e26; sig=macd.ewm(span=9).mean()
    mv=float(macd.iloc[-1]); sv=float(sig.iloc[-1])
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.rolling(14).mean().iloc[-1])
    hh=float(h.tail(50).max()); ll=float(l.tail(50).min()); pr=float(c.iloc[-1])
    fib=min([("23%",hh-(hh-ll)*0.236),("38%",hh-(hh-ll)*0.382),("50%",hh-(hh-ll)*0.5),("61%",hh-(hh-ll)*0.618)], key=lambda x:abs(x[1]-pr))
    trend="صاعد قوي 📈📈" if ma[10]>ma[20]>ma[30]>ma[50] else "صاعد 📈" if ma[10]>ma[20]>ma[30] else "هابط قوي 📉📉" if ma[10]<ma[20]<ma[30]<ma[50] else "هابط 📉" if ma[10]<ma[20] else "عرضي"
    candle=analyze_candle(o,h,l,c)
    buy=(ma[10]>ma[20])+(ma[20]>ma[30])+(mv>sv)+(rsi>50)
    sell=(ma[10]<ma[20])+(ma[20]<ma[30])+(mv<sv)+(rsi<50)
    final="WAIT"; reason=""
    if buy>=3:
        if rsi>75: reason=f"RSI {rsi:.0f}>75 ممنوع الشراء"
        elif "شرائي" not in candle: reason=f"الشمعة {candle} لا توافق شراء"
        else: final="BUY"
    elif sell>=3:
        if rsi<25: reason=f"RSI {rsi:.0f}<25 ممنوع البيع"
        elif "بيعي" not in candle: reason=f"الشمعة {candle} لا توافق بيع"
        else: final="SELL"
    return {"p":pr,"ma":ma,"rsi":rsi,"macd":mv,"sig":sv,"atr":atr,"fib":fib,"candle":candle,"trend":trend,"final":final,"reason":reason,"ob":"بلوك شرائي" if float(c.iloc[-1])>float(o.iloc[-1]) else "بلوك بيعي"}

def load_state():
    return json.loads(open(STATE_FILE).read()) if os.path.exists(STATE_FILE) else {}
def save_state(s): open(STATE_FILE,'w').write(json.dumps(s))

NOW=datetime.now(MUSCAT)
TIME_FULL=NOW.strftime("%A %Y-%m-%d %I:%M:%S %p توقيت عمان")
GOLD_CLOSED=is_gold_closed()
state=load_state()

send_whatsapp(f"✅ تم تفعيل البوت {TIME_FULL}\nذهب/فضة: {'مغلق حتى الاثنين 1ص' if GOLD_CLOSED else 'مفتوح'} | بيتكوين: مفتوح\nفريم 5د | موفنجات 10/20/30/50/70/100/200 + MACD + فيبو + RSI + بلوك + ATR + شموع\nفلتر: لا بيع RSI<25 ولا شراء RSI>75 + الشمعة توافق")

n=get_news_alert()
if n: send_whatsapp(n)

report=f"📊 تقرير كل ساعة {TIME_FULL}\n"; signals=[]
for sym,name in [("GC=F","ذهب"),("SI=F","فضة"),("BTC-USD","بيتكوين")]:
    if name in ["ذهب","فضة"] and GOLD_CLOSED:
        report+=f"{name}: مغلق حتى الاثنين 1ص\n"; continue
    df=get_df(sym)
    if df is None: continue
    a=analyze(df)
    report+=f"{name}:{a['p']:.2f} {a['trend']} RSI:{a['rsi']:.0f} {a['candle']} => {a['final']} {a['reason']}\n"
    if a['final']!="WAIT":
        signals.append((name,a))
        if state.get(f"{name}_final") and state.get(f"{name}_final")!=a['final']:
            send_whatsapp(f"🔄 تغيير {name} {TIME_FULL}\nمن {state.get(f'{name}_final')} الى {a['final']}\nالسعر:{a['p']:.2f}")

for name,a in signals: state[f"{name}_final"]=a['final']

if state.get("last_hour")!=NOW.hour:
    send_whatsapp(report); state["last_hour"]=NOW.hour

save_state(state)

for name,a in signals:
    buy=a['final']=="BUY"; atr=a['atr']; p=a['p']
    sl=p-atr*2.2 if buy else p+atr*2.2
    tp1=p+atr*1.1 if buy else p-atr*1.1
    tp2=p+atr*2.2 if buy else p-atr*2.2
    tp3=p+atr*3.5 if buy else p-atr*3.5
    send_whatsapp(f"""🚨 ادخل الصفقة الان 🚨
⏰ {TIME_FULL}
💰 {name}
💵 السعر الحالي:{p:.2f}
📈 نوع الترند:{a['trend']}
{'🟢 شراء' if buy else '🔴 بيع'}: {a['final']}
🎯 الدخول:{p:.2f}
هدف1:{tp1:.2f}
هدف2:{tp2:.2f}
هدف3:{tp3:.2f}
⛔ وقف الخسارة:{sl:.2f}
RSI:{a['rsi']:.0f} MACD:{a['macd']:.3f}
فيبو:{a['fib'][0]} {a['fib'][1]:.2f}
{a['ob']} | {a['candle']} | ATR:{atr:.2f}
MA10:{a['ma'][10]:.2f} 20:{a['ma'][20]:.2f} 30:{a['ma'][30]:.2f} 50:{a['ma'][50]:.2f} 70:{a['ma'][70]:.2f} 100:{a['ma'][100]:.2f} 200:{a['ma'][200]:.2f}""")
