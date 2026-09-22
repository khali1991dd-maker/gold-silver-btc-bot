import os, requests, datetime, time, pandas as pd, yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try: requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=20)
    except: pass

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(m):
    if m.weekday()==5: return False
    if m.weekday()==4 and m.hour>=23: return False
    if m.weekday()==6 and m.hour<1: return False
    return True

def rsi(s, p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))

def get_price_mt5():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if 4000 < p < 5000: return p, "سعر إكسنس المباشر"
    except: pass
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5).json()
        p=float(r['price'])
        if 4000 < p < 5000: return p, "سعر إكسنس لايف"
    except: pass
    return None, None

مسقط=get_muscat_time()
الوقت=مسقط.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(مسقط):
    send(f"⏰ الوقت: {الوقت}\n🥇 سوق الذهب مغلق حالياً")
else:
    df=yf.download("XAUUSD=X", period="30d", interval="5m", progress=False, auto_adjust=True)
    if df.empty or len(df)<200:
        df=yf.download("GC=F", period="30d", interval="5m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    c,h,l,o=df["Close"],df["High"],df["Low"],df["Open"]
    df["ma20"]=c.rolling(20).mean()
    df["ma50"]=c.rolling(50).mean()
    df["ma100"]=c.rolling(100).mean()
    df["ma200"]=c.rolling(200).mean().shift(14)
    df["rsi"]=rsi(c,14)
    df["macd"]=c.ewm(span=5).mean() - c.ewm(span=20).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.rolling(14).mean().iloc[-1])

    السعر, المصدر = get_price_mt5()
    if السعر is None:
        السعر=float(c.iloc[-1]); المصدر="احتياطي"

    قوة=float(df["rsi"].iloc[-1])
    ماكد=float(df["macd"].iloc[-1])

    نظرة=50
    قمة=float(h[-نظرة:].max()); قاع=float(l[-نظرة:].min()); فرق=قمة-قاع
    فيبو0=قمة
    فيبو25=قمة-فرق*0.25
    فيبو50=قمة-فرق*0.5
    فيبو100=قاع

    قريب_فيبو=False; نص_فيبو=""
    for اسم, قيمة in [("٢٥٪",فيبو25),("٥٠٪",فيبو50),("٠٪",فيبو0),("١٠٠٪",فيبو100)]:
        if abs(السعر-قيمة) < max(2.5, atr*1.2):
            قريب_فيبو=True; نص_فيبو=f"منطقة فيبو {اسم} عند {قيمة:.2f}"; break

    نص_ob=""
    for i in range(-15, -3):
        zp=(float(o.iloc[i])+float(c.iloc[i]))/2
        if abs(السعر-zp) < max(2.5, atr*1.2):
            if float(o.iloc[i]) < float(c.iloc[i]) and (float(o.iloc[i+1])-float(c.iloc[i+1])) > atr*0.5:
                نص_ob=f"منطقة بيع قوية عند {zp:.2f}"; break
            if float(o.iloc[i]) > float(c.iloc[i]) and (float(c.iloc[i+1])-float(o.iloc[i+1])) > atr*0.5:
                نص_ob=f"منطقة شراء قوية عند {zp:.2f}"; break

    قريب = قريب_فيبو or (نص_ob!="")
    م20=float(df["ma20"].iloc[-1]); م50=float(df["ma50"].iloc[-1]); م100=float(df["ma100"].iloc[-1]); م200=float(df["ma200"].iloc[-1])

    صاعد = م20 > م50 and السعر > م100
    هابط = م20 < م50 and السعر < م100
    صاعد_كامل = م20 > م50 > م100 > م200
    هابط_كامل = م20 < م50 < م100 < م200

    اشارة=None
    if 25 <= قوة <= 75 and قريب:
        if صاعد and ماكد > 0: اشارة="شراء"
        elif هابط and ماكد < 0: اشارة="بيع"

    if اشارة:
        وقف=السعر-atr*2 if اشارة=="شراء" else السعر+atr*2
        هدف1=السعر+atr*1.5 if اشارة=="شراء" else السعر-atr*1.5
        هدف2=السعر+atr*3 if اشارة=="شراء" else السعر-atr*3
        هدف3=السعر+atr*4.5 if اشارة=="شراء" else السعر-atr*4.5
        سبب=نص_ob if نص_ob else نص_فيبو
        ترتيب="المتوسطات مرتبة ترتيب كامل" if (صاعد_كامل or هابط_كامل) else "المتوسطات مرتبة جزئياً"

        رسالة=(f"🚀 توصية {اشارة} قوية - فريم 5 دقائق\n"
               f"⏰ الوقت: {الوقت}\n"
               f"💰 سعر الذهب الحالي: {السعر:.2f} دولار [{المصدر}]\n"
               f"📦 السبب: {سبب}\n"
               f"📈 الحالة: {ترتيب}\n"
               f" متوسط 20: {م20:.2f}\n"
               f" متوسط 50: {م50:.2f}\n"
               f" متوسط 100: {م100:.2f}\n"
               f" متوسط 200 مزاح 14 شمعة: {م200:.2f}\n"
               f"📉 مؤشر الماكد: {ماكد:.3f} ({'فوق الصفر - ايجابي' if ماكد>0 else 'تحت الصفر - سلبي'})\n"
               f"📊 مؤشر القوة النسبية: {قوة:.1f}\n\n"
               f"💵 سعر الدخول: {السعر:.2f}\n"
               f"🎯 الهدف الأول: {هدف1:.2f}\n"
               f"🎯 الهدف الثاني: {هدف2:.2f}\n"
               f"🎯 الهدف الثالث: {هدف3:.2f}\n"
               f"🛑 وقف الخسارة: {وقف:.2f}")

        for _ in range(5):
            send(رسالة); time.sleep(1.2)
    else:
        حالة="هابط كامل ✅" if هابط_كامل else "صاعد كامل ✅" if صاعد_كامل else "متذبذب ⚠️"
        رسالة=(f"⏰ الوقت: {الوقت} - فريم 5 دقائق\n"
               f"🥇 سعر الذهب: {السعر:.2f} دولار [{المصدر}]\n"
               f"📈 المتوسطات: 20={م20:.1f} | 50={م50:.1f} | 100={م100:.1f} | 200@14={م200:.1f} - {حالة}\n"
               f"📊 القوة النسبية: {قوة:.1f} | الماكد: {ماكد:.3f}\n"
               f"📐 فيبو: 0%={فيبو0:.1f} | 25%={فيبو25:.1f} | 50%={فيبو50:.1f} | 100%={فيبو100:.1f}\n"
               f"🚫 لا توجد اشارة حالياً - السعر بعيد عن مناطق فيبو والطلب بأكثر من 2.5 دولار - ننتظر رجوع السعر")
        send(رسالة)

print("تم - رسائل عربية")
