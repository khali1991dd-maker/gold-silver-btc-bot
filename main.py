import os, requests
tok=os.getenv("TG_TOKEN")
chat=os.getenv("TG_CHAT")
print(f"TOK len={len(tok) if tok else 0} CHAT={chat}")
r=requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id":chat,"text":"✅ اختبار وصول"}, timeout=10)
print(f"STATUS {r.status_code}")
print(r.text)
