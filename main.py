import os, requests, datetime, yfinance as yf, pandas as pd, numpy as np

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try:
        requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=10)
    except: pass

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(symbol, muscat):
    if "BTC" in symbol: return True
    wd = muscat.weekday() # 0=Mon
    h = muscat.hour
    if wd == 4 and h >= 23: return False # Fri 11pm
    if wd == 5: return False # Sat
    if wd == 6: return False # Sun
    if wd == 0 and h < 1: return False # Mon before 1am
    return True

def rsi(series, p=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/p).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/p).mean()
    rs = gain / loss
    return 100 - (100/(1+rs))

def get_analysis(symbol):
    try:
        df = yf.download(symbol, period="10d", interval="5m", progress=False)
        if len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close = df['Close']; high = df['High']; low = df['Low']
        df['MA10']=close.rolling(10).mean(); df['MA20']=close.rolling(20).mean()
        df['MA30']=close.rolling(30).mean(); df['MA50']=close.rolling(50).mean()
        df['MA70']=close.rolling(70).mean(); df['MA100']=close.rolling(100).mean()
        df['MA200']=close.rolling(200).mean()
        # MACD
        ema12=close.ewm(span=12).mean(); ema26=close.ewm(span=26).mean()
        df['MACD']=ema12-ema26; df['SIG']=df['MACD'].ewm(span=9).mean()
        # RSI
        df['RSI']=rsi(close)
        # ATR
        tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
        df['ATR']=tr.rolling(14).mean()
        # Fibonacci
        last100 = df.tail(100)
        hh=last100['High'].max(); ll=last100['Low'].min()
        diff=hh-ll
        fib618 = hh - diff*0.618; fib50= hh - diff*0.5; fib786= hh - diff*0.786

        last = df.iloc[-1]; prev = df.iloc[-2]
        price = float(last['Close']); atr = float(last['ATR'])
        # Trend
        trend = "عرضي"
        if last['MA10']>last['MA20']>last['MA30']>last['MA50']>last['MA70']>last['MA100']:
            trend="صاعد قوي"
        elif last['MA10']<last['MA20']<last['MA30']<last['MA50']<last['MA70']<last['MA100']:
            trend="هابط قوي"

        # Candle
        body = abs(float(last['Close']-last['Open'])); rng = float(last['High']-last['Low'])
        bullish = float(last['Close']) > float(last['Open'])
        bearish = not bullish
        candle = "عادية"
        if rng>0 and body/rng < 0.1: candle="دوجي"
        elif bullish and prev['Close']<prev['Open'] and last['Close']>prev['Open']: candle="ابتلاعية صاعدة"
        elif bearish and prev['Close']>prev['Open'] and last['Close']<prev['Open']: candle="ابتلاعية هابطة"

        # Block order
        block = rng > atr*1.8

        # Entry
        signal = None
        if trend=="صاعد قوي" and price>last['MA10'] and bullish and last['MACD']>last['SIG'] and last['RSI']<=75:
            signal="شراء"
        elif trend=="هابط قوي" and price<last['MA10'] and bearish and last['MACD']<last['SIG'] and last['RSI']>=25:
            signal="بيع"

        return {
            "price": price, "trend": trend, "signal": signal, "rsi": float(last['RSI']),
            "atr": atr, "macd": float(last['MACD']), "sig": float(last['SIG']),
            "fib": (fib618,fib50,fib786), "candle": candle, "block": block, "df": df
        }
    except Exception as e:
        print(f"Error {symbol}: {e}"); return None

# --- MAIN ---
muscat = get_muscat_time()
time_str = muscat.strftime("%d-%m %Y %I:%M %p")
print(f"Time Muscat: {time_str}")

# 1. رسالة التفعيل - اول مرة تشغل يدوي
import sys
if "workflow_dispatch" in str(os.getenv("GITHUB_EVENT_NAME","")) or True:
    # نرسل تفعيل فقط اذا الساعة دقيقة 0 و 5 عشان ما يزعج كل 5د
    if muscat.minute % 60 == 0 or os.getenv("FIRST_RUN"):
        pass

symbols = {"GC=F":"الذهب", "SI=F":"الفضة", "BTC-USD":"البيتكوين"}

# 2. تنبيه خبر 3:30م مسقط
if muscat.hour==15 and muscat.minute>=30 and muscat.minute<35:
    send(f"⚠️ تنبيه خبر مهم الساعة 4:30م مسقط\n\nالذهب والبيتكوين قد يتحرك بقوة، انتبه للصفقات المفتوحة.\n{time_str}")

full_report = []
closed_report = []

for sym, name in symbols.items():
    open_status = is_market_open(sym, muscat)
    if not open_status:
        if muscat.minute % 15 == 0: # كل 15 دقيقة فقط
            closed_report.append(f"{name}: ⏸️ مغلق")
        continue

    an = get_analysis(sym)
    if not an: continue

    # بناء التقرير
    txt = f"{name} {sym}\nالسعر: {an['price']:.2f}\nالترند: {an['trend']}\nRSI: {an['rsi']:.1f}\nالشمعة: {an['candle']}\n"
    if an['block']: txt+= "بلوك اوردر: يوجد ✅\n"
    txt+= f"فيبو 61.8%: {an['fib'][0]:.2f}\n"

    if an['signal']:
        entry = an['price']
        atr = an['atr']
        if an['signal']=="شراء":
            sl = entry - atr*2
            tp1 = entry + atr*1.5; tp2 = entry + atr*3; tp3 = entry + atr*4.5
        else:
            sl = entry + atr*2
            tp1 = entry - atr*1.5; tp2 = entry - atr*3; tp3 = entry - atr*4.5

        msg = f"🚀 ادخل الصفقة الان - {name}\n\n"
        msg+= f"التاريخ: {time_str}\nالسعر الحالي: {entry:.2f}\nنوع الترند: {an['trend']}\n"
        msg+= f"الاشارة: {an['signal']}\nالشمعة: {an['candle']}\nRSI: {an['rsi']:.1f}\n"
        msg+= f"\nالدخول: {entry:.2f}\n"
        msg+= f"هدف1: {tp1:.2f}\nهدف2: {tp2:.2f}\nهدف3: {tp3:.2f}\n"
        msg+= f"وقف خسارة: {sl:.2f}\n"
        msg+= f"ATR: {atr:.2f}"
        send(msg)
    else:
        full_report.append(txt)

# تقرير مغلق
if closed_report and muscat.minute % 15 == 0:
    send("تقرير السوق:\n" + "\n".join(closed_report) + f"\n\n{time_str}")

# اذا تبغى تقرير صامت كل ساعة مثلا (اختياري)
# if muscat.minute==0:
# send("تقرير كل ساعة:\n\n" + "\n---\n".join(full_report))

print("Done")
