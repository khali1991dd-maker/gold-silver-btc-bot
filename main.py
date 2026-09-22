import os, requests, datetime, time, pandas as pd

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=20)
    except Exception as e:
        print(e)

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
    rs=g/l
    return 100-(100/(1+rs))

def get_exness_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=6).json()
        p=float(r.get('price',0))
        if p>1000: return p, "Exness مباشر"
    except: pass
    return None, None

def get_tv_candles():
    try:
        from tvDatafeed import TvDatafeed, Interval
        tv = TvDatafeed()
        df = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_5_minute, n_bars=500)
        if df is None or len(df)<250:
            df = tv.get_hist(symbol='XAUUSD', exchange='FXCM', interval=Interval.in_5_minute, n_bars=500)
        if df is None or len(df)<250:
            df = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_5_minute, n_bars=500, extended_session=False)
        return df
    except Exception as e:
        print(f"TV fail {e}")
        return None

muscat = get_muscat_time()
t_str = muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 الذهب - السوق مغلق")
else:
    df = get_tv_candles()
    source_candle = "TradingView OANDA = نفس MT5"

    if df is None or df.empty:
        import yfinance as yf
        df = yf.download("GC=F", period="30d", interval="5m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        source_candle = "Yahoo احتياطي"
        df.rename(columns={"Close":"close","High":"high","Low":"low","Open":"open"}, inplace=True)

    df.columns = [c.lower() for c in df.columns]
    c=df["close"]; h=df["high"]; l=df["low"]; o=df["open"]

    df["ma20"]=c.rolling(20).mean()
    df["ma50"]=c.rolling(50).mean()
    df["ma100"]=c.rolling(100).mean()
    df["ma200"]=c.rolling(200).mean().shift(14)

    df["rsi"]=rsi(c,14)
    df["macd"]=c.ewm(span=5).mean() - c.ewm(span=20).mean()

    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    last = df.iloc[-1]
    price, price_src = get_exness_price()
    if price is None:
        price=float(c.iloc[-1])
        price_src="TV"

    r = float(df["rsi"].iloc[-1])
    macd_val = float(df["macd"].iloc[-1])

    # فيبو حسب صورتك 0,0.25,0.5,1
    look=50
    rh=float(h[-look:].max()); rl=float(l[-look:].min()); fr=rh-rl
    fib_25 = rh - fr*0.25
    fib_50 = rh - fr*0.5
    fib_25_up = rl + fr*0.25
    fib_50_up = rl + fr*0.5

    near_fib=False; fib_txt=""
    for lvl, val in [("0.25",fib_25),("0.5",fib_50),("0.25",fib_25_up),("0.5",fib_50_up)]:
        if abs(price-val) < atr*0.7:
            near_fib=True
            fib_txt=f"فيبو {lvl} = {val:.1f}"
            break

    # Order Block
    ob_txt=""; ob_price=0
    for i in range(-12, -4):
        # بيعي
        if o.iloc[i] < c.iloc[i] and (o.iloc[i+1]-c.iloc[i+1]) > atr*0.6:
            ob_price=(o.iloc[i]+c.iloc[i])/2
            if abs(price-ob_price) < atr*1.0:
                ob_txt=f"OB بيعي {ob_price:.1f}"
                break
        # شرائي
        if o.iloc[i] > c.iloc[i] and (c.iloc[i+1]-o.iloc[i+1]) > atr*0.6:
            ob_price=(o.iloc[i]+c.iloc[i])/2
            if abs(price-ob_price) < atr*1.0:
                ob_txt=f"OB شرائي {ob_price:.1f}"
                break

    near_key = near_fib or (ob_txt!="")
    ma20=df["ma20"].iloc[-1]; ma50=df["ma50"].iloc[-1]; ma100=df["ma100"].iloc[-1]; ma200=df["ma200"].iloc[-1]

    up = ma20 > ma50 > ma100 > ma200
    down = ma20 < ma50 < ma100 < ma200

    signal=None; reason=""
    if 30 <= r <= 70 and near_key:
        if up and macd_val > 0:
            signal="شراء"
            reason = ob_txt if ob_txt else fib_txt
        elif down and macd_val < 0:
            signal="بيع"
            reason = ob_txt if ob_txt else fib_txt

    if signal:
        sl = price - atr*2 if signal=="شراء" else price + atr*2
        tp1 = price + atr*1.5 if signal=="شراء" else price - atr*1.5
        tp2 = price + atr*3 if signal=="شراء" else price - atr*3
        tp3 = price + atr*4.5 if signal=="شراء" else price - atr*4.5

        msg = (f"🚀 {signal} قوي [{source_candle}]\n"
               f"⏰ {t_str}\n"
               f"💰 السعر {price:.2f} [{price_src}]\n"
               f"📦 {reason}\n"
               f"📈 موفنجات 20/50/100@0 + 200@14 مرتبة\n"
               f"📉 MACD {macd_val:.3f} {'فوق 0 ✅' if macd_val>0 else 'تحت 0 ✅'}\n"
               f"📊 RSI {r:.1f}\n\n"
               f"دخول {price:.2f}\n"
               f"هدف 1 {tp1:.2f}\n"
               f"هدف 2 {tp2:.2f}\n"
               f"هدف 3 {tp3:.2f}\n"
               f"وقف {sl:.2f}")

        for i in range(5):
            send(msg)
            time.sleep(1.5)
    else:
        send(f"⏰ {t_str}\n🥇 {price:.2f} [{source_candle} + {price_src}]\n📈 20:{ma20:.1f} 50:{ma50:.1f} 100:{ma100:.1f} 200@14:{ma200:.1f}\n📊 RSI {r:.1f} MACD {macd_val:.3f}\n📐 فيبو 0.25 {fib_25:.1f} 0.5 {fib_50:.1f}\n🚫 لا اشارة - الموفنجات مو مرتبة او بعيد عن OB/فيبو")

print("Done TV MT5 Exness 5 msgs")
