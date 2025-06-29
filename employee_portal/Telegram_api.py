import requests

TELEGRAM_BOT_TOKEN = "8000858451:AAHhU8v23NgsfR3t_zsYVjLjuXDmskm--c0"
url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

resp = requests.get(url)
print(resp.json())

