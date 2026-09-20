import os, requests, datetime, pytz, json
from urllib.parse import quote

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)
tok=os.getenv("TG_TOKEN"); chat=os.getenv("TG_CHAT")

def send(m):
    try:
        url=f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m[:3900])}&parse_mode=Markdown"
        requests.get(url, timeout=20)
        print(f"SENT: {m[:50]}")
    except Exception as e:
        print(f"SEND FAIL {e}")

# 1. رسالة تأكيد فورية اول ما يتفعل - عشان تتأكد الحين
send(f"🔔 تم تفعيل البوت بنجاح\n⏰ {NOW.strftime('%Y-%m-%d %H:%M:%S')} مسقط\n📊 الذهب - الفضة - البيتكوين - فريم 5د")

def gold_closed():
    # الذهب يغلق الجمعة 11 مساء ويفتح الاثنين 1 صباحا بتوقيت مسقط
    wd=NOW.weekday(); h=NOW.hour
    if wd==4 and h>=23: return True # الجمعة 11م
    if wd==5: return True # السبت
    if wd==6 and h<1: return True # الاحد الى 1ص
    if wd==0 and h<1: return True # الاثنين قبل 1ص
    return False

try:
    import yfinance as yf, pandas as pd
    def get_df(sym):
        try:
            df=yf.download(sym, period="10d", interval="5m", progress=False, auto_adjust=True)
            if hasattr(df.columns,'get_level_values'):
                try: df.columns=df.columns.get_level_values(0)
                except: pass
            return df.dropna()
        except Exception as e:
            print(f"YF FAIL {sym} {e}")
            return None

    # 2. تنبيه قبل اي خبر بساعة - خبر 4:30 م مسقط
    if NOW.hour==15 and NOW.minute<12: # 15:30 مسقط = قبل الخبر بساعة
        send(f"⚠️ تنبيه خبر مهم جدا\n⏰ الساعة 4:30م مسقط خبر قوي على الذهب والدولار\n🚫 لا تدخل صفقات جديدة قبل الخبر\n📅 {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")

    is_hourly = NOW.minute < 12 # تقرير كل ساعة حتى لو تأخر GitHub
    last_file="/tmp/last_trends.json"
    try:
        with open(last_file,"r") as f: last_trends=json.load(f)
    except: last_trends={}
    new_trends={}

    for sym,name in [("GC=F","الذهب"),("SI=F","الفضة"),("BTC-USD","البيتكوين")]:

        # اغلاق الذهب
        if name!="البيتكوين" and gold_closed():
            if is_hourly:
                send(f"⏸️ {name} مغلق\n📅 {NOW.strftime('%Y-%m-%d %H:%M')} مسقط\nيغلق الجمعة 11م ويفتح الاثنين 1ص")
            continue

        df=get_df(sym)
        if df is None or len(df)<200:
            if is_hourly:
                send(f"⚠️ {name} لا توجد بيانات حاليا - yfinance محظور مؤقتا\n📅 {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")
            continue

        # === المؤشرات المطلوبة ===
        c=df['Close']
        # 1. موفنجات 10/20/30/50/70/100/200
        ma={}
        for p in [10,20,30,50,70,100,200]:
            ma[p]=float(c.rolling(p).mean().iloc[-1])
        ma_prev={}
        for p in [10,20,30,50,70,100]:
            ma_prev[p]=float(c.rolling(p).mean().iloc[-2])
        price_prev=float(c.iloc[-2])

        # 2. ماكد
        ema12=c.ewm(span=12).mean(); ema26=c.ewm(span=26).mean()
        macd_line=ema12-ema26
        macd=float(macd_line.iloc[-1]); sig=float(macd_line.ewm(span=9).mean().iloc[-1])

        # 3. RSI
        delta=c.diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
        rs=gain/loss; rsi=float((100-(100/(1+rs))).iloc[-1])

        # 4. موفنج ترو افرج ATR
        tr=pd.concat([df['High']-df['Low'], (df['High']-c.shift()).abs(), (df['Low']-c.shift()).abs()], axis=1).max(axis=1)
        atr=float(tr.rolling(14).mean().iloc[-1])

        # 5. فيبوناتشي من اخر 100 شمعة
        hi=float(df['High'].rolling(100).max().iloc[-1]); lo=float(df['Low'].rolling(100).min().iloc[-1])
        fib61=hi-(hi-lo)*0.618; fib50=hi-(hi-lo)*0.5; fib78=hi-(hi-lo)*0.786

        # 6. تحليل الشموع اليابانية فريم 5د
        last=df.iloc[-1]
        o=float(last['Open']); cl=float(last['Close']); hh=float(last['High']); ll=float(last['Low'])
        body=abs(cl-o); rng=hh-ll if rng!=0 else 0.001
        upper=hh-max(o,cl); lower=min(o,cl)-ll
        is_doji=body < rng*0.1
        is_hammer = lower > body*2 and upper < body*0.5
        is_shooting = upper > body*2 and lower < body*0.5
        bull_eng = cl>o and body>rng*0.6
        bear_eng = cl<o and body>rng*0.6
        if is_doji: candle="دوجي - تردد"
        elif is_hammer: candle="همر - انعكاس صاعد"
        elif is_shooting: candle="شهاب - انعكاس هابط"
        elif bull_eng: candle="ابتلاعية صاعدة قوية"
        elif bear_eng: candle="ابتلاعية هابطة قوية"
        else: candle="عادية"

        # 7. بلوك اوردر
        block="يوجد بلوك اوردر ✅" if rng>atr*1.8 else "لا يوجد بلوك"

        price=float(c.iloc[-1])

        # تحديد الترند - لازم كل الموفنجات مرتبة
        strong_up = ma[10]>ma[20]>ma[30]>ma[50]>ma[70]>ma[100] and price>ma[10]
        strong_down = ma[10]<ma[20]<ma[30]<ma[50]<ma[70]<ma[100] and price<ma[10]
        trend_type="صاعد قوي مرتب ✅" if strong_up else "هابط قوي مرتب ✅" if strong_down else "عرضي - لا دخول ❌"
        curr_type="صاعد" if strong_up else "هابط" if strong_down else "عرضي"
        new_trends[sym]=curr_type

        # تغيير الترند - يرسل فورا كل 5 دقايق
        if sym in last_trends and last_trends[sym]!=curr_type and curr_type!="عرضي":
            send(f"🔄 تغيير ترند {name}\nمن {last_trends[sym]} الى {curr_type}\n💰 السعر: {price:.2f}\n📅 {NOW.strftime('%Y-%m-%d %H:%M:%S')} مسقط")

        # شروط الدخول - اهم نقطة طلبتها
        # ما يبيع اذا RSI تحت 25 وما يشتري اذا فوق 75 + الشمعة توافق الترند
        candle_buy_ok = bull_eng or is_hammer
        candle_sell_ok = bear_eng or is_shooting

        buy_ok = strong_up and candle_buy_ok and not is_doji and macd>sig and rsi<=75
        sell_ok = strong_down and candle_sell_ok and not is_doji and macd<sig and rsi>=25

        # يرسل كل 5 دقايق اذا فيه صفقة + يرسل كل ساعة تقرير
        if buy_ok or sell_ok or is_hourly:
            if buy_ok or sell_ok:
                action="🟢 شراء" if buy_ok else "🔴 بيع"
                header=f"🚀 ادخل الصفقة الان - {name}"
            else:
                action="🟡 انتظار"
                header=f"📊 تقرير ساعي - {name}"

            msg=f"""{header}
📅 {NOW.strftime('%Y-%m-%d %H:%M:%S')} مسقط
⏱️ فريم: 5 دقايق

💰 السعر الحالي: {price:.2f}
📈 نوع الترند: {trend_type}
{action}

📊 الموفنجات:
MA10={ma[10]:.2f} MA20={ma[20]:.2f} MA30={ma[30]:.2f}
MA50={ma[50]:.2f} MA70={ma[70]:.2f} MA100={ma[100]:.2f} MA200={ma[200]:.2f}

📉 ماكد: {macd:.3f} | اشارة: {sig:.3f}
📊 RSI: {rsi:.1f} {'⚠️ فوق 75 لا شراء' if rsi>75 else '⚠️ تحت 25 لا بيع' if rsi<25 else '✅ مناسب'}
📏 ATR: {atr:.2f}

🔢 فيبوناتشي:
61.8%={fib61:.2f} 50%={fib50:.2f} 78.6%={fib78:.2f}

🕯️ الشموع: {candle}
📦 {block}
"""
            if buy_ok:
                tp1=price+atr*1.0; tp2=price+atr*2.0; tp3=price+atr*3.0; sl=price-atr*1.5
                msg+=f"""
✅ شروط الشراء تحققت:
- ترند صاعد مرتب ✅
- شمعة صاعدة توافق الترند ✅
- MACD فوق الاشارة ✅
- RSI={rsi:.1f} <=75 ✅

🎯 الدخول: {price:.2f}
🎯 هدف1: {tp1:.2f}
🎯 هدف2: {tp2:.2f}
🎯 هدف3: {tp3:.2f}
⛔ وقف الخسارة: {sl:.2f}
"""
            elif sell_ok:
                tp1=price-atr*1.0; tp2=price-atr*2.0; tp3=price-atr*3.0; sl=price+atr*1.5
                msg+=f"""
✅ شروط البيع تحققت:
- ترند هابط مرتب ✅
- شمعة هابطة توافق الترند ✅
- MACD تحت الاشارة ✅
- RSI={rsi:.1f} >=25 ✅

🎯 الدخول: {price:.2f}
🎯 هدف1: {tp1:.2f}
🎯 هدف2: {tp2:.2f}
🎯 هدف3: {tp3:.2f}
⛔ وقف الخسارة: {sl:.2f}
"""
            send(msg)

    with open(last_file,"w") as f: json.dump(new_trends,f)

except Exception as e:
    import traceback
    print(traceback.format_exc())
    send(f"❌ خطأ في البوت: {e}\n📅 {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")
