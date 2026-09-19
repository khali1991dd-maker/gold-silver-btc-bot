import requests, pytz
from datetime import datetime
import yfinance as yf
import pandas as pd
MUSCAT=pytz.timezone('Asia/Muscat')
NOW=datetime.now(MUSCAT)
TIME_FULL=NOW.strftime("%A %Y-%m-%d %I:%M %p توقيت عمان")
PHONE="96897134774"
APIKEY="4515814"
def send(t):
 for i in range(0,len(t),2800):
  try:
   u=f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={requests.utils.quote(t[i:i+2800])}&apikey={APIKEY}"
   requests.get(u,timeout=20)
  except: pass
def get_df(s):
 try:
  df=yf.download(s,period="5d",interval="5m",progress=False,auto_adjust=True)
  if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
  return df if len(df)>=210 else None
 except: return None
def analyze(df):
 c=df['Close'];h=df['High'];l=df['Low'];o=df['Open']
 ma={p:float(c.rolling(p).mean().iloc[-1]) for p in [10,20,30,50,70,100,200]}
 d=c.diff();g=d.where(d>0,0).rolling(14).mean();lo=-d.where(d<0,0).rolling(14).mean()
 rsi=float((100-(100/(1+g/lo))).iloc[-1])
 e12=c.ewm(span=12).mean();e26=c.ewm(span=26).mean();macd=e12-e26;sig=macd.ewm(span=9).mean()
 mv=float(macd.iloc[-1]);sv=float(sig.iloc[-1])
 tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
 atr=float(tr.rolling(14).mean().iloc[-1])
 hh=float(h.tail(50).max());ll=float(l.tail(50).min());diff=hh-ll
 fib={"23%":hh-diff*0.236,"38%":hh-diff*0.382,"50%":hh-diff*0.5,"61%":hh-diff*0.618}
 pr=float(c.iloc[-1]);near=min(fib.items(),key=lambda x:abs(x[1]-pr))
 o0=float(o.iloc[-1]);c0=pr;body=abs(c0-o0)
 ob="بلوك شرائي" if c0>o0 and body>atr*0.6 else "بلوك بيعي" if c0<o0 and body>atr*0.6 else "بدون"
 po=float(o.iloc[-2]);pc=float(c.iloc[-2])
 candle="ابتلاع شرائي" if c0>o0 and pc<po else "ابتلاع بيعي" if c0<o0 and pc>po else "عادية"
 trend="صاعد 📈" if ma[10]>ma[20]>ma[30] else "هابط 📉" if ma[10]<ma[20]<ma[30] else "عرضي"
 buy=(ma[10]>ma[20])+(mv>sv)+(1 if rsi>50 else 0);sell=(ma[10]<ma[20])+(mv<sv)+(1 if rsi<50 else 0)
 final="BUY" if buy>=2 and buy>sell else "SELL" if sell>=2 and sell>buy else "WAIT"
 return {"p":pr,"ma":ma,"rsi":rsi,"atr":atr,"fib":near,"ob":ob,"candle":candle,"trend":trend,"final":final}
send(f"✅ تم تفعيل البوت {TIME_FULL}")
rep=f"📊 تقرير {TIME_FULL}\n";trds=[]
for sym,name in [("GC=F","ذهب"),("SI=F","فضة"),("BTC-USD","بيتكوين")]:
 df=get_df(sym)
 if df is not None:
  a=analyze(df)
  rep+=f"{name}:{a['p']:.2f} {a['trend']} RSI:{a['rsi']:.0f} =>{a['final']}\n"
  if a['final']!="WAIT": trds.append((name,a))
send(rep)
for name,a in trds:
 sl=a['p']-a['atr']*2 if a['final']=="BUY" else a['p']+a['atr']*2
 tp1=a['p']+a['atr']*1.2 if a['final']=="BUY" else a['p']-a['atr']*1.2
 tp2=a['p']+a['atr']*2.5 if a['final']=="BUY" else a['p']-a['atr']*2.5
 tp3=a['p']+a['atr']*4 if a['final']=="BUY" else a['p']-a['atr']*4
 send(f"🚨 ادخل {name} {a['final']} {TIME_FULL} السعر:{a['p']:.2f} ترند:{a['trend']} دخول:{a['p']:.2f} هدف1:{tp1:.2f} هدف2:{tp2:.2f} هدف3:{tp3:.2f} وقف:{sl:.2f} RSI:{a['rsi']:.0f} فيبو:{a['fib'][0]} بلوك:{a['ob']} شمعة:{a['candle']}")
