import os, requests, datetime, pytz, yfinance as yf, pandas as pd, numpy as np
from urllib.parse import quote

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)
tok = os.getenv("TG_TOKEN")
chat = os.getenv("TG_CHAT")

def send(m):
    try:
        url = f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m)}&parse_mode=Markdown"
        requests.get(url, timeout=15)
    except Exception as e:
        print(e)

def gold_closed():
    wd = NOW.weekday() # 0=اثنين
    h = NOW.hour
    # جمعة 11م = 4, من 23:00
    if wd == 4 and h >= 23: return True
    if wd == 5: return True # سبت كامل
    if wd == 6 and h < 1: return True # احد لين 1ص
    # اثنين 1ص يفتح = wd0 h>=1 مفتوح
    if wd == 0 and h < 1: return True
    return False

def get_data(symbol):
    df = yf.download(symbol, period="10d", interval="5m", auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df.dropna()

def indicators(df):
    c = df['Close']
    ma = {}
    for p in [10,20,30,50,70,100,200]:
        ma[p] = c.rolling(p).mean().iloc[-1]
    # MACD
    ema12 = c.ewm(span=12).mean(); ema26 = c.ewm(span=26).mean()
    macd = (ema12-ema26).iloc[-1]
    sig = (ema12-ema26).ewm(span=9).mean().iloc[-1]
    # RSI
    delta = c.diff(); gain = delta.where(delta>0,0).rolling(14).mean(); loss = -delta.where(delta<0,0).rolling(14).mean()
    rs = gain/loss; rsi = 100-(100/(1+rs)); rsi = rsi.iloc[-1]
    # ATR
    tr = pd.concat([df['High']-df['Low'], (df['High']-c.shift()).abs(), (df['Low']-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    # فيبوناتشي
    hi = df['High'].rolling(100).max().iloc[-1]; lo = df['Low'].rolling(100).min().iloc[-1]
    fib61 = hi - (hi-lo)*0.61; fib78 = hi - (hi-lo)*0.78
    # شموع
    last = df.iloc[-1]; body = abs(last['Close']-last['Open']); rng = last['High']-last['Low']
    is_doji = body < rng*0.1
    bull = last['Close'] > last['Open'] and body > rng*0.6
    bear = last['Close'] < last['Open'] and body > rng*0.6
    candle = "دوجي" if is_doji else "قوية صاعدة" if bull else "قوية هابطة" if bear else "عادية"
    # بلوك اوردر
    block = "يوجد" if rng > atr*1.8 and last['Volume'] > df['Volume'].rolling(20).mean().iloc[-1]*1.5 else "لا يوجد"
    return ma, macd, sig, rsi, atr, fib61, fib78, candle, bull, bear, is_doji, block, c.iloc[-1]

# 1- تنبيه قبل الخبر بساعة (3:30م -> خبر 4:30م)
if NOW.hour == 15 and NOW.minute < 5:
    send(f"⚠️ *تنبيه خبر مهم*\nالساعة 4:30م بتوقيت مسقط خبر قوي على الدولار - لا تدخل صفقات جديدة قبل الخبر\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")

# تقرير كل ساعة
is_hourly = NOW.minute < 5

for sym, name in [("GC=F","الذهب"), ("SI=F","الفضة"), ("BTC-USD","BTC")]:
    if name!= "BTC" and gold_closed() and not is_hourly:
        continue
    if name!= "BTC" and gold_closed() and is_hourly:
        send(f"⏸️ {name} مغلق\nالذهب يغلق جمعة 11م ويفتح اثنين 1ص بتوقيت مسقط\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')}")
        continue

    df = get_data(sym)
    if len(df) < 200: continue
    ma, macd, sig, rsi, atr, f61, f78, candle, bull, bear, doji, block, price = indicators(df)

    # بدون دخول عرضي: سعر < MA10 < MA20 < MA30 < MA50 < MA70 < MA100 = صاعد مرتب
    up_trend = price < ma[10] < ma[20] < ma[30] < ma[50] < ma[70] < ma[100] if False else ma[10] > ma[20] > ma[30] > ma[50] > ma[70] > ma[100] and price > ma[10]
    # شرطك: سعر < MA10 <... للبيع، والعكس للشراء - نطبق الصح: للشراء لازم السعر فوق الكل والموفنجات مرتبة صاعدة
    # التعديل حسب شرطك الحرفي: شراء = سعر < MA10 <... مستحيل يكون صاعد، فالمقصود ترتيب موفنجات
    # نطبق: صاعد = MA10>MA20>MA30>MA50>MA70>MA100 و سعر > MA10
    # هابط = MA10<MA20<MA30<MA50<MA70<MA100 و سعر < MA10
    strong_up = ma[10] > ma[20] > ma[30] > ma[50] > ma[70] > ma[100] and price > ma[10]
    strong_down = ma[10] < ma[20] < ma[30] < ma[50] < ma[70] < ma[100] and price < ma[10]

    # RSI فلتر
    can_buy = rsi <= 75
    can_sell = rsi >= 25

    # شمعة توافق الترند + مو دوجي
    buy_ok = strong_up and bull and not doji and macd > sig and can_buy and price > f61
    sell_ok = strong_down and bear and not doji and macd < sig and can_sell and price < f61

    trend_type = "صاعد قوي مرتب" if strong_up else "هابط قوي مرتب" if strong_down else "عرضي - لا دخول"

    # كل 5 دقايق صفقة فورية + كل ساعة تقرير
    if buy_ok or sell_ok or is_hourly:
        action = "🟢 شراء" if buy_ok else "🔴 بيع" if sell_ok else "🟡 انتظار"
        entry = price
        if buy_ok:
            tp1, tp2, tp3 = entry+atr, entry+atr*2, entry+atr*3
            sl = entry-atr*1.5
        elif sell_ok:
            tp1, tp2, tp3 = entry-atr, entry-atr*2, entry-atr*3
            sl = entry+atr*1.5
        else:
            tp1=tp2=tp3=sl=0

        msg = f"""{'🚀 ادخل الصفقة الان' if buy_ok or sell_ok else '📊 تقرير ساعي'} {name}
⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط
💰 السعر الحالي: {price:.2f}
📈 نوع الترند: {trend_type}
{action}

📊 المؤشرات:
MA10={ma[10]:.2f} MA20={ma[20]:.2f} MA30={ma[30]:.2f}
MA50={ma[50]:.2f} MA70={ma[70]:.2f} MA100={ma[100]:.2f} MA200={ma[200]:.2f}
MACD={macd:.2f} SIG={sig:.2f}
RSI={rsi:.1f} ATR={atr:.2f}
فيبو 61%={f61:.2f} 78%={f78:.2f}
شمعة: {candle} بلوك اوردر: {block}
"""
        if buy_ok or sell_ok:
            msg += f"""
🎯 الدخول: {entry:.2f}
هدف1: {tp1:.2f} هدف2: {tp2:.2f} هدف3: {tp3:.2f}
⛔ وقف: {sl:.2f}
"""
        send(msg)

# كرون: */5 * * * * + توقيت Asia/Muscat في الـ yml
