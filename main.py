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
logged_in_users = {} 

def get_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    sh = gc.open_by_key(SHEET_ID).sheet1
    return sh

def get_special_codes():
    sheet = get_sheet()
    col_codes = sheet.col_values(10) # ستون J
    col_msgs = sheet.col_values(11)  # ستون K
    
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
            send_message(chat_id, f"💰 موجودی حساب شما: **{balance:,} طوس کوین** می‌باشد.")
        else:
            send_message(chat_id, "❌ خطا: حساب کاربری یافت نشد. لطفاً دوباره /start رو بزنید.")
    except Exception as e:
        send_message(chat_id, "خطا در ارتباط با سرور.")
        print(f"Sheet Error Balance: {e}")

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
        user_states[chat_id] = {"step": "waiting_for_products"}
        send_message(chat_id, "📦 لطفاً کد محصول(های) مورد نظرت رو بفرست:\n(اگر چند تا هست، با فاصله یا کاما جدا کن. مثال: 101 103)\n\n📩 کد محصولات در کانال @tos_kala")
    
    elif data == "balance":
        if chat_id in logged_in_users:
            fetch_and_send_balance(chat_id, logged_in_users[chat_id])
        else:
            user_states[chat_id] = {"step": "waiting_for_pass_check"}
            send_message(chat_id, "🔑 لطفاً رمز کاربری خودت رو بفرست تا موجودیت رو بگم:")
            
    elif data == "back_to_login":
        # بازگشت به صفحه لاگین برای کدهای خاص
        user_states[chat_id] = {"step": "waiting_for_login"}
        send_message(chat_id, "👋 لطفاً برای ورود به سیستم، رمز کاربری خودت رو بفرست:")
        
    elif data == "show_more_menu":
        # نمایش منوی اضافه تر
        url = f"{BASE_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "لطفاً یکی از گزینه‌های زیر رو انتخاب کن:",
            "reply_markup": {
                "inline_keyboard": [
                    # دکمه مستقیم (بدون اجرای کد در ربات، مستقیم میره آیدی)
                    [{"text": "✍️ نظرات و پیشنهادات", "url": "https://t.me/@YourCommentID"}], # حتماً این آیدی رو عوض کن
                    
                    # دکمه چنج کردن طوس کوین
                    [{"text": "🔄 خرید خارج از کانال", "callback_data": "outside_purchase"}],
                    
                    # بازگشت
                    [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back_to_main"}]
                ]
            }
        }
        requests.post(url, json=payload)

    elif data == "outside_purchase":
        # ارسال پیام چنج ارز با اسم کاربر
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
            
            msg = f"{user_name} عزیز\n\nشما میتوانید طوس کوین خود را به ارز های رایج :\nCP کالاف مبایل\nچنج کنید.\nبرای چنج و تبادل ارز ها به آیدی زیر پیام بدید:"
            
            url = f"{BASE_URL}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": msg,
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🔗 ارتباط با @Radis_Market", "url": "@Radis_Market"}]
                    ]
                }
            }
            requests.post(url, json=payload)
        else:
            send_message(chat_id, "❌ لطفاً ابتدا وارد حساب کاربری خود شوید.")

    elif data == "back_to_main":
        show_main_menu(chat_id)

def handle_user(chat_id, text):
    state = user_states.get(chat_id)

    if text == "/start":
        user_states[chat_id] = {"step": "waiting_for_login"}
        send_message(chat_id, "👋 سلام! به فروشگاه ما خوش اومدی.\n\n🔑 لطفاً برای ورود، رمز کاربری خودت رو بفرست:")
        return

    if state and state["step"] == "waiting_for_login":
        password = text
        
        # چک کردن کدهای خاص (ستون J)
        special_codes = get_special_codes()
        if password in special_codes:
            del user_states[chat_id] 
            special_msg = special_codes[password]
            
            url = f"{BASE_URL}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": special_msg,
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🔙 بازگشت به منوی ورود", "callback_data": "back_to_login"}]
                    ]
                }
            }
            requests.post(url, json=payload)
            return

        # لاگین عادی مشتری‌ها (ستون A)
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
                send_message(chat_id, f"✅ {user_name} عزیز، سلام! به ربات فروشگاه خوش آمدی.")
                show_main_menu(chat_id)
            else:
                send_message(chat_id, "❌ رمز عبور اشتباه است. لطفاً دوباره تلاش کن:")
        except Exception as e:
            send_message(chat_id, "خطا در ارتباط با سرور.")
            print(f"Sheet Error Login: {e}")
        return

    if state and state["step"] == "waiting_for_products":
        products = get_products() 
        input_codes = text.replace(',', ' ').split()
        
        if not input_codes:
            send_message(chat_id, "❌ لطفاً حداقل یک کد محصول وارد کنید.")
            return

        selected_products = []
        total_price = 0
        
        for code in input_codes:
            if code in products:
                selected_products.append(products[code])
                total_price += products[code]['price']
            else:
                send_message(chat_id, f"❌ کد محصول «{code}» اشتباه است. لطفاً دوباره کدهای معتبر رو بفرست:")
                return
        
        state["step"] = "waiting_for_pass_buy"
        state["selected_products"] = selected_products
        state["total_price"] = total_price
        
        prod_names = " و ".join([p['name'] for p in selected_products])
        send_message(chat_id, f"✅ محصولات «{prod_names}» با مجموع قیمت {total_price:,} طوس کوین انتخاب شد.\n\n🔒 برای حفظ امنیت حساب شما، لطفاً رمز کاربری خودت رو مجدداً وارد کن تا خرید نهایی بشه:")

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
            
            if user_idx == -1:
                send_message(chat_id, "❌ رمز عبور اشتباه است و خرید لغو شد.")
                return
                
            balance = int(col_balances[user_idx])
            user_name = col_names[user_idx].strip() 
            
            if balance >= total_price:
                new_balance = balance - total_price
                sheet.update_cell(user_idx + 1, 2, new_balance)
                
                prod_names = "، ".join([p['name'] for p in selected_products])
                send_message(chat_id, f"🎉 خرید موفق!\n محصولات: {prod_names}\n مبلغ کسر شده: {total_price:,} طوس کوین\n موجودی جدید شما: {new_balance:,} طوس کوین")
                
                admin_text = f"🛒 خرید جدید:\n👤 نام مشتری: {user_name}\n📦 محصولات: {prod_names}\n💰 مبلغ کل کسر شده: {total_price:,} طوس کوین\n💎 موجودی باقیمانده مشتری: {new_balance:,} طوس کوین"
                send_message(ADMIN_CHAT_ID, admin_text)
            else:
                send_message(chat_id, f"❌ موجودی حساب شما کافی نیست!\n موجودی فعلی: {balance:,} طوس کوین\n مبلغ کل خرید: {total_price:,} طوس کوین")
        except Exception as e:
            send_message(chat_id, "خطایی در ارتباط با سرور رخ داد.")
            print(f"Sheet Error Buy: {e}")

    elif state and state["step"] == "waiting_for_pass_check":
        password = text
        del user_states[chat_id]
        fetch_and_send_balance(chat_id, password)
            
    else:
        send_message(chat_id, "لطفاً از منوی اصلی گزینه مورد نظرت رو انتخاب کن.")

def show_main_menu(chat_id):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "لطفاً یکی از گزینه‌های زیر رو انتخاب کن:",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "🛒 خرید محصول", "callback_data": "order"}],
                [{"text": "💰 استعلام اعتبار", "callback_data": "balance"}],
                [{"text": "➕ اضافه تر", "callback_data": "show_more_menu"}] # دکمه جدید
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
