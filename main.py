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

# خواندن محصولات از ستون‌های E, F, G
def get_products():
    sheet = get_sheet()
    col_codes = sheet.col_values(5)  # ستون E
    col_names = sheet.col_values(6)  # ستون F
    col_prices = sheet.col_values(7) # ستون G
    
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
        send_message(chat_id, "📦 لطفاً کد محصول(های) مورد نظرت رو بفرست:\n(اگر چند تا هست، با فاصله یا کاما جدا کن. مثال: 101 103)")
    
    elif data == "balance":
        user_states[chat_id] = {"step": "waiting_for_pass_check"}
        send_message(chat_id, "🔑 برای مشاهده موجودی طوس کوین کد کاربری خود را وارد کنید:")

def handle_user(chat_id, text):
    state = user_states.get(chat_id)

    if text == "/start":
        show_main_menu(chat_id)
        return

    # مرحله 1: گرفتن کد(های) محصول از کاربر
    if state and state["step"] == "waiting_for_products":
        products = get_products() 
        
        # جایگزینی کاما با فاصله و جدا کردن کدها
        input_codes = text.replace(',', ' ').split()
        
        if not input_codes:
            send_message(chat_id, "❌ لطفاً حداقل یک کد محصول وارد کنید.")
            return

        selected_products = []
        total_price = 0
        
        # بررسی اینکه آیا همه کدها درست هستن یا نه
        for code in input_codes:
            if code in products:
                selected_products.append(products[code])
                total_price += products[code]['price']
            else:
                send_message(chat_id, f"❌ کد محصول «{code}» پیدا نشد. لطفاً دوباره کدهای معتبر رو بفرست:")
                return
        
        # ذخیره اطلاعات در حافظه ربات
        state["step"] = "waiting_for_pass_buy"
        state["selected_products"] = selected_products
        state["total_price"] = total_price
        
        prod_names = " و ".join([p['name'] for p in selected_products])
        send_message(chat_id, f"✅ محصولات «{prod_names}» با مجموع قیمت {total_price:,} طوس کوین انتخاب شد.\n\n🔑 برای تایید خرید و کسر از اعتبار، لطفاً کد کاربری خودت رو بفرست:")

    # مرحله 2: گرفتن رمز برای خرید و کسر طوس کوین
    elif state and state["step"] == "waiting_for_pass_buy":
        password = text
        selected_products = state["selected_products"]
        total_price = state["total_price"]
        del user_states[chat_id]
        
        try:
            sheet = get_sheet()
            
            # خواندن اطلاعات کاربر (ستون A رمز، ستون B موجودی، ستون C نام)
            col_passwords = sheet.col_values(1) 
            col_balances = sheet.col_values(2)
            col_names = sheet.col_values(3)  # خواندن ستون C برای اسم
            
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password:
                    user_idx = i
                    break
            
            if user_idx == -1:
                send_message(chat_id, "❌ رمز عبور اشتباه است.")
                return
                
            balance = int(col_balances[user_idx])
            user_name = col_names[user_idx].strip() # گرفتن اسم کاربر از ستون C
            
            if balance >= total_price:
                new_balance = balance - total_price
                
                # آپدیت کردن موجودی در ستون B
                sheet.update_cell(user_idx + 1, 2, new_balance)
                
                prod_names = "، ".join([p['name'] for p in selected_products])
                send_message(chat_id, f"🎉 خرید موفق!\n محصولات: {prod_names}\n مبلغ کسر شده: {total_price:,} طوس کوین\n موجودی جدید شما: {new_balance:,} طوس کوین")
                
                # پیامی که برای ادمین (شما) فرستاده میشه
                admin_text = f"🛒 خرید جدید:\n👤 نام مشتری: {user_name}\n📦 محصولات: {prod_names}\n💰 مبلغ کل کسر شده: {total_price:,} طوس کوین\n💎 موجودی باقیمانده مشتری: {new_balance:,} طوس کوین"
                send_message(ADMIN_CHAT_ID, admin_text)
            else:
                send_message(chat_id, f"❌ موجودی حساب شما کافی نیست!\n موجودی فعلی: {balance:,} طوس کوین\n مبلغ کل خرید: {total_price:,} طوس کوین")
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
        "text": "به ربات فورشگاه توس کلا خوش اومدی .",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "🛒 خرید محصول", "callback_data": "order"}],
                [{"text": "💰 استعلام اعتبار", "callback_data": "balance"}]
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
