import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# توکن از تنظیمات رندر خونده میشه
TOKEN = os.environ.get("TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

@app.route('/webhook', methods=['POST'])
def webhook():
    # سرور بله پیام جدید رو اینجا می‌فرسته
    data = request.json
    
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        
        # منطق ربات
        if text == "/start":
            send_message(chat_id, "سلام! من روی سرور رایگان رندر هستم و ۲۴ ساعته روشنم!")
        elif text:
            send_message(chat_id, f"تو گفتی: {text}")
            
    return jsonify({"ok": True})

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

# این خط برای رندر ضروریه تا بدون خطا اجرا بشه
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)