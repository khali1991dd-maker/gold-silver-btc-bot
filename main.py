import os, requests
from urllib.parse import quote
import datetime, pytz

MUSCAT = pytz.timezone("Asia/Muscat")
NOW = datetime.datetime.now(MUSCAT)

tok=os.getenv("TG_TOKEN")
chat=os.getenv("TG_CHAT")

def send(m):
    requests.get(f"https://api.telegram.org/bot{tok}/sendMessage?chat_id={chat}&text={quote(m)}&parse_mode=Markdown", timeout=15)

send(f"✅ التجربة شغالة\n⏰ {NOW.strftime('%Y-%m-%d %H:%M')} مسقط\nاذا وصلت هذه يعني السيكرتس صح - المشكلة في yfinance فقط")
