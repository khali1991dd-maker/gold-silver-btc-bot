import os, requests, datetime, pytz, traceback
from urllib.parse import quote

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)
tok=os.getenv("TG_TOKEN"); chat=os.getenv("TG_CHAT")

def send(m):
    try:
        requests.get(f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m[:3900])}&parse_mode=Markdown", timeout=20)
    except: pass

def main():
    try:
        import yfinance as yf, pandas as pd
    except Exception as e:
        send(f"❌ فشل تحميل yfinance: {e}\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")
        return

    def gold_closed():
        wd=NOW.weekday(); h=NOW.hour
        if wd==4 and h>=23: return True
        if wd==5: return True
        if wd==6 and h<1: return True
        if wd==0 and h<1: return True
        return False

    def get_df(sym):
        try:
            df=yf.download(sym, period="5d", interval="5m", progress=False, auto_adjust=True)
            if hasattr(df.columns,'get_level_values'):
                try: df.columns=df.columns.get_level_values(0)
                except: pass
            return df.dropna()
        except: return None

    # تنبيه خبر 3:30م
    if NOW.hour==15 and NOW.minute<5:
        send(f"⚠️ *تنبيه خبر مهم*\nالساعة 4:30م بتوقيت مسقط خبر قوي\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')}")

    is_hourly = NOW.minute<20 # نوسعها 20 دقيقة عشان ما تفوت

    for sym,name in [("GC=F","الذهب"),("SI=F","الفضة"),("BTC-USD","البيتكوين")]:
        if name!="البيتكوين" and gold_closed():
            if is_hourly:
                send(f"⏸️ {name} مغلق - يفتح اثنين 1ص\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط")
            continue

        df=get_df(sym)
        if df is None or len(df)<200:
            if is_hourly:
                send(f"📊 {name} - لا بيانات كافية {len(df) if df is not None else 0}\n⏰ {NOW.strftime('%H:%M')} مسقط")
            continue

        c=df['Close']; ma={}
        for p in [10,20,30,50,70,100,200]:
            ma[p]=float(c.rolling(p).mean().iloc[-1])
        ema12=c.ewm(span=12).mean(); ema26=c.ewm(span=26).mean()
        macd=float((ema12-ema26).iloc[-1]); sig=float((ema12-ema26).ewm(span=9).mean().iloc[-1])
        delta=c.diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=-delta.where(delta<0,0).rolling(14).mean()
        rsi=float(100-(100/(1+gain/loss)).iloc[-1])
        tr=pd.concat([df['High']-df['Low'], (df['High']-c.shift()).abs(), (df['Low']-c.shift()).abs()], axis=1).max(axis=1)
        atr=float(tr.rolling(14).mean().iloc[-1])
        hi=float(df['High'].rolling(100).max().iloc[-1]); lo=float(df['Low'].rolling(100).min().iloc[-1])
        f61=hi-(hi-lo)*0.61; f78=hi-(hi-lo)*0.78
        last=df.iloc[-1]; body=abs(float(last['Close']-last['Open'])); rng=float(last['High']-last['Low'])
        is_doji=body < rng*0.1
        bull=float(last['Close'])>float(last['Open']) and body>rng*0.6
        bear=float(last['Close'])<float(last['Open']) and body>rng*0.6
        candle="دوجي" if is_doji else "قوية صاعدة" if bull else "قوية هابطة" if bear else "عادية"
        block="يوجد" if rng>atr*1.8 else "لا يوجد"
        price=float(c.iloc[-1])

        # بدون دخول عرضي: 6 موفنجات مرتبة
        strong_up = ma[10]>ma[20]>ma[30]>ma[50]>ma[70]>ma[100] and price>ma[10]
        strong_down = ma[10]<ma[20]<ma[30]<ma[50]<ma[70]<ma[100] and price<ma[10]
        trend_type="صاعد قوي مرتب" if strong_up else "هابط قوي مرتب" if strong_down else "عرضي - لا دخول"

        buy_ok = strong_up and bull and not is_doji and macd>sig and rsi<=75 and price>f61
        sell_ok = strong_down and bear and not is_doji and macd<sig and rsi>=25 and price<f61

        if buy_ok or sell_ok or is_hourly:
            action="🟢 شراء" if buy_ok else "🔴 بيع" if sell_ok else "🟡 انتظار"
            entry=price
            if buy_ok: tp1, tp2, tp3 = entry+atr, entry+atr*2, entry+atr*3; sl=entry-atr*1.5
            elif sell_ok: tp1, tp2, tp3 = entry-atr, entry-atr*2, entry-atr*3; sl=entry+atr*1.5
            else: tp1=tp2=tp3=sl=0

            msg=f"""{'🚀 ادخل الصفقة الان' if buy_ok or sell_ok else '📊 تقرير ساعي'} {name}
⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط
💰 السعر: {price:.2f}
📈 الترند: {trend_type}
{action}
MA10={ma[10]:.1f} MA20={ma[20]:.1f} MA30={ma[30]:.1f}
MA50={ma[50]:.1f} MA70={ma[70]:.1f} MA100={ma[100]:.1f} MA200={ma[200]:.1f}
MACD={macd:.2f} SIG={sig:.2f} RSI={rsi:.1f} ATR={atr:.2f}
فيبو 61%={f61:.1f} 78%={f78:.1f}
شمعة: {candle} بلوك: {block}
"""
            if buy_ok or sell_ok:
                msg+=f"🎯 دخول: {entry:.2f}\nهدف1: {tp1:.2f} هدف2: {tp2:.2f} هدف3: {tp3:.2f}\n⛔ وقف: {sl:.2f}\n"
            send(msg)

try:
    main()
except Exception as e:
    send(f"❌ خطأ:\n{str(e)[:500]}\n{traceback.format_exc()[:1000]}\n⏰ {NOW.strftime('%H:%M')}")
