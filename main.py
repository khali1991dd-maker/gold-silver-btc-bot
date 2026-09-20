import yfinance as yf, pandas as pd, pytz, requests, os, json
from datetime import datetime
oman=pytz.timezone('Asia/Muscat')
NOW=datetime.now(oman)
TG_TOKEN=os.getenv("TG_TOKEN")
TG_CHAT=os.getenv("TG_CHAT")
FILE="last.json"
def send(t):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",data={"chat_id":TG_CHAT,"text":t},timeout=15)
    print(t)
def gold_closed():
    w=NOW.weekday();h=NOW.hour
    return (w==4 and h>=23) or w==5 or w==6 or (w==0 and h<1)
def calc(df):
    for p in [10,20,30,50,70,100,200]:df[f'MA{p}']=df['Close'].rolling(p).mean()
    d=df['Close'].diff();g=d.where(d>0,0).rolling(14).mean();l=-d.where(d<0,0).rolling(14).mean()
    df['RSI']=100-(100/(1+g/l.replace(0,0.001)))
    df['MACD']=df['Close'].ewm(12).mean()-df['Close'].ewm(26).mean()
    df['SIG']=df['MACD'].ewm(9).mean()
    tr=pd.concat([df['High']-df['Low'],(df['High']-df['Close'].shift()).abs(),(df['Low']-df['Close'].shift()).abs()],axis=1).max(axis=1)
    df['ATR']=tr.rolling(14).mean()
    return df
def load():
    try:return json.load(open(FILE))
    except:return {}
def save(x):open(FILE,'w').write(json.dumps(x))
if NOW.hour==15 and NOW.minute<5:
    send(f"⚠️ تنبيه خبر 4:30م بعد ساعة\n{NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')}")
syms={"ذهب":"GC=F","فضة":"SI=F","بيتكوين":"BTC-USD"}
prev=load()
for name,sym in syms.items():
    if name!="بيتكوين" and gold_closed():continue
    df=yf.download(sym,period="10d",interval="5m",progress=False)
    if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
    if len(df)<210:continue
    df=calc(df);l=df.iloc[-1]
    price=float(l['Close']);rsi=float(l['RSI']);atr=float(l['ATR']);macd=float(l['MACD']);sig=float(l['SIG'])
    ma={p:float(l[f'MA{p}']) for p in [10,20,30,50,70,100,200]}
    body=abs(l['Close']-l['Open']);rng=l['High']-l['Low']
    is_doji=body<rng*0.15;bull=l['Close']>l['Open'] and body>rng*0.4;bear=l['Close']<l['Open'] and body>rng*0.4
    hi=df['High'].tail(40).max();lo=df['Low'].tail(40).min()
    fibo78=hi-(hi-lo)*0.78;fibo61=hi-(hi-lo)*0.618
    ob="بلوك شرائي" if df['Close'].iloc[-4]<df['Open'].iloc[-4] and bull else "بلوك بيعي" if df['Close'].iloc[-4]>df['Open'].iloc[-4] and bear else "بدون بلوك"
    candle="دوجي" if is_doji else "شرائية قوية" if bull else "بيعية قوية" if bear else "شرائية" if l['Close']>l['Open'] else "بيعية"
    signal=None;trend=None
    if price<ma[10]<ma[20]<ma[30]<ma[50]<ma[70]<ma[100] and rsi>=25 and macd<sig and bear and not is_doji:
        signal="SELL";trend="هابط قوي جدا"
    elif price>ma[10]>ma[20]>ma[30]>ma[50]>ma[70]>ma[100] and rsi<=75 and macd>sig and bull and not is_doji:
        signal="BUY";trend="صاعد قوي جدا"
    if signal and prev.get(name)!=signal:
        if prev.get(name):send(f"🔄 تغيير {name}:{prev.get(name)}->{signal}\n{NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')}")
        sl=price+atr*1.8 if signal=="SELL" else price-atr*1.8
        tp1=price-atr*1.2 if signal=="SELL" else price+atr*1.2
        tp2=price-atr*2.2 if signal=="SELL" else price+atr*2.2
        tp3=price-atr*3.5 if signal=="SELL" else price+atr*3.5
        send(f"🚨 ادخل الصفقة الان 🚨\n⏰ {NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')} عمان\n📈 {name}-{signal}\n💰 الحالي:{price:.2f}\n📊 الترند:{trend}\n{'🔴 بيع' if signal=='SELL' else '🟢 شراء'}:{price:.2f}\n🎯1:{tp1:.2f}\n🎯2:{tp2:.2f}\n🎯3:{tp3:.2f}\n⛔ وقف:{sl:.2f}\nRSI:{rsi:.1f} MACD:{macd:.2f}\nATR:{atr:.2f} فيبو78:{fibo78:.2f} 61:{fibo61:.2f}\n{ob}\n{candle}")
        prev[name]=signal;save(prev)
if NOW.minute<5:
    rep=f"📊 تقرير {NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')} عمان\n"
    for name,sym in syms.items():
        if name!="بيتكوين" and gold_closed():
            rep+=f"🔒 {name}:مغلق\n";continue
        df=yf.download(sym,period="1d",interval="5m",progress=False)
        if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
        if len(df)<50:continue
        df=calc(df);l=df.iloc[-1]
        rep+=f"{name}:{float(l['Close']):.2f} RSI:{float(l['RSI']):.0f}\n"
    send(rep)
if os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch":
    send(f"✅ البوت تفعل {NOW.strftime('%A %Y-%m-%d %I:%M:%S %p')}")
