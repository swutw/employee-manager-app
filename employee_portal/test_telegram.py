import requests

bot_token = "8000858451:AAHhU8v23NgsfR3t_zsYVjLjuXDmskm--c0"
chat_id = "7321860394"
message = "這是來自 Python 的測試訊息 ✅"

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
data = {
    "chat_id": chat_id,
    "text": message
}

response = requests.post(url, data=data)
print(response.status_code)
print(response.text)

