import os, requests
TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
print(f"TOKEN exists: {bool(TOKEN)} CHAT: {CHAT}")
# رسالة اختبار
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, data={"chat_id": CHAT, "text": "✅ البوت اشتغل والتوكن الجديد شغال 100% - خالد"})
print(r.text)
