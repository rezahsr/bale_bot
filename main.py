import os
import json
import requests
import gspread
from flask import Flask, request, jsonify
from datetime import datetime # اضافه شد برای تاریخ فاکتور

app = Flask(__name__)

TOKEN = os.environ.get("TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
ADMIN_CHAT_ID = 1262888912 # حتماً آیدی عددی خودت رو اینجا بذار

CREDS = json.loads(os.environ.get("GOOGLE_CREDS"))
SHEET_ID = os.environ.get("SHEET_ID")

# ✨ آیدی استیکر خودت رو اینجا بذار (بدون علامت []
SUCCESS_STICKER_ID = "AgACAgIAAxkBAAI..." 

user_states = {}
logged_in_users = {} 

def get_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    sh = gc.open_by_key(SHEET_ID).sheet1 # شیت اول (کاربران و کالاها)
    return sh

def get_invoice_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.get_worksheet(1) # شیت دوم (فاکتورها)
    except:
        return None

def get_special_codes():
    sheet = get_sheet()
    col_codes = sheet.col_values(10)
    col_msgs = sheet.col_values(11)
    special_data = {}
    for i in range(1, len(col_codes)):
        code = col_codes[i].strip()
        msg = col_msgs[i].strip() if i < len(col_msgs) else ""
        if code and msg:
            special_data[code] = msg
    return special_data

def get_products():
    sheet = get_sheet()
    col_codes = sheet.col_values(5)  
    col_names = sheet.col_values(6)  
    col_prices = sheet.col_values(7) 
    products = {}
    for i in range(1, len(col_codes)):
        code = col_codes[i].strip()
        name = col_names[i].strip() if i < len(col_names) else ""
        price_str = col_prices[i].strip() if i < len(col_prices) else ""
        if code and name and price_str:
            try:
                products[code] = {"name": name, "price": int(price_str)}
            except:
                pass
    return products

# ✨ تابع جدید: افکت تایپ کردن
def send_typing_action(chat_id):
    url = f"{BASE_URL}/sendChatAction"
    payload = {"chat_id": chat_id, "action": "typing"}
    try:
        requests.post(url, json=payload)
    except:
        pass

# ✨ تابع جدید: فرستادن استیکر
def send_sticker(chat_id, file_id):
    url = f"{BASE_URL}/sendSticker"
    payload = {"chat_id": chat_id, "sticker": file_id}
    try:
        requests.post(url, json=payload)
    except:
        pass

def delete_message(chat_id, message_id):
    url = f"{BASE_URL}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    try:
        requests.post(url, json=payload)
    except:
        pass

def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error: {e}")

def fetch_and_send_balance(chat_id, password):
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
            markup = {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_main"}]]}
            send_message(chat_id, f"━━━━━━━━━━━━━━━\n💰 **موجودی حساب شما:**\n🔸 {balance:,} طوس کوین\n━━━━━━━━━━━━━━━", markup)
        else:
            send_message(chat_id, "❌ کاربری با این رمز یافت نشد.")
    except:
        send_message(chat_id, "⚠️ خطا در دریافت اطلاعات.")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        
        # ✨ افکت تایپ کردن وقتی کاربر متنی میفرسته (فوراً اجرا میشه قبل از خوندن شیت)
        send_typing_action(chat_id)
        
        handle_user(chat_id, text)
    elif "callback_query" in data:
        chat_id = data["callback_query"]["from"]["id"]
        callback_data = data["callback_query"]["data"]
        message_id = data["callback_query"]["message"]["message_id"]
        delete_message(chat_id, message_id)
        handle_callback(chat_id, callback_data)
    return jsonify({"ok": True})

def handle_callback(chat_id, data):
    
    if data == "order":
        user_states[chat_id] = {"step": "waiting_for_products"}
        markup = {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_main"}]]}
        send_message(chat_id, "🛒 **ثبت سفارش**\n━━━━━━━━━━━━━━━\nلطفاً کد کالا را ارسال کنید.\n_(مثال: 101 یا 101 103)_\n\n📌 مشاهده کالاها: @tos_kala", markup)
    
    elif data == "balance":
        if chat_id in logged_in_users:
            send_typing_action(chat_id) # ✨ افکت تایپ برای استعلام هم
            fetch_and_send_balance(chat_id, logged_in_users[chat_id])
        else:
            user_states[chat_id] = {"step": "waiting_for_pass_check"}
            markup = {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_main"}]]}
            send_message(chat_id, "🔑 **استعلام موجودی**\n━━━━━━━━━━━━━━━\nلطفاً رمز عبور خود را ارسال کنید:", markup)
            
    elif data == "show_more_menu":
        markup = {
            "inline_keyboard": [
                [{"text": "✍️ نظرات و پیشنهادات", "url": "https://ble.ir/YourCommentID"}], 
                [{"text": "🔄 تبدیل طوس کوین", "callback_data": "outside_purchase"}],
                [{"text": "« بازگشت", "callback_data": "back_to_main"}]
            ]
        }
        send_message(chat_id, "⚙️ **منوی خدمات**", markup)

    elif data == "outside_purchase":
        if chat_id in logged_in_users:
            password = logged_in_users[chat_id]
            user_name = "کاربر"
            try:
                sheet = get_sheet()
                col_passwords = sheet.col_values(1) 
                col_names = sheet.col_values(3)  
                for i in range(1, len(col_passwords)):
                    if str(col_passwords[i].strip()) == password:
                        user_name = col_names[i].strip()
                        break
            except: pass
            
            msg = f"🔄 **تبدیل ارز**\n━━━━━━━━━━━━━━━\n{user_name} عزیز، شما می‌توانید طوس کوین خود را به ارز CP کالاف تبدیل کنید."
            markup = {
                "inline_keyboard": [
                    [{"text": "🔗 ارتباط با @Radis_Market", "url": "https://ble.ir/Radis_Market"}],
                    [{"text": "« بازگشت", "callback_data": "back_to_more"}]
                ]
            }
            send_message(chat_id, msg, markup)
        else:
            send_message(chat_id, "❌ لطفاً ابتدا وارد حساب خود شوید.")

    elif data == "back_to_main":
        show_main_menu(chat_id)
    elif data == "back_to_more":
        handle_callback(chat_id, "show_more_menu")
    elif data == "back_to_products":
        user_states[chat_id] = {"step": "waiting_for_products"}
        markup = {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_main"}]]}
        send_message(chat_id, "🛒 **ثبت سفارش**\n━━━━━━━━━━━━━━━\nلطفاً کد کالا را ارسال کنید.\n_(مثال: 101 یا 101 103)_\n\n📌 مشاهده کالاها: @tos_kala", markup)
    elif data == "back_to_login":
        user_states[chat_id] = {"step": "waiting_for_login"}
        send_message(chat_id, "🔐 **ورود به سیستم**\n━━━━━━━━━━━━━━━\nلطفاً رمز عبور خود را ارسال کنید:")

def handle_user(chat_id, text):
    state = user_states.get(chat_id)

    if text == "/start":
        user_states[chat_id] = {"step": "waiting_for_login"}
        send_message(chat_id, "🔐 **ورود به سیستم**\n━━━━━━━━━━━━━━━\nلطفاً رمز عبور خود را ارسال کنید:")
        return

    if state and state["step"] == "waiting_for_login":
        password = text
        
        special_codes = get_special_codes()
        if password in special_codes:
            del user_states[chat_id] 
            special_msg = special_codes[password]
            markup = {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_login"}]]}
            send_message(chat_id, special_msg, markup)
            return

        try:
            sheet = get_sheet()
            col_passwords = sheet.col_values(1) 
            col_names = sheet.col_values(3)  
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password:
                    user_idx = i
                    break
            
            if user_idx != -1:
                user_name = col_names[user_idx].strip() 
                del user_states[chat_id] 
                logged_in_users[chat_id] = password 
                send_message(chat_id, f"✅ خوش آمدید، {user_name} عزیز")
                show_main_menu(chat_id)
            else:
                send_message(chat_id, "❌ رمز اشتباه است.")
        except:
            send_message(chat_id, "⚠️ خطا در برقراری ارتباط.")
        return

    if state and state["step"] == "waiting_for_products":
        products = get_products() 
        input_codes = text.replace(',', ' ').split()
        
        if not input_codes:
            send_message(chat_id, "⚠️ لطفاً کد محصول را وارد کنید.")
            return

        selected_products = []
        total_price = 0
        
        for code in input_codes:
            if code in products:
                selected_products.append(products[code])
                total_price += products[code]['price']
            else:
                send_message(chat_id, f"❌ کد «{code}» نامعتبر است.")
                return
        
        state["step"] = "waiting_for_pass_buy"
        state["selected_products"] = selected_products
        state["total_price"] = total_price
        
        prod_names = " و ".join([p['name'] for p in selected_products])
        markup = {"inline_keyboard": [[{"text": "« تغییر کالاها", "callback_data": "back_to_products"}]]}
        send_message(chat_id, f"💳 **صورت حساب**\n━━━━━━━━━━━━━━━\n🛍 کالا: {prod_names}\n💎 مبلغ: {total_price:,} طوس کوین\n━━━━━━━━━━━━━━━\n🔐 لطفاً برای تایید نهایی، رمز عبور خود را ارسال کنید:", markup)

    elif state and state["step"] == "waiting_for_pass_buy":
        password = text
        selected_products = state["selected_products"]
        total_price = state["total_price"]
        del user_states[chat_id]
        
        try:
            sheet = get_sheet()
            col_passwords = sheet.col_values(1) 
            col_balances = sheet.col_values(2)
            col_names = sheet.col_values(3)  
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password:
                    user_idx = i
                    break
            
            markup = {"inline_keyboard": [[{"text": "🏠 منوی اصلی", "callback_data": "back_to_main"}]]}
            
            if user_idx == -1:
                send_message(chat_id, "❌ رمز اشتباه بود. سفارش لغو شد.", markup)
                return
                
            balance = int(col_balances[user_idx])
            user_name = col_names[user_idx].strip() 
            
            if balance >= total_price:
                new_balance = balance - total_price
                sheet.update_cell(user_idx + 1, 2, new_balance)
                
                prod_names = "، ".join([p['name'] for p in selected_products])
                
                # ✨ فرستادن استیکر موفقیت
                send_sticker(chat_id, SUCCESS_STICKER_ID)
                
                # ✨ ثبت فاکتور در شیت دوم
                invoice_sheet = get_invoice_sheet()
                if invoice_sheet:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    invoice_sheet.append_row([now, user_name, prod_names, total_price, new_balance])
                
                send_message(chat_id, f"✅ **تراکنش موفق**\n━━━━━━━━━━━━━━━\nمبلغ کسر شده: {total_price:,} طوس کوین\nموجودی جدید: {new_balance:,} طوس کوین", markup)
                
                admin_text = f"🛒 **خرید جدید**\n👤 {user_name}\n📦 {prod_names}\n💰 {total_price:,} طوس کوین کسر شد.\n💎 باقیمانده: {new_balance:,} طوس کوین"
                send_message(ADMIN_CHAT_ID, admin_text)
            else:
                send_message(chat_id, f"❌ **موجودی ناکافی**\n━━━━━━━━━━━━━━━\nموجودی شما: {balance:,} طوس کوین\nمبلغ خرید: {total_price:,} طوس کوین", markup)
        except:
            send_message(chat_id, "⚠️ خطا در پردازش سفارش.")

    elif state and state["step"] == "waiting_for_pass_check":
        password = text
        del user_states[chat_id]
        fetch_and_send_balance(chat_id, password)
            
    else:
        send_message(chat_id, "⚠️ لطفاً از منوی استفاده کنید.")

def show_main_menu(chat_id):
    markup = {
        "inline_keyboard": [
            [{"text": "🛒 ثبت سفارش", "callback_data": "order"}],
            [{"text": "💰 استعلام موجودی", "callback_data": "balance"}],
            [{"text": "⚙️ خدمات بیشتر", "callback_data": "show_more_menu"}]
        ]
    }
    send_message(chat_id, "🏠 **منوی اصلی**\n━━━━━━━━━━━━━━━\nگزینه مورد نظر را انتخاب کنید:", markup)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
