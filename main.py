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

def find_order_block(df):
    # نبحث في اخر 50 شمعة
    df50=df.tail(50)
    bullish_ob=None
    bearish_ob=None
    for i in range(len(df50)-5, 5, -1):
        curr=df50.iloc[i]
        nxt=df50.iloc[i+1:i+4]
        # بلوك شرائي: شمعة حمراء + بعدها 3 شمعات خضراء قوية
        if curr["Close"] < curr["Open"] and (nxt["Close"] > nxt["Open"]).all() and (nxt["Close"].iloc[-1] - curr["Low"]) > curr["ATR"]*1.5:
            bullish_ob=float(curr["Low"])
            break
    for i in range(len(df50)-5, 5, -1):
        curr=df50.iloc[i]
        nxt=df50.iloc[i+1:i+4]
        # بلوك بيعي: شمعة خضراء + بعدها 3 شمعات حمراء قوية
        if curr["Close"] > curr["Open"] and (nxt["Close"] < nxt["Open"]).all() and (curr["High"] - nxt["Close"].iloc[-1]) > curr["ATR"]*1.5:
            bearish_ob=float(curr["High"])
            break
    return bullish_ob, bearish_ob

muscat=get_muscat_time()
t_str=muscat.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(muscat):
    send(f"⏰ {t_str}\n🥇 مغلق")
else:
    df=yf.download("GC=F", period="5d", interval="1m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]; h=df["High"]; l=df["Low"]; o=df["Open"]
    df["MA20"]=c.rolling(20).mean()
    df["MA50"]=c.rolling(50).mean()
    df["MA100"]=c.rolling(100).mean()
    df["MA200"]=c.rolling(200).mean()
    df["RSI"]=rsi(c)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df["ATR"]=tr.rolling(14).mean()

    ex=get_exness()
    last=df.iloc[-1]
    price=ex if ex else float(last["Close"])
    rsi_now=float(last["RSI"])
    atr=float(last["ATR"])

    # فيبو
    last100=df.tail(100)
    hi=float(last100["High"].max()); lo=float(last100["Low"].min())
    diff=hi-lo
    fib_618=hi-diff*0.618
    fib_05=hi-diff*0.5
    near_fib=None
    for level in [fib_618, fib_05, hi-diff*0.382]:
        if abs(price-level) < atr*1.5:
            near_fib=level
            break

    # بلوك اوردر
    bull_ob, bear_ob=find_order_block(df)
    near_ob=None
    ob_price=None
    if bull_ob and abs(price-bull_ob) < atr*2:
        near_ob="طلب"; ob_price=bull_ob
    if bear_ob and abs(price-bear_ob) < atr*2:
        near_ob="عرض"; ob_price=bear_ob

    # ترند 20/50/100/200
    if last["MA20"]>last["MA50"]>last["MA100"]>last["MA200"]: trend="صاعد قوي"
    elif last["MA20"]<last["MA50"]<last["MA100"]<last["MA200"]: trend="هابط قوي"
    elif last["MA20"]>last["MA50"]: trend="صاعد"
    elif last["MA20"]<last["MA50"]: trend="هابط"
    else: trend="عرضي"

    signal=None
    if (near_fib or near_ob) and trend in ["صاعد قوي","صاعد"] and 35 <= rsi_now <= 68 and (near_ob!="عرض"):
        signal="شراء"
    elif (near_fib or near_ob) and trend in ["هابط قوي","هابط"] and 32 <= rsi_now <= 65 and (near_ob!="طلب"):
        signal="بيع"

    if signal:
        sl=price-atr*2 if signal=="شراء" else price+atr*2
        tp1=price+atr*1.5 if signal=="شراء" else price-atr*1.5
        tp2=price+atr*3 if signal=="شراء" else price-atr*3
        tp3=price+atr*4.5 if signal=="شراء" else price-atr*4.5

        ob_txt=f"بلوك {near_ob} {ob_price:.2f}" if near_ob else "بدون بلوك"
        fib_txt=f"فيبو {near_fib:.2f}" if near_fib else "بعيد عن الفيبو"

        msg=(f"🚀🚀🚀 {signal} الان - 1M 🚀🚀🚀\n\n"
             f"⏰ {t_str}\n💰 {price:.2f}\n"
             f"📈 {trend} (20/50/100/200)\n"
             f"📊 RSI {rsi_now:.1f}\n"
             f"📐 {fib_txt}\n"
             f"📦 {ob_txt}\n\n"
             f"دخول {price:.2f}\nهدف1 {tp1:.2f}\nهدف2 {tp2:.2f}\nهدف3 {tp3:.2f}\nوقف {sl:.2f}")
        for i in range(3):
            send(msg)
            time.sleep(1)
    else:
        fib_info=f"{near_fib:.2f}" if near_fib else f"بعيد عن 0.618 ({fib_618:.2f})"
        ob_info=f"بلوك {near_ob} {ob_price:.2f}" if near_ob else "لا يوجد بلوك قريب"
        send(f"⏰ {t_str}\n🥇 {price:.2f} [1M]\n📈 {trend}\n📊 RSI {rsi_now:.1f}\n📐 {fib_info}\n📦 {ob_info}\n🤖 لا اشارة")
