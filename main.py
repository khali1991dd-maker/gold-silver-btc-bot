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

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 مغلق")
else:
    df=yf.download("GC=F", period="2d", interval="1m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]
    df["MA21"]=c.rolling(21).mean()
    df["MA55"]=c.rolling(55).mean()
    df["RSI"]=rsi(c)
    df["MACD"]=c.ewm(span=12).mean() - c.ewm(span=26).mean()
    df["SIG"]=df["MACD"].ewm(span=9).mean()
    tr=pd.concat([df["High"]-df["Low"],(df["High"]-c.shift()).abs(),(df["Low"]-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean().iloc[-1]

    last=df.iloc[-1]; prev=df.iloc[-2]
    price=float(c.iloc[-1])
    r=float(last["RSI"])

    ma_trend="صاعد" if last["MA21"]>last["MA55"] else "هابط"
    buy_cross = prev["MACD"] < prev["SIG"] and last["MACD"] > last["SIG"]
    sell_cross = prev["MACD"] > prev["SIG"] and last["MACD"] < last["SIG"]

    signal=None
    if ma_trend=="صاعد" and buy_cross and 35 <= r <= 70:
        signal="شراء"
    elif ma_trend=="هابط" and sell_cross and 30 <= r <= 65:
        signal="بيع"

    if signal:
        sl=price-atr*2 if signal=="شراء" else price+atr*2
        tp1=price+atr*1.5 if signal=="شراء" else price-atr*1.5
        tp2=price+atr*3 if signal=="شراء" else price-atr*3
        tp3=price+atr*4.5 if signal=="شراء" else price-atr*4.5
        msg=(f"🚀🚀🚀 {signal} الان [1M] 🚀🚀🚀\n⏰ {t_str}\n💰 {price:.2f}\n"
             f"📈 {ma_trend} 21/55\n📉 MACD تقاطع {'صاعد' if buy_cross else 'هابط'}\n📊 RSI {r:.1f}\n\n"
             f"دخول {price:.2f}\nهدف1 {tp1:.2f}\nهدف2 {tp2:.2f}\nهدف3 {tp3:.2f}\nوقف {sl:.2f}")
        for i in range(3):
            send(msg)
            time.sleep(1)
    else:
        macd_s="صاعد" if last["MACD"]>last["SIG"] else "هابط"
        send(f"⏰ {t_str}\n🥇 {price:.2f} [1M]\n📈 {ma_trend} 21/55\n📉 MACD {macd_s}\n📊 RSI {r:.1f}\n🤖 لا اشارة")

print("Done 1M 21/55 + MACD + RSI")
