import yfinance as yf, pandas as pd, pytz, requests, os, json
from datetime import datetime
oman = pytz.timezone('Asia/Muscat')
NOW = datetime.now(oman)

TG_TOKEN=os.getenv("TG_TOKEN"); TG_CHAT=os.getenv("TG_CHAT")
WA_PHONE="968XXXXXXXX" # <-- حط رقمك هنا
WA_KEY=os.getenv("WA_KEY")
FILE="last.json"

def send(t):
    t=t.replace('""','"').replace("''","'").strip()
    try: requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",data={"chat_id":TG_CHAT,"text":t},timeout=10)
    except: pass
    try:
        if WA_KEY: requests.get(f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={requests.utils.quote(t)}&apikey={WA_KEY}",timeout=10)
    except: pass
    print(t)

def gold_closed():
    w=NOW.weekday(); h=NOW.hour
    return (w==4 and h>=23) or w==5 or w==6 or (w==0 and h<1)

def calc(df):
    for p in [10,20,30,50,70,100,200]: df[f'MA{p}']=df['Close'].rolling(p).mean()
    d=df['Close'].diff(); g=d.where(d>0,0).rolling(14).mean(); l=-d.where(d<0,0).rolling(14).mean()
    df['RSI']=100-(100/(1+g/l.replace(0,0.001)))
    e12=df['Close'].ewm(12).mean(); e26=df['Close'].ewm(26).mean()
    df['MACD']=e12-e26; df['SIG']=df['MACD'].ewm(9).mean()
    tr=pd.concat([df['High']-df['Low'],(df['High']-df['Close'].shift()).abs(),(df['Low']-df['Close'].shift()).abs()],axis=1).max(axis=1)
    df['ATR']=tr.rolling(14).mean()
    return df

def last_sig():
    try: return json.load(open(FILE))
    except: return {}
def save_sig(x): open(FILE,'w').write(json.dumps(x))

# تنبيه قبل الخبر بساعة - 4:30م عمان وقت اخبار امريكا
if NOW.hour==15 and NOW.minute<5:
    send(f"⚠️ تنبيه خبر مهم بعد ساعة 4:30م توقيت عمان\n{NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')}")

syms={"ذهب":"GC=F","فضة":"SI=F","بيتكوين":"BTC-USD"}
prev=last_sig()

for name,sym in syms.items():
    if name!="بيتكوين" and gold_closed(): continue
    df=yf.download(sym,period="10d",interval="5m",progress=False)
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    if len(df)<210: continue
    df=calc(df); l=df.iloc[-1]
    price=float(l['Close']); rsi=float(l['RSI']); atr=float(l['ATR']); macd=float(l['MACD']); sig=float(l['SIG'])
    ma={p:float(l[f'MA{p}']) for p in [10,20,30,50,70,100,200]}
    body=abs(l['Close']-l['Open']); rng=l['High']-l['Low']
    is_doji=body<rng*0.15
    bull= l['Close']>l['Open'] and body>rng*0.4
    bear= l['Close']<l['Open'] and body>rng*0.4
    candle="دوجي" if is_doji else "شمعة شرائية قوية" if bull else "شمعة بيعية قوية" if bear else "شمعة شرائية" if l['Close']>l['Open'] else "شمعة بيعية"

    hi=df['High'].tail(40).max(); lo=df['Low'].tail(40).min()
    fibo78=hi-(hi-lo)*0.78; fibo61=hi-(hi-lo)*0.618
    ob="بلوك اوردر شرائي" if df['Close'].iloc[-4]<df['Open'].iloc[-4] and bull else "بلوك اوردر بيعي" if df['Close'].iloc[-4]>df['Open'].iloc[-4] and bear else "بدون بلوك واضح"

    signal=None; trend=None
    # بدون عرضي نهائيا: لازم 5 موفنجات مرتبة + فوق 100 + ماكد مع الترند + شمعة توافق + RSI شرطك
    if price < ma[10] < ma[20] < ma[30] < ma[50] < ma[70] and ma[70] < ma[100] and rsi>=25 and macd<sig and bear and not is_doji:
        signal="SELL"; trend="هابط قوي جدا"
    elif price > ma[10] > ma[20] > ma[30] > ma[50] > ma[70] and ma[70] > ma[100] and rsi<=75 and macd>sig and bull and not is_doji:
        signal="BUY"; trend="صاعد قوي جدا"

    if signal:
        if prev.get(name)!=signal and prev.get(name):
            send(f"🔄 تغيير ترند {name}: من {prev.get(name)} الى {signal}\n{NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')} توقيت عمان")
        if prev.get(name)!=signal:
            sl=price+atr*1.8 if signal=="SELL" else price-atr*1.8
            tp1=price-atr*1.2 if signal=="SELL" else price+atr*1.2
            tp2=price-atr*2.2 if signal=="SELL" else price+atr*2.2
            tp3=price-atr*3.5 if signal=="SELL" else price+atr*3.5
            send(f"""🚨 ادخل الصفقة الان 🚨
⏰ وقت الارسال: {NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')} توقيت عمان
📈 {name} - {signal}
💰 السعر الحالي: {price:.2f}
📊 نوع الترند: {trend}
{'🔴 بيع' if signal=='SELL' else '🟢 شراء'} الدخول: {price:.2f}
🎯 هدف1: {tp1:.2f}
🎯 هدف2: {tp2:.2f}
🎯 هدف3: {tp3:.2f}
⛔ وقف الخسارة: {sl:.2f}
RSI:{rsi:.1f} MACD:{macd:.2f} SIG:{sig:.2f}
ATR:{atr:.2f} فيبو78:{fibo78:.2f} 61:{fibo61:.2f}
{ob}
الشمعة: {candle}
MA10/20/30/50/70/100/200: {ma[10]:.1f}/{ma[20]:.1f}/{ma[30]:.1f}/{ma[50]:.1f}/{ma[70]:.1f}/{ma[100]:.1f}/{ma[200]:.1f}""")
            prev[name]=signal; save_sig(prev)

# تقرير كل ساعة
if NOW.minute<5:
    rep=f"📊 تقرير السوق {NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')} توقيت عمان\nفريم 5د\n"
    for name,sym in syms.items():
        if name!="بيتكوين" and gold_closed():
            rep+=f"🔒 {name}: مغلق الجمعة 11م - الاثنين 1ص\n"; continue
        df=yf.download(sym,period="1d",interval="5m",progress=False)
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        if len(df)<50: continue
        df=calc(df); l=df.iloc[-1]
        rep+=f"{name}:{float(l['Close']):.2f} RSI:{float(l['RSI']):.0f} {'هابط' if float(l['Close'])<float(l['MA20']) else 'صاعد'}\n"
    send(rep)

# رسالة اول تفعيل
if os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch":
    send(f"✅ البوت تفعل {NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')} توقيت عمان\nالذهب/الفضة مغلق جمعة 11م - اثنين 1ص\nفريم 5د - التقرير كل ساعة والصفقات فورية")
