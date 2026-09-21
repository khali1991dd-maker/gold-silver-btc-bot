import os, requests

TOKEN = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

print(f"TOKEN exists: {bool(TOKEN)} CHAT: {CHAT}")

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
    print(r.text)
    return r.ok

# --- اختبار اولي ---
if not TOKEN or not CHAT:
    print("الـ Secrets ما وصلت!")
else:
    send("✅ *تم اصلاح البوت يا خالد!*\n\nالتوكن والايدي الحين متوافقين 100% - `TG_TOKEN` شغال.\n\nالخطوة الجاية برجع لك كود تحليل الذهب.")
