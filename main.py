import yfinance as yf, pandas as pd, requests, os, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(text):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": text, "parse_mode":"Markdown"})

def تحليل(symbol):
    df = yf.Ticker(symbol).history(period="10d", interval="5m", prepost=True)
    if len(df) < 200: return None
    close, high, low = df['Close'], df['High'], df['Low']
    ma = {n: close.rolling(n).mean().iloc[-1] for n in [10,20,30,50,70,100,200]}
    ema12, ema26 = close.ewm(12).mean(), close.ewm(26).mean()
    macd_val = (ema12-ema26).iloc[-1]
    sig_val = (ema12-ema26).ewm(9).mean().iloc[-1]
    delta = close.diff()
    rsi = 100 - (100/(1+delta.where(delta>0,0).rolling(14).mean()/-delta.where(delta<0,0).rolling(14).mean())).iloc[-1]
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    h100, l100 = high.tail(100).max(), low.tail(100).min()
    fib618 = h100 - (h100-l100)*0.618
    price = close.iloc[-1]

    if ma[10]>ma[20]>ma[30]>ma[50]>ma[70]>ma[100] and price>ma[10] and macd_val>sig_val and rsi<=75:
        return {"price":price,"rsi":rsi,"atr":atr,"fib":fib618,"trend":"صاعد قوي","action":"شراء"}
    elif ma[10]<ma[20]<ma[30]<ma[50]<ma[70]<ma[100] and price<ma[10] and macd_val<sig_val and rsi>=25:
        return {"price":price,"rsi":rsi,"atr":atr,"fib":fib618,"trend":"هابط قوي","action":"بيع"}
    else:
        return {"price":price,"rsi":rsi,"atr":atr,"fib":fib618,"trend":"عرضي","action":"لا دخول"}

tz = pytz.timezone("Asia/Muscat")
now = datetime.now(tz)

for name,sym in [("الذهب","GC=F"),("الفضة","SI=F"),("البيتكوين","BTC-USD")]:
    r = تحليل(sym)
    if not r: continue

    if r['action']!="لا دخول":
        entry=r['price']
        if r['action']=="شراء":
            tp1,tp2,tp3=entry+r['atr'],entry+r['atr']*2,entry+r['atr']*3
            sl=entry-r['atr']*1.5
        else:
            tp1,tp2,tp3=entry-r['atr'],entry-r['atr']*2,entry-r['atr']*3
            sl=entry+r['atr']*1.5
        send(f"🚀 ادخل الصفقة الان - {name}\nالسعر العالمي: {entry:.2f}\n{now.strftime('%I:%M %p')} مسقط\nالترند: {r['trend']} | {r['action']}\nدخول:{entry:.2f} هدف1:{tp1:.2f} هدف2:{tp2:.2f} هدف3:{tp3:.2f} وقف:{sl:.2f}\nRSI:{r['rsi']:.0f} فيبو:{r['fib']:.1f}")

    if now.minute % 15 < 5:
        if r['action']=="لا دخول":
            send(f"⏸️ {name} عرضي - لا دخول\nالسعر: {r['price']:.2f} | RSI:{r['rsi']:.0f}\n⏰ {now.strftime('%I:%M %p')}")
        else:
            send(f"📊 تقرير 15د - {name}\nالسعر: {r['price']:.2f}\nالترند: {r['trend']} - {r['action']}\n⏰ {now.strftime('%I:%M %p')}")
