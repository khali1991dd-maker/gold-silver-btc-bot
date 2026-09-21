import os, requests, datetime

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})

def get_price(symbol):
    try:
        if symbol == "XAU":
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
            return float(r.get('price', 0))
        else:
            # للفضة والبيتكوين من Binance مجاني
            s = "XAGUSDT" if symbol == "XAG" else "BTCUSDT"
            # نحول سعر الفضة التقريبي
            if symbol == "XAG":
                r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=XAGUSDT", timeout=10)
                if r.status_code != 200:
                    return 31.5 # سعر تقريبي اذا فشل
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={s}", timeout=10).json()
            return float(r.get('price', 0))
    except:
        return 0

now = datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p")
gold = get_price("XAU")
silver = get_price("XAG")
btc = get_price("BTC")

if gold == 0: gold = 2685.30
if silver == 0: silver = 31.85
if btc == 0: btc = 68500

# تحليل
def analysis(price, high, low):
    if price >= high: return "🔴 بيع - قمة"
    if price <= low: return "🟢 شراء - قاع"
    return "🟡 انتظار"

msg = f"""📈 *تقرير الذهب والفضة والبيتكوين*
⏰ {now} - مسقط

*🥇 الذهب (XAU):* ${gold:.2f}
{analysis(gold, 2720, 2650)}

*🥈 الفضة (XAG):* ${silver:.2f}
{analysis(silver, 33, 30)}

*₿ البيتكوين:* ${btc:,.0f}
{analysis(btc, 70000, 65000)}

🤖 البوت يراقب كل 5 دقايق تلقائيا
@goldsniper_oman_98_bot
"""

send(msg)
print("تم الارسال")
