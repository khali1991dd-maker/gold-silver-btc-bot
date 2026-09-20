import os, requests, datetime, pytz, json
from urllib.parse import quote

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)
tok=os.getenv("TG_TOKEN"); chat=os.getenv("TG_CHAT")

def send(m):
    try:
        requests.get(f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m[:3900])}&parse_mode=Markdown", timeout=20)
    except: pass

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
        df=yf.download(sym, period="10d", interval="5m", progress=False, auto_adjust=True)
        if hasattr(df.columns,'get_level_values'):
            try: df.columns=df.columns.get_level_values(0)
            except: pass
        return df.dropna()

    if NOW.hour==15 and NOW.minute<30:
        send(f"⚠️ *تنبيه خبر مهم*\nالساعة 4:30م بتوقيت مسقط خبر قوي\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')}")

    is_hourly = NOW.minute < 5
    last_file="/tmp/last_trends.json"
    try:
        with open(last_file,"r") as f: last_trends=json.load(f)
    except: last_trends={}

    new_trends={}

    for sym,name in [("GC=F","الذهب"),("SI=F","الفضة"),("BTC-USD","البيتكوين")]:
        if name!="البيتكوين" and gold_closed():
            if is_hourly:
                send(f"⏸️ {name} مغلق - يفتح اثنين 1ص\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")
            continue

        df=get_df(sym)
        if df is None or len(df)<200: continue

        c=df['Close']; ma={}
        for p in [10,20,30,50,70,100,200]:
            ma[p]=float(c.rolling(p).mean().iloc[-1])

        # للكشف عن تغيير الترند نحسب الترند السابق
        ma_prev={}
        for p in [10,20,30,50,70,100]:
            ma_prev[p]=float(c.rolling(p).mean().iloc[-2])
        price_prev=float(c.iloc[-2])

        ema12=c.ewm(span=12).mean(); ema26=c.ewm(span=26).mean()
        macd=float((ema12-ema26).iloc[-1]); sig=float((ema12-ema26).ewm(span=9).mean().iloc[-1])
        delta=c.diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
        rsi=float((100-(100/(1+gain/loss))).iloc[-1])
        tr=pd.concat([df['High']-df['Low'], (df['High']-c.shift()).abs(), (df['Low']-c.shift()).abs()], axis=1).max(axis=1)
        atr=float(tr.rolling(14).mean().iloc[-1])
        hi=float(df['High'].rolling(100).max().iloc[-1]); lo=float(df['Low'].rolling(100).min().iloc[-1])
        fib61=hi-(hi-lo)*0.61; fib78=hi-(hi-lo)*0.78
        last=df.iloc[-1]; body=abs(float(last['Close']-last['Open'])); rng=float(last['High']-last['Low'])
        is_doji=body < rng*0.1
        bull=float(last['Close'])>float(last['Open']) and body>rng*0.6
        bear=float(last['Close'])<float(last['Open']) and body>rng*0.6
        candle="دوجي" if is_doji else "قوية صاعدة" if bull else "قوية هابطة" if bear else "عادية"
        block="يوجد بلوك" if rng>atr*1.8 else "لا يوجد"
        price=float(c.iloc[-1])

        strong_up = ma[10]>ma[20]>ma[30]>ma[50]>ma[70]>ma[100] and price>ma[10]
        strong_down = ma[10]<ma[20]<ma[30]<ma[50]<ma[70]<ma[100] and price<ma[10]
        trend_type="صاعد قوي مرتب ✅" if strong_up else "هابط قوي مرتب ✅" if strong_down else "عرضي - لا دخول ❌"

        # كشف تغيير الترند
        prev_up = ma_prev[10]>ma_prev[20]>ma_prev[30]>ma_prev[50]>ma_prev[70]>ma_prev[100] and price_prev>ma_prev[10]
        prev_down = ma_prev[10]<ma_prev[20]<ma_prev[30]<ma_prev[50]<ma_prev[70]<ma_prev[100] and price_prev<ma_prev[10]
        prev_type="صاعد" if prev_up else "هابط" if prev_down else "عرضي"
        curr_type="صاعد" if strong_up else "هابط" if strong_down else "عرضي"

        new_trends[sym]=curr_type
        if sym in last_trends and last_trends[sym]!=curr_type and curr_type!="عرضي":
            send(f"🔄 *تغيير ترند* {name}\nمن {last_trends[sym]} الى {curr_type}\n💰 {price:.2f}\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")

        buy_ok = strong_up and bull and not is_doji and macd>sig and rsi<=75
        sell_ok = strong_down and bear and not is_doji and macd<sig and rsi>=25

        if buy_ok or sell_ok or is_hourly:
            action="🟢 شراء" if buy_ok else "🔴 بيع" if sell_ok else "🟡 انتظار"
            if buy_ok: tp1, tp2, tp3 = price+atr, price+atr*2, price+atr*3; sl=price-atr*1.5; entry=price
            elif sell_ok: tp1, tp2, tp3 = price-atr, price-atr*2, price-atr*3; sl=price+atr*1.5; entry=price
            else: tp1=tp2=tp3=sl=entry=0
            msg=f"""{'🚀 ادخل الصفقة الان' if buy_ok or sell_ok else '📊 تقرير ساعي'} {name}
⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط
💰 السعر الحالي: {price:.2f}
📈 نوع الترند: {trend_type}
{action}
MA10={ma[10]:.1f} MA20={ma[20]:.1f} MA30={ma[30]:.1f}
MA50={ma[50]:.1f} MA70={ma[70]:.1f} MA100={ma[100]:.1f} MA200={ma[200]:.1f}
MACD={macd:.2f} SIG={sig:.2f} RSI={rsi:.1f} ATR={atr:.2f}
فيبو 61%={fib61:.1f} 78%={fib78:.1f}
شمعة: {candle} {block}
"""
            if buy_ok or sell_ok:
                msg+=f"🎯 دخول: {entry:.2f}\nهدف1: {tp1:.2f} هدف2: {tp2:.2f} هدف3: {tp3:.2f}\n⛔ وقف: {sl:.2f}\n"
            send(msg)

    with open(last_file,"w") as f: json.dump(new_trends,f)

except Exception as e:
    import traceback
    send(f"❌ خطأ: {e}\n⏰ {NOW.strftime('%H:%M')}")
