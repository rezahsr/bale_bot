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

# تابع جدید: خواندن محصولات از ستون های E, F, G
def get_products():
    sheet = get_sheet()
    data = sheet.get_all_values()
    if not data:
        return {}
        
    products = {}
    headers = data[0]
    
    try:
        # پیدا کردن شماره ستون ها بر اساس اسمی که تو ردیف اول نوشتی
        code_idx = headers.index('code')
        name_idx = headers.index('name')
        price_idx = headers.index('price')
    except ValueError:
        print("Error: ستون‌های code, name یا price در شیت پیدا نشد.")
        return {}
        
    # خواندن ردیف‌های بعدی و تبدیل به دیکشنری
    for row in data[1:]:
        if len(row) > max(code_idx, name_idx, price_idx):
            code = row[code_idx].strip()
            name = row[name_idx].strip()
            price_str = row[price_idx].strip()
            
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
        
        # گرفتن لیست محصولات از گوگل شیت
        products = get_products()
        if not products:
            send_message(chat_id, "❌ خطا در خواندن لیست محصولات. لطفاً دوباره تلاش کنید.")
            return
            
        product_list = "📦 لیست محصولات:\n\n"
        for code, info in products.items():
            product_list += f"کد {code}: {info['name']} (قیمت: {info['price']:,} تومان)\n"
        product_list += "\nلطفاً کد محصول مورد نظرت رو بفرست:"
        send_message(chat_id, product_list)
    
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
        products = get_products() # هر بار از شیت آپدیت می‌خونه
        
        if text in products:
            state["step"] = "waiting_for_pass_buy"
            state["product_code"] = text
            prod = products[text]
            send_message(chat_id, f"✅ محصول «{prod['name']}» با قیمت {prod['price']:,} تومان انتخاب شد.\n\n🔑 برای تایید خرید و کسر از اعتبار، لطفاً رمز کاربری خودت رو بفرست:")
        else:
            send_message(chat_id, "❌ کد محصول اشتباهه! لطفاً از لیست بالا یه کد معتبر بفرست.")

    # مرحله 2: گرفتن رمز برای خرید و کسر پول
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
            records = sheet.get_all_records()
            user_record = next((r for r in records if str(r['password']) == password), None)
            
            if not user_record:
                send_message(chat_id, "❌ رمز عبور اشتباه است.")
                return
                
            balance = int(user_record['balance'])
            
            if balance >= prod['price']:
                # کسر پول از موجودی
                new_balance = balance - prod['price']
                
                # پیدا کردن سلول رمز و آپدیت کردن ستون balance (ستون 2)
                cell = sheet.find(str(password))
                sheet.update_cell(cell.row, 2, new_balance)
                
                send_message(chat_id, f"🎉 خرید موفق!\n محصول: {prod['name']}\n مبلغ کسر شده: {prod['price']:,} تومان\n موجودی جدید شما: {new_balance:,} تومان")
                
                admin_text = f"🛒 خرید جدید:\nرمز کاربر: {password}\nمحصول: {prod['name']}\nموجودی باقیمانده: {new_balance:,}"
                send_message(ADMIN_CHAT_ID, admin_text)
            else:
                send_message(chat_id, f"❌ موجودی حساب شما کافی نیست!\n موجودی فعلی: {balance:,} تومان\n قیمت محصول: {prod['price']:,} تومان")
        except Exception as e:
            send_message(chat_id, "خطایی در ارتباط با سرور رخ داد.")
            print(f"Sheet Error Buy: {e}")

    # مرحله 3: استعلام اعتبار
    elif state and state["step"] == "waiting_for_pass_check":
        password = text
        del user_states[chat_id]
        try:
            sheet = get_sheet()
            records = sheet.get_all_records()
            user_record = next((r for r in records if str(r['password']) == password), None)
            
            if user_record:
                balance = int(user_record['balance'])
                send_message(chat_id, f"💰 موجودی حساب شما: **{balance:,} تومان** می‌باشد.")
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
        "text": "سلام! به ربات فروشگاه خوش اومدی.",
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
