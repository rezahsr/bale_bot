import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ.get("TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

# ⚠️ بسیار مهم: آیدی عددی اکانت خودت رو در بله اینجا بذار
# (برای پیدا کردن آیدیت میتونی به @userinfobot پیام بدی)
ADMIN_CHAT_ID = 1262888912

# اینجا یه دیتابیس ساده (غیرواقعی) برای تست اعتبار ساختیم
# در پروژه‌های واقعی باید از دیتابیس مثل SQLite استفاده کنی
USER_BALANCES = {
    "1234": {"name": "علی", "balance": 150000},
    "0110362330": {"name": "رضا", "balance": 50000}
}

# حافظه موقت ربات برای یادآوری اینکه هر کاربر تو کدوم مرحله هست
user_states = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        
        # دکمه شیشه‌ای که کاربر زده
        callback_data = data["message"].get("data") 

        handle_user(chat_id, text)
        
    # برای وقتی کاربر روی دکمه‌ها کلیک می‌کنه
    elif "callback_query" in data:
        chat_id = data["callback_query"]["from"]["id"]
        callback_data = data["callback_query"]["data"]
        handle_callback(chat_id, callback_data)

    return jsonify({"ok": True})

def handle_callback(chat_id, data):
    if data == "order":
        user_states[chat_id] = {"step": "waiting_for_product"}
        send_message(chat_id, "🛒 لطفاً کد جنس یا نام محصولی که می‌خوای سفارش بدی رو بفرست:")
    
    elif data == "balance":
        user_states[chat_id] = {"step": "waiting_for_password"}
        send_message(chat_id, "🔑 لطفاً رمز کاربری خودت رو بفرست تا اعتبارت رو بگم:")

def handle_user(chat_id, text):
    state = user_states.get(chat_id)

    if text == "/start":
        show_main_menu(chat_id)
        return

    # اگر کاربر تو مرحله ثبت سفارش هست
    if state and state["step"] == "waiting_for_product":
        state["step"] = "waiting_for_name"
        state["product"] = text
        send_message(chat_id, f"✅ محصول «{text}» ثبت شد.\n\n👤 حالا نام و نام خانوادگی خودت رو بفرست:")

    # اگر کاربر تو مرحله گرفتن اسم هست
    elif state and state["step"] == "waiting_for_name":
        product = state["product"]
        customer_name = text
        del user_states[chat_id] # پاک کردن حالت
        
        # فرستادن پیام به ادمین
        admin_text = f"🚨 **سفارش جدید**\n\n👤 نام مشتری: {customer_name}\n📦 محصول درخواستی: {product}"
        send_message(ADMIN_CHAT_ID, admin_text)
        
        send_message(chat_id, "🎉 سفارش شما با موفقیت ثبت شد و به ادمین ارسال شد. به زودی باهات تماس می‌گیریم.")

    # اگر کاربر تو مرحله چک کردن اعتبار هست
    elif state and state["step"] == "waiting_for_password":
        del user_states[chat_id] # پاک کردن حالت
        
        if text in USER_BALANCES:
            user_info = USER_BALANCES[text]
            balance = user_info["balance"]
            send_message(chat_id, f"💰 سلام {user_info['name']} عزیز!\n\nموجودی حساب شما: **{balance:,} تومان** می‌باشد.")
        else:
            send_message(chat_id, "❌ رمز عبور اشتباه است. لطفاً دوباره از منوی اصلی اقدام کنید.")
            
    else:
        send_message(chat_id, "لطفاً از منوی پایین گزینه مورد نظرت رو انتخاب کن.")

def show_main_menu(chat_id):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "سلام! به ربات فروشگاه من خوش اومدی.\nلطفاً یکی از گزینه‌های زیر رو انتخاب کن:",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🛒 ثبت سفارش جدید", "callback_data": "order"}
                ],
                [
                    {"text": "💰 استعلام موجودی/اعتبار", "callback_data": "balance"}
                ]
            ]
        }
    }
    requests.post(url, json=payload)

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
