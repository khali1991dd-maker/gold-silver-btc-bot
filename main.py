import os, requests, datetime, pytz, json
from urllib.parse import quote

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)
tok=os.getenv("TG_TOKEN"); chat=os.getenv("TG_CHAT")

def send(m):
    try:
        url=f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m[:3900])}&parse_mode=Markdown"
        requests.get(url, timeout=20)
    except Exception as e:
        print(f"SEND FAIL {e}")

send(f"🔔 تم تفعيل البوت بنجاح\n⏰ {NOW.strftime('%Y-%m-%d %H:%M:%S')} مسقط\n📊 الذهب - الفضة - البيتكوين - فريم 5د")

def gold_closed():
    wd=NOW.weekday(); h=NOW.hour
    if wd==4 and h>=23: return True
    if wd==5: return True
    if wd==6 and h<1: return True
    if wd==0 and h<1: return True
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

    if NOW.hour==15 and NOW.minute<12:
        send(f"⚠️ تنبيه خبر مهم\n⏰ الساعة 4:30م مسقط خبر قوي\n📅 {NOW.strftime('%H:%M')}")

    is_hourly = NOW.minute < 12
    last_file="/tmp/last_trends.json"
    try:
        with open(last_file,"r") as f: last_trends=json.load(f)
    except: last_trends={}
    new_trends={}

    for sym,name in [("GC=F","الذهب"),("SI=F","الفضة"),("BTC-USD","البيتكوين")]:
        if name!="البيتكوين" and gold_closed():
            if is_hourly:
                send(f"⏸️ {name} مغلق - يفتح الاثنين 1ص\n📅 {NOW.strftime('%H:%M')}")
            continue

        df=get_df(sym)
        if df is None or len(df)<200:
            if is_hourly:
                send(f"⚠️ {name} لا توجد بيانات\n📅 {NOW.strftime('%H:%M')}")
            continue

        c=df['Close']
        ma={}
        for p in [10,20,30,50,70,100,200]: ma[p]=float(c.rolling(p).mean().iloc[-1])

        ema12=c.ewm(span=12).mean(); ema26=c.ewm(span=26).mean()
        macd_line=ema12-ema26
        macd=float(macd_line.iloc[-1]); sig=float(macd_line.ewm(span=9).mean().iloc[-1])

        delta=c.diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
        rs=gain/loss; rsi=float((100-(100/(1+rs))).iloc[-1])

        tr=pd.concat([df['High']-df['Low'], (df['High']-c.shift()).abs(), (df['Low']-c.shift()).abs()], axis=1).max(axis=1)
        atr=float(tr.rolling(14).mean().iloc[-1])

        hi=float(df['High'].rolling(100).max().iloc[-1]); lo=float(df['Low'].rolling(100).min().iloc[-1])
        fib61=hi-(hi-lo)*0.618; fib50=hi-(hi-lo)*0.5; fib78=hi-(hi-lo)*0.786

        last=df.iloc[-1]
        o=float(last['Open']); cl=float(last['Close']); hh=float(last['High']); ll=float(last['Low'])
        body=abs(cl-o); rng=hh-ll
        if rng==0: rng=0.001
        upper=hh-max(o,cl); lower=min(o,cl)-ll
        is_doji=body < rng*0.1
        is_hammer = lower > body*2 and upper < body*0.5
        is_shooting = upper > body*2 and lower < body*0.5
        bull_eng = cl>o and body>rng*0.6
        bear_eng = cl<o and body>rng*0.6

        if is_doji: candle="دوجي - تردد"
        elif is_hammer: candle="همر صاعد"
        elif is_shooting: candle="شهاب هابط"
        elif bull_eng: candle="ابتلاعية صاعدة قوية"
        elif bear_eng: candle="ابتلاعية هابطة قوية"
        else: candle="عادية"

        block="يوجد بلوك اوردر ✅" if rng>atr*1.8 else "لا يوجد بلوك"
        price=float(c.iloc[-1])

        strong_up = ma[10]>ma[20]>ma[30]>ma[50]>ma[70]>ma[100] and price>ma[10]
        strong_down = ma[10]<ma[20]<ma[30]<ma[50]<ma[70]<ma[100] and price<ma[10]
        trend_type="صاعد قوي مرتب ✅" if strong_up else "هابط قوي مرتب ✅" if strong_down else "عرضي ❌"
        curr_type="صاعد" if strong_up else "هابط" if strong_down else "عرضي"
        new_trends[sym]=curr_type

        if sym in last_trends and last_trends[sym]!=curr_type and curr_type!="عرضي":
            send(f"🔄 تغيير ترند {name}\nمن {last_trends[sym]} الى {curr_type}\n💰 {price:.2f}\n📅 {NOW.strftime('%H:%M:%S')}")

        buy_ok = strong_up and (bull_eng or is_hammer) and not is_doji and macd>sig and rsi<=75
        sell_ok = strong_down and (bear_eng or is_shooting) and not is_doji and macd<sig and rsi>=25

        if buy_ok or sell_ok or is_hourly:
            header=f"🚀 ادخل الصفقة الان - {name}" if (buy_ok or sell_ok) else f"📊 تقرير ساعي - {name}"
            action="🟢 شراء" if buy_ok else "🔴 بيع" if sell_ok else "🟡 انتظار"
            msg=f"""{header}
📅 {NOW.strftime('%Y-%m-%d %H:%M:%S')} مسقط
⏱️ فريم 5د
💰 السعر: {price:.2f}
📈 الترند: {trend_type}
{action}
MA10={ma[10]:.2f} MA20={ma[20]:.2f} MA30={ma[30]:.2f}
MA50={ma[50]:.2f} MA70={ma[70]:.2f} MA100={ma[100]:.2f} MA200={ma[200]:.2f}
MACD={macd:.3f} SIG={sig:.3f} RSI={rsi:.1f} ATR={atr:.2f}
فيبو 61={fib61:.2f} 50={fib50:.2f} 78={fib78:.2f}
شمعة: {candle} | {block}
"""
            if buy_ok:
                tp1=price+atr; tp2=price+atr*2; tp3=price+atr*3; sl=price-atr*1.5
                msg+=f"🎯 دخول: {price:.2f}\nهدف1: {tp1:.2f} هدف2: {tp2:.2f} هدف3: {tp3:.2f}\n⛔ وقف: {sl:.2f}\n"
            elif sell_ok:
                tp1=price-atr; tp2=price-atr*2; tp3=price-atr*3; sl=price+atr*1.5
                msg+=f"🎯 دخول: {price:.2f}\nهدف1: {tp1:.2f} هدف2: {tp2:.2f} هدف3: {tp3:.2f}\n⛔ وقف: {sl:.2f}\n"
            send(msg)

    with open(last_file,"w") as f: json.dump(new_trends,f)

except Exception as e:
    import traceback
    print(traceback.format_exc())
    send(f"❌ خطأ: {e}\n📅 {NOW.strftime('%H:%M')}")
