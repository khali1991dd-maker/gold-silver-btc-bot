import os, requests, datetime, yfinance as yf, pandas as pd, time

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(m):
    wd=m.weekday(); h=m.hour
    if wd==4 and h>=23: return False
    if wd==5: return False
    if wd==6 and h<1: return False
    return True

def rsi(s, p=14):
    d=s.diff()
    g=d.clip(lower=0).ewm(alpha=1/p).mean()
    l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))

def get_exness():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if p>1000: return p
    except: pass
    return None

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 مغلق")
else:
    df=yf.download("GC=F", period="2d", interval="1m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]; h=df["High"]; l=df["Low"]
    ma30=c.rolling(30).mean().iloc[-1]
    ma70=c.rolling(70).mean().iloc[-1]
    r=rsi(c).iloc[-1]
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean().iloc[-1]
    ex=get_exness()
    price=ex if ex else float(c.iloc[-1])

    trend="صاعد" if ma30>ma70 else "هابط"
    signal=None
    if ma30>ma70 and 40 <= r <= 70: signal="شراء"
    elif ma30<ma70 and 30 <= r <= 60: signal="بيع"

    if signal:
        sl=price-atr*2 if signal=="شراء" else price+atr*2
        tp1=price+atr*1.5 if signal=="شراء" else price-atr*1.5
        tp2=price+atr*3 if signal=="شراء" else price-atr*3
        tp3=price+atr*4.5 if signal=="شراء" else price-atr*4.5
        msg=(f"🚀 {signal} الان - 1M\n⏰ {t_str}\n💰 {price:.2f}\n📈 {trend} 30>70\n📊 RSI {r:.1f}\n\n"
             f"دخول {price:.2f}\nهدف1 {tp1:.2f}\nهدف2 {tp2:.2f}\nهدف3 {tp3:.2f}\nوقف {sl:.2f}")
        for i in range(3):
            send(msg)
            time.sleep(1)
    else:
        send(f"⏰ {t_str}\n🥇 {price:.2f} [1M]\n📈 {trend} 30/70\n📊 RSI {r:.1f}\n🤖 لا اشارة")
