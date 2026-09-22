import os, requests, datetime, yfinance as yf, pandas as pd, time

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

def send(text):
    try: requests.post(TG_URL, data={"chat_id": CHAT, "text": text}, timeout=15)
    except: pass

def get_muscat_time():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)

def is_market_open(m):
    wd=m.weekday(); h=m.hour
    if wd==4 and h>=23: return False
    if wd==5: return False
    if wd==6 and h<1: return False
    return True

def rsi(s, p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(alpha=1/p).mean(); l=-d.clip(upper=0).ewm(alpha=1/p).mean()
    return 100-(100/(1+g/l))

def get_exness_price():
    try:
        r=requests.get("https://api.gold-api.com/price/XAU", timeout=5).json()
        p=float(r.get('price',0))
        if p>1000: return p, "إكسنس مباشر"
    except: pass
    return None, None

مسقط = get_muscat_time()
وقت = مسقط.strftime("%d-%m-%Y %I:%M %p")

if not is_market_open(مسقط):
    send(f"⏰ {وقت}\n🥇 السوق مغلق - إجازة")
else:
    df=yf.download("GC=F", period="30d", interval="5m", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]; h=df["High"]; l=df["Low"]; o=df["Open"]

    # موفنجات: 20/50/100 عند شمعة 0 و 200 عند شمعة 14
    df["م20"]=c.rolling(20).mean()
    df["م50"]=c.rolling(50).mean()
    df["م100"]=c.rolling(100).mean()
    df["م200"]=c.rolling(200).mean().shift(14)

    df["RSI"]=rsi(c,14)
    df["ماكد"]=c.ewm(span=5).mean() - c.ewm(span=20).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean().iloc[-1]

    last=df.iloc[-1]
    السعر, المصدر = get_exness_price()
    if السعر is None: السعر=float(c.iloc[-1]); المصدر="ياهو احتياطي"

    مؤشر_قوة=float(last["RSI"]); ماكد=float(last["ماكد"])

    # فيبو حسب صورتك 0 و 0.25 و 0.5 و 1
    look=50
    قمة=float(h[-look:].max()); قاع=float(l[-look:].min()); فرق=قمة-قاع
    فيبو_25=قمة-فرق*0.25; فيبو_50=قمة-فرق*0.5

    قريب_فيبو = abs(السعر-فيبو_25)<atr*0.7 or abs(السعر-فيبو_50)<atr*0.7

    # بلوك اوردر
    بلوك=""; منطقة=0
    for i in range(-12, -4):
        if o.iloc[i] > c.iloc[i] and (c.iloc[i+1]-o.iloc[i+1]) > atr*0.6:
            منطقة=(o.iloc[i]+c.iloc[i])/2
            if abs(السعر-منطقة) < atr*1.0: بلوك=f"منطقة شراء {منطقة:.1f}"; break
        if o.iloc[i] < c.iloc[i] and (o.iloc[i+1]-c.iloc[i+1]) > atr*0.6:
            منطقة=(o.iloc[i]+c.iloc[i])/2
            if abs(السعر-منطقة) < atr*1.0: بلوك=f"منطقة بيع {منطقة:.1f}"; break

    قريب = قريب_فيبو or (بلوك!="")
    صاعد = last["م20"] > last["م50"] > last["م100"] > last["م200"]
    هابط = last["م20"] < last["م50"] < last["م100"] < last["م200"]

    اشارة=None
    if 30 <= مؤشر_قوة <= 70 and قريب:
        if صاعد and ماكد > 0: اشارة="شراء قوي 🚀"
        elif هابط and ماكد < 0: اشارة="بيع قوي 🔻"

    if اشارة:
        وقف=السعر-atr*2 if "شراء" in اشارة else السعر+atr*2
        ه1=السعر+atr*1.5 if "شراء" in اشارة else السعر-atr*1.5
        ه2=السعر+atr*3 if "شراء" in اشارة else السعر-atr*3
        ه3=السعر+atr*4.5 if "شراء" in اشارة else السعر-atr*4.5
        رسالة=(f"🚀 {اشارة}\n⏰ الوقت {وقت}\n💰 السعر {السعر:.2f} [{المصدر}]\n"
               f"📦 {بلوك if بلوك else f'فيبو {فيبو_50:.1f}'}\n📈 الموفنجات مرتبة\n📉 الماكد {ماكد:.2f} {'فوق الصفر' if ماكد>0 else 'تحت الصفر'}\n📊 القوة {مؤشر_قوة:.1f}\n\n"
               f"الدخول {السعر:.2f}\nالهدف الاول {ه1:.2f}\nالهدف الثاني {ه2:.2f}\nالهدف الثالث {ه3:.2f}\nوقف الخسارة {وقف:.2f}")
        for _ in range(5): send(رسالة); time.sleep(1.5)
    else:
        send(f"⏰ {وقت}\n🥇 الذهب {السعر:.2f} [{المصدر}]\n📈 موفنج 20 {last['م20']:.1f} موفنج 50 {last['م50']:.1f} موفنج 100 {last['م100']:.1f} موفنج 200 {last['م200']:.1f}\n📊 قوة {مؤشر_قوة:.1f} ماكد {ماكد:.2f}\n🚫 لا توجد صفقة الان - انتظر ترتيب الموفنجات\n🤖 البوت يراقب")

print("تم بالعربي")
