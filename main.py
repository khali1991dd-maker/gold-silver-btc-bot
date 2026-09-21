import os, requests, datetime

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
    print(f"Telegram: {r.text}")

def get_gold():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r.get('price', 2685))
    except:
        return 2685.0

gold = get_gold()
now = datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=4))).strftime("%d-%m %I:%M %p")

# تحليل بسيط
if gold > 2720:
    sig = "🔴 بيع - السعر في القمة، انتظر نزول"
elif gold < 2650:
    sig = "🟢 شراء قوي - فرصة ممتازة"
elif gold < 2670:
    sig = "🟢 شراء - قريب من القاع"
else:
    sig = "🟡 انتظار - السوق عرضي"

msg = f"""🥇 *الذهب الان - GOLD*

💰 السعر: *${gold:.2f}*
⏰ الوقت: {now} مسقط

📊 التحليل:
{sig}

📍 الدعم: $2650
📍 المقاومة: $2720

🤖 @goldsniper_oman_98_bot
يراقب كل 5 دقائق تلقائيا
"""

send(msg)
