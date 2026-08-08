import os
import json
import requests
import gspread
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN = os.environ.get("TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
ADMIN_CHAT_ID = 1262888912 # حتماً آیدی عددی خودت رو اینجا بذار

# اطلاعات گوگل شیت از تنظیمات رندر خونده میشه
CREDS = json.loads(os.environ.get("GOOGLE_CREDS"))
SHEET_ID = os.environ.get("SHEET_ID")

user_states = {}

# اتصال به گوگل شیت
def get_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    sh = gc.open_by_key(SHEET_ID).sheet1
    return sh

# تابع جدید و بسیار سریع برای خواندن فقط ستون‌های محصولات (E, F, G)
def get_products():
    sheet = get_sheet()
    col_codes = sheet.col_values(5)  # ستون E (کد محصول)
    col_names = sheet.col_values(6)  # ستون F (نام محصول)
    col_prices = sheet.col_values(7) # ستون G (قیمت)
    
    products = {}
    for i in range(1, len(col_codes)): # از ردیف 2 به بعد می‌خونه (ردیف 1 عنوان هست)
        code = col_codes[i].strip()
        name = col_names[i].strip() if i < len(col_names) else ""
        price_str = col_prices[i].strip() if i < len(col_prices) else ""
        
        if code and name and price_str:
            try:
                products[code] = {"name": name, "price": int(price_str)}
            except:
                pass
    return products

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        handle_user(chat_id, text)
    elif "callback_query" in data:
        chat_id = data["callback_query"]["from"]["id"]
        callback_data = data["callback_query"]["data"]
        handle_callback(chat_id, callback_data)
    return jsonify({"ok": True})

def handle_callback(chat_id, data):
    if data == "order":
        user_states[chat_id] = {"step": "waiting_for_product"}
        # طبق خواسته شما لیست حذف شد
        send_message(chat_id, "📦 لطفاً کد محصول مورد نظرت رو بفرست:")
    
    elif data == "balance":
        user_states[chat_id] = {"step": "waiting_for_pass_check"}
        send_message(chat_id, "🔑 لطفاً رمز کاربری خودت رو بفرست تا موجودیت رو بگم:")

def handle_user(chat_id, text):
    state = user_states.get(chat_id)

    if text == "/start":
        show_main_menu(chat_id)
        return

    # مرحله 1: گرفتن کد محصول از کاربر
    if state and state["step"] == "waiting_for_product":
        products = get_products() 
        
        if text in products:
            state["step"] = "waiting_for_pass_buy"
            state["product_code"] = text
            prod = products[text]
            send_message(chat_id, f"✅ محصول «{prod['name']}» با قیمت {prod['price']:,} طوس کوین انتخاب شد.\n\n🔑 برای تایید خرید و کسر از اعتبار، لطفاً رمز کاربری خودت رو بفرست:")
        else:
            send_message(chat_id, "❌ کد محصول اشتباهه! لطفاً کد معتبر رو بفرست.")

    # مرحله 2: گرفتن رمز برای خرید و کسر طوس کوین
    elif state and state["step"] == "waiting_for_pass_buy":
        password = text
        product_code = state["product_code"]
        del user_states[chat_id]
        
        try:
            sheet = get_sheet()
            products = get_products()
            
            if product_code not in products:
                send_message(chat_id, "❌ محصول یافت نشد.")
                return
                
            prod = products[product_code]
            
            # خواندن سریع فقط ستون A (رمز) و ستون B (موجودی)
            col_passwords = sheet.col_values(1) 
            col_balances = sheet.col_values(2)
            
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password:
                    user_idx = i
                    break
            
            if user_idx == -1:
                send_message(chat_id, "❌ رمز عبور اشتباه است.")
                return
                
            balance = int(col_balances[user_idx])
            
            if balance >= prod['price']:
                new_balance = balance - prod['price']
                
                # آپدیت کردن موجودی در ستون B (شماره ستون 2)
                # چون لیست‌ها از 0 میشمارن ولی ردیف‌های شیت از 1، پس user_idx + 1
                sheet.update_cell(user_idx + 1, 2, new_balance)
                
                send_message(chat_id, f"🎉 خرید موفق!\n محصول: {prod['name']}\n مبلغ کسر شده: {prod['price']:,} طوس کوین\n موجودی جدید شما: {new_balance:,} طوس کوین")
                
                admin_text = f"🛒 خرید جدید:\nرمز کاربر: {password}\nمحصول: {prod['name']}\nموجودی باقیمانده: {new_balance:,} طوس کوین"
                send_message(ADMIN_CHAT_ID, admin_text)
            else:
                send_message(chat_id, f"❌ موجودی حساب شما کافی نیست!\n موجودی فعلی: {balance:,} طوس کوین\n قیمت محصول: {prod['price']:,} طوس کوین")
        except Exception as e:
            send_message(chat_id, "خطایی در ارتباط با سرور رخ داد.")
            print(f"Sheet Error Buy: {e}")

    # مرحله 3: استعلام اعتبار
    elif state and state["step"] == "waiting_for_pass_check":
        password = text
        del user_states[chat_id]
        try:
            sheet = get_sheet()
            col_passwords = sheet.col_values(1) 
            col_balances = sheet.col_values(2)
            
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password:
                    user_idx = i
                    break
                    
            if user_idx != -1:
                balance = int(col_balances[user_idx])
                send_message(chat_id, f"💰 موجودی حساب شما: **{balance:,} طوس کوین** می‌باشد.")
            else:
                send_message(chat_id, "❌ رمز عبور اشتباه است.")
        except Exception as e:
            send_message(chat_id, "خطا در ارتباط با سرور.")
            print(f"Sheet Error Balance: {e}")
            
    else:
        send_message(chat_id, "لطفاً از منوی اصلی گزینه مورد نظرت رو انتخاب کن.")

def show_main_menu(chat_id):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "سلام! به ربات طوس کالا خوش اومدی.",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "🛒 سفارش محصول", "callback_data": "order"}],
                [{"text": "💰 استعلام طوس کوین", "callback_data": "balance"}]
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
