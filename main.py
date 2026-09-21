import os, requests

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

print(f"CHAT_ID المستخدم: {CHAT}")

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {"chat_id": CHAT, "text": "تجربة"}
r = requests.post(url, data=data)

print(f"رد تليجرام: {r.text}")
print(f"Status: {r.status_code}")

if r.ok:
    print("تم الارسال")
else:
    print("فشل الارسال - شوف رد تليجرام فوق")
