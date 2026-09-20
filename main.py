import os, requests, datetime, pytz, json
from urllib.parse import quote

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)
tok=os.getenv("TG_TOKEN"); chat=os.getenv("TG_CHAT")

print(f"TOKEN exists: {bool(tok)} CHAT exists: {bool(chat)}")
print(f"TIME MUSCAT: {NOW}")

def send(m):
    try:
        if not tok or not chat:
            print("ERROR: TOKEN or CHAT empty")
            return
        url=f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m[:3900])}&parse_mode=Markdown"
        r=requests.get(url, timeout=20)
        print(f"TELEGRAM RESPONSE: {r.status_code} {r.text[:300]}")
    except Exception as e:
        print(f"SEND ERROR: {e}")

# رسالة اختبار فورية
send(f"✅ تجربة البوت شغال\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط\nاذا وصلك هذا يعني التوكن والايدي صح")

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

    is_hourly = NOW.minute < 10
    for sym,name in [("GC=F","الذهب"),("SI=F","الفضة"),("BTC-USD","البيتكوين")]:
        if name!="البيتكوين" and gold_closed(): continue
        df=get_df(sym)
        if df is None or len(df)<200:
            print(f"{name} no data")
            continue
        c=df['Close']; ma={}
        for p in [10,20,30,50,70,100,200]: ma[p]=float(c.rolling(p).mean().iloc[-1])
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
        buy_ok = strong_up and bull and not is_doji and macd>sig and rsi<=75
        sell_ok = strong_down and bear and not is_doji and macd<sig and rsi>=25
        if buy_ok or sell_ok or is_hourly:
            action="🟢 شراء" if buy_ok else "🔴 بيع" if sell_ok else "🟡 انتظار"
            msg=f"{'🚀 ادخل الصفقة الان' if buy_ok or sell_ok else '📊 تقرير ساعي'} {name}\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط\n💰 السعر: {price:.2f}\n📈 {trend_type}\n{action}\nMA10={ma[10]:.1f} MA20={ma[20]:.1f} MA30={ma[30]:.1f}\nMA50={ma[50]:.1f} MA70={ma[70]:.1f} MA100={ma[100]:.1f} MA200={ma[200]:.1f}\nMACD={macd:.2f} SIG={sig:.2f} RSI={rsi:.1f} ATR={atr:.2f}\nفيبو 61={fib61:.1f} 78={fib78:.1f}\nشمعة: {candle} {block}\n"
            send(msg)
except Exception as e:
    import traceback
    print(traceback.format_exc())
    send(f"❌ خطأ: {e}")
