import os, requests
TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {"chat_id": CHAT, "text": "الذهب الان 2685 - البوت شغال تمام يا خالد"}
r = requests.post(url, data=data)
print(r.text)
