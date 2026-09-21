import os, requests, datetime

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

def get_price():
    try:
        # API الذهب
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r.get('price', 0))
    except:
        return 2685.5

price = get_price()

# وقت مسقط
now = datetime.datetime.now(datetime.timezone.utc)
muscat = now + datetime.timedelta(hours=4)
time_str = muscat.strftime("%d-%m %I:%M %p")

if price > 2720:
    signal = "بيع - قمة"
elif price < 2650:
    signal = "شراء قوي"
elif price < 2670:
    signal = "شراء"
else:
    signal = "انتظار"

text = f"GOLD PRICE\n\nالسعر: {price:.2f} $\nالوقت: {time_str} مسقط\nالتحليل: {signal}\n\nالدعم 2650 - المقاومة 2720\nالبوت يراقب كل 5 دقائق"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, data={"chat_id": CHAT, "text": text})
print(r.text)
