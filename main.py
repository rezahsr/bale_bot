آها متوجه شدم! عذرخواهی می‌کنم اشتباه متوجه شدم. 

یعنی میخوای:
1. وقتی **عضو (مشتری)** اضافه میشه، رمزش بیاد تو سلول **O9** شیت اصلی.
2. وقتی **ادمین** اضافه میشه، دستی به O9 نزنه و فقط بره تو همون شیت `admins` (پنل ادمین‌ها) ثبت بشه.

من دقیقاً همین دو تا بخش رو اصلاح کردم. بقیه کدها کاملاً دست‌نخورده باقی مونده.

کد کامل رو بذارم که راحت جایگزین کنی:

```python
import os
import json
import requests
import gspread
from flask import Flask, request, jsonify
from datetime import datetime 

app = Flask(__name__)

TOKEN = os.environ.get("TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
ADMIN_CHAT_ID = 1262888912 # آیدی عددی خودت

CREDS = json.loads(os.environ.get("GOOGLE_CREDS"))
SHEET_ID = os.environ.get("SHEET_ID")

SUCCESS_STICKER_ID = "CAACAgUAAxkBAAMFZmuCVTGnOOJgu5Yw_y-UG4TK4yl4AAtkSAAJn_0FLYrrMKpPVrsNIy4E" 

user_states = {}
logged_in_users = {} 

def get_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    return gc.open_by_key(SHEET_ID).sheet1

def get_invoice_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    try: return gc.open_by_key(SHEET_ID).get_worksheet(1)
    except: return None

def get_deduction_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    try: return gc.open_by_key(SHEET_ID).worksheet("کسریات")
    except: return None

def get_admins_sheet():
    gc = gspread.service_account_from_dict(CREDS)
    try: return gc.open_by_key(SHEET_ID).worksheet("admins")
    except: return None

def get_first_empty_row(sheet, col=1):
    col_vals = sheet.col_values(col)
    for i, val in enumerate(col_vals, start=1):
        if not val or not str(val).strip():
            return i
    return len(col_vals) + 1

def get_special_codes():
    sheet = get_sheet()
    col_codes, col_msgs = sheet.col_values(10), sheet.col_values(11)
    return {col_codes[i].strip(): col_msgs[i].strip() for i in range(1, len(col_codes)) if col_codes[i].strip() and i < len(col_msgs)}

def get_products():
    sheet = get_sheet()
    col_codes, col_names, col_prices = sheet.col_values(5), sheet.col_values(6), sheet.col_values(7)
    products = {}
    for i in range(1, len(col_codes)):
        code, name, price_str = col_codes[i].strip(), (col_names[i].strip() if i < len(col_names) else ""), (col_prices[i].strip() if i < len(col_prices) else "")
        if code and name and price_str:
            try: products[code] = {"name": name, "price": int(price_str)}
            except: pass
    return products

def send_typing_action(chat_id):
    try: requests.post(f"{BASE_URL}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
    except: pass

def send_sticker(chat_id, file_id):
    try: requests.post(f"{BASE_URL}/sendSticker", json={"chat_id": chat_id, "sticker": file_id})
    except: pass

def delete_message(chat_id, message_id):
    try: requests.post(f"{BASE_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})
    except: pass

def answer_callback_query(callback_query_id):
    try: requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": callback_query_id})
    except: pass

def send_message(chat_id, text, reply_markup=None):
    try:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup: payload["reply_markup"] = reply_markup
        requests.post(f"{BASE_URL}/sendMessage", json=payload)
    except Exception as e: print(f"Error: {e}")

def check_perm(chat_id, required_role):
    if chat_id not in logged_in_users: return False
    user_data = logged_in_users[chat_id]
    if isinstance(user_data, str): return False
    role = user_data.get('role', 'user')
    if required_role == 'god': return role == 'god'
    if required_role == 'vip': return role in ['god', 'vip']
    if required_role == 'admin': return role in ['god', 'vip', 'admin']
    return True

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        send_typing_action(chat_id)
        handle_user(chat_id, text)
    elif "callback_query" in data:
        chat_id = data["callback_query"]["from"]["id"]
        callback_data = data["callback_query"]["data"]
        message_id = data["callback_query"]["message"]["message_id"]
        callback_query_id = data["callback_query"]["id"] 
        delete_message(chat_id, message_id)
        answer_callback_query(callback_query_id)
        handle_callback(chat_id, callback_data)
    return jsonify({"ok": True})

def handle_callback(chat_id, data):
    back_btn = [{"text": "« بازگشت به منوی ادمین", "callback_data": "adm_menu"}]
    
    if data == "adm_menu":
        if not check_perm(chat_id, 'admin'): return show_main_menu(chat_id)
        rows = [
            [{"text": "👤 اضافه/حذف عضو", "callback_data": "adm_mem_menu"}],
            [{"text": "⚙️ خدمات بیشتر", "callback_data": "adm_ser_menu"}],
            [{"text": "🛡️ اضافه/حذف ادمین", "callback_data": "adm_adm_menu"}],
            [{"text": "🎁 جوایز", "callback_data": "adm_prize_menu"}],
        ]
        if check_perm(chat_id, 'vip'):
            rows.append([{"text": "📊 اطلاعات کاربران", "callback_data": "adm_info"}])
        rows.append([{"text": "🚪 خروج از ادمین", "callback_data": "adm_logout"}])
        send_message(chat_id, "🔐 **پنل مدیریت**\n━━━━━━━━━━━━━━━", {"inline_keyboard": rows})

    elif data == "adm_logout":
        if chat_id in logged_in_users: del logged_in_users[chat_id]
        if chat_id in user_states: del user_states[chat_id]
        send_message(chat_id, "✅ با موفقیت خارج شدید.")

    elif data == "adm_mem_menu":
        markup = {"inline_keyboard": [[{"text": "➕ اضافه کردن عضو", "callback_data": "adm_mem_add_start"}], [{"text": "➖ حذف کردن عضو", "callback_data": "adm_mem_del_start"}], back_btn]}
        send_message(chat_id, "👤 **مدیریت اعضا**", markup)
        
    elif data == "adm_mem_add_start":
        user_states[chat_id] = {"step": "adm_add_name"}
        send_message(chat_id, "لطفا یک نام کوتاه برای کاربر انتخاب کنید (برای نمایش در ربات):")

    elif data == "adm_mem_del_start":
        sheet = get_sheet()
        names = sheet.col_values(4)
        if len(names) <= 1:
            send_message(chat_id, "❌ هیچ عضوی برای حذف وجود ندارد.", {"inline_keyboard": [back_btn]})
            return
        text_list = "📋 **لیست کاربران:**\n━━━━━━━━━━━━━━━\n"
        for i in range(1, len(names)):
            if names[i].strip(): text_list += f"{i}_ {names[i].strip()}\n"
        text_list += "\n⚠️ عدد کنار کاربر را برای حذف ارسال کنید:"
        user_states[chat_id] = {"step": "adm_del_sel", "max_idx": len(names)-1}
        send_message(chat_id, text_list, {"inline_keyboard": [back_btn]})

    elif data == "adm_ser_menu":
        markup = {"inline_keyboard": [[{"text": "💸 کسر طوس کوین", "callback_data": "adm_ser_deduct_start"}], back_btn]}
        send_message(chat_id, "⚙️ **خدمات بیشتر**", markup)
        
    elif data == "adm_ser_deduct_start":
        user_states[chat_id] = {"step": "adm_deduct_pass"}
        send_message(chat_id, "لطفا کد کاربری (رمز عبور) عضو را وارد کنید:", {"inline_keyboard": [back_btn]})

    elif data == "adm_adm_menu":
        is_vip = check_perm(chat_id, 'vip')
        rows = [[{"text": "➕ اضافه کردن ادمین", "callback_data": "adm_adm_add_start"}]]
        if is_vip: rows.append([{"text": "➖ حذف کردن ادمین", "callback_data": "adm_adm_del_start"}])
        rows.append(back_btn)
        send_message(chat_id, "🛡️ **مدیریت ادمین‌ها**", {"inline_keyboard": rows})

    elif data == "adm_adm_add_start":
        user_states[chat_id] = {"step": "adm_add_adm_fullname"}
        send_message(chat_id, "لطفا نام و نام خانوادگی ادمین جدید را بنویسید:")

    elif data == "adm_adm_del_start":
        if not check_perm(chat_id, 'vip'):
            return send_message(chat_id, "❌ فقط ادمین‌های ویژه اجازه حذف ادمین را دارند.", {"inline_keyboard": [back_btn]})
        adm_sheet = get_admins_sheet()
        if not adm_sheet: return send_message(chat_id, "❌ خطا در پیدا کردن شیت ادمین‌ها.")
        adm_passes = adm_sheet.col_values(1)
        adm_names = adm_sheet.col_values(2)
        adm_vips = adm_sheet.col_values(3)
        if len(adm_passes) <= 1: return send_message(chat_id, "❌ هیچ ادمینی وجود ندارد.", {"inline_keyboard": [back_btn]})
        text_list = "📋 **لیست ادمین‌ها:**\n━━━━━━━━━━━━━━━\n"
        for i in range(1, len(adm_passes)):
            if adm_passes[i].strip():
                vip_tag = " [VIP]" if i < len(adm_vips) and str(adm_vips[i].strip()).lower() == 'yes' else ""
                text_list += f"{i}_ {adm_names[i].strip() if i < len(adm_names) else 'نامشخص'}{vip_tag}\n"
        text_list += "\n⚠️ عدد کنار ادمین را برای حذف ارسال کنید:"
        user_states[chat_id] = {"step": "adm_del_adm_sel", "max_idx": len(adm_passes)-1}
        send_message(chat_id, text_list, {"inline_keyboard": [back_btn]})

    elif data == "adm_prize_menu":
        markup = {"inline_keyboard": [[{"text": "➕ اضافه کردن جایزه", "callback_data": "adm_prize_add_name"}], [{"text": "✏️ ویرایش جایزه", "callback_data": "adm_prize_edit_code"}], back_btn]}
        send_message(chat_id, "🎁 **مدیریت جوایز**", markup)
        
    elif data == "adm_prize_add_name":
        user_states[chat_id] = {"step": "adm_prize_name"}
        send_message(chat_id, "لطفا اسم جایزه را بنویسید:")

    elif data == "adm_prize_edit_code":
        user_states[chat_id] = {"step": "adm_prize_get_code"}
        send_message(chat_id, "لطفا کد کالای جایزه را بنویسید:", {"inline_keyboard": [back_btn]})

    elif data == "adm_info":
        if not check_perm(chat_id, 'vip'): return
        sheet = get_sheet()
        passes, names_short, names_full, balances = sheet.col_values(1), sheet.col_values(3), sheet.col_values(4), sheet.col_values(2)
        msg = "📊 **اطلاعات کاربران سیستم:**\n━━━━━━━━━━━━━━━\n"
        for i in range(1, len(passes)):
            if passes[i].strip():
                bal = int(float(balances[i])) if i < len(balances) and balances[i].strip() else 0
                msg += f"🔹 **{names_full[i].strip() if i < len(names_full) and names_full[i].strip() else 'نامشخص'}**\n   رمز: `{passes[i].strip()}` | موجودی: {bal:,}\n\n"
        send_message(chat_id, msg, {"inline_keyboard": [back_btn]})

    elif data == "back_to_main": show_main_menu(chat_id)
    elif data == "back_to_more": handle_callback(chat_id, "show_more_menu")
    elif data == "back_to_products": user_states[chat_id] = {"step": "waiting_for_products"}; send_message(chat_id, "🛒 لطفاً کد کالا را ارسال کنید:")
    elif data == "back_to_login": user_states[chat_id] = {"step": "waiting_for_login"}; send_message(chat_id, "🔐 لطفاً رمز عبور خود را ارسال کنید:")

    elif data == "order":
        user_states[chat_id] = {"step": "waiting_for_products"}
        send_message(chat_id, "🛒 **ثبت سفارش**\n━━━━━━━━━━━━━━━\nلطفاً کد کالا را ارسال کنید.\n_(مثال: 101 یا 101 103)_\n\n📌 مشاهده کالاها: @tos_kala", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_main"}]]})
    elif data == "balance":
        if chat_id in logged_in_users and logged_in_users[chat_id]['role'] == 'user':
            send_typing_action(chat_id)
            fetch_and_send_balance(chat_id, logged_in_users[chat_id]['pass'])
        else:
            user_states[chat_id] = {"step": "waiting_for_pass_check"}
            send_message(chat_id, "🔑 **استعلام موجودی**\n━━━━━━━━━━━━━━━\nلطفاً رمز عبور خود را ارسال کنید:")
    elif data == "show_more_menu":
        markup = {"inline_keyboard": [[{"text": "✍️ نظرات و پیشنهادات", "url": "https://ble.ir/YourCommentID"}], [{"text": "🔄 تبدیل طوس کوین", "callback_data": "outside_purchase"}], [{"text": "« بازگشت", "callback_data": "back_to_main"}]]}
        send_message(chat_id, "⚙️ **منوی خدمات**", markup)
    elif data == "outside_purchase":
        if chat_id in logged_in_users:
            password = logged_in_users[chat_id]['pass']
            user_name = "کاربر"
            try:
                sheet = get_sheet(); col_p, col_n = sheet.col_values(1), sheet.col_values(3)
                for i in range(1, len(col_p)):
                    if str(col_p[i].strip()) == password: user_name = col_n[i].strip(); break
            except: pass
            msg = f"🔄 **تبدیل ارز**\n━━━━━━━━━━━━━━━\n{user_name} عزیز، شما می‌توانید طوس کوین خود را به ارز CP کالاف تبدیل کنید."
            send_message(chat_id, msg, {"inline_keyboard": [[{"text": "🔗 ارتباط با @Radis_Market", "url": "https://ble.ir/Radis_Market"}], [{"text": "« بازگشت", "callback_data": "back_to_more"}]]})
        else: send_message(chat_id, "❌ لطفاً ابتدا وارد حساب خود شوید.")

def handle_user(chat_id, text):
    state = user_states.get(chat_id)

    if text == "/start":
        user_states[chat_id] = {"step": "waiting_for_login"}
        send_message(chat_id, "🔐 **ورود به سیستم**\n━━━━━━━━━━━━━━━\nلطفاً رمز عبور خود را ارسال کنید:")
        return

    if state and state["step"] == "waiting_for_login":
        password = text.strip()
        sheet = get_sheet()
        
        god_pass = sheet.acell('X2').value
        if god_pass and str(god_pass).strip() == password:
            logged_in_users[chat_id] = {'pass': password, 'role': 'god'}
            del user_states[chat_id]
            return handle_callback(chat_id, "adm_menu")

        adm_sheet = get_admins_sheet()
        if adm_sheet:
            adm_passes = adm_sheet.col_values(1)
            adm_vips = adm_sheet.col_values(3)
            for i in range(1, len(adm_passes)):
                if str(adm_passes[i].strip()) == password:
                    role = 'vip' if i < len(adm_vips) and str(adm_vips[i].strip()).lower() == 'yes' else 'admin'
                    logged_in_users[chat_id] = {'pass': password, 'role': role}
                    del user_states[chat_id]
                    return handle_callback(chat_id, "adm_menu")

        special_codes = get_special_codes()
        if password in special_codes:
            del user_states[chat_id]
            return send_message(chat_id, special_codes[password], {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_login"}]]})

        try:
            col_passwords, col_names = sheet.col_values(1), sheet.col_values(3)
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password: user_idx = i; break
            if user_idx != -1:
                user_name = col_names[user_idx].strip()
                logged_in_users[chat_id] = {'pass': password, 'role': 'user'}
                del user_states[chat_id]
                send_message(chat_id, f"✅ خوش آمدید، {user_name} عزیز")
                return show_main_menu(chat_id)
            else: send_message(chat_id, "❌ رمز اشتباه است.")
        except: send_message(chat_id, "⚠️ خطا در برقراری ارتباط.")
        return

    # ✨ اصلاح اضافه کردن عضو (کد عضو میاد تو O9)
    if state and state["step"] == "adm_add_name":
        user_states[chat_id] = {"step": "adm_add_fullname", "short_name": text}
        send_message(chat_id, "لطفا نام و نام خانوادگی عضو جدید را بنویسید:")
        
    elif state and state["step"] == "adm_add_fullname":
        user_states[chat_id] = {"step": "adm_add_pass", "short_name": state["short_name"], "full_name": text}
        send_message(chat_id, "لطفا یک رمز عبور برای ایشان انتخاب کنید:")
        
    elif state and state["step"] == "adm_add_pass":
        user_states[chat_id] = {"step": "adm_add_confirm", "short_name": state["short_name"], "full_name": state["full_name"], "pass": text}
        msg = f"🔗 **اطلاعات عضو جدید:**\nنام کوتاه: {state['short_name']}\nنام کامل: {state['full_name']}\nرمز عبور: {text}\n\nآیا تایید می‌کنید؟ (بله/خیر)"
        send_message(chat_id, msg)
        
    elif state and state["step"] == "adm_add_confirm":
        if text.strip().lower() == "بله":
            try:
                sheet = get_sheet()
                empty_row = get_first_empty_row(sheet)
                sheet.update_cell(empty_row, 1, state["pass"]) # A
                sheet.update_cell(empty_row, 2, "=P11")     # B
                sheet.update_cell(empty_row, 3, state["short_name"]) # C
                sheet.update_cell(empty_row, 4, state["full_name"])  # D
                
                # ✨ قرار دادن کد کاربری عضو جدید در O9
                sheet.update('O9', state["pass"])
                
                del user_states[chat_id]
                send_message(chat_id, "✅ کاربر با موفقیت اضافه شد.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_mem_menu"}]]})
            except: send_message(chat_id, "❌ خطا در ثبت اطلاعات.")
        else: handle_callback(chat_id, "adm_mem_add_start")

    elif state and state["step"] == "adm_del_sel":
        try:
            idx = int(text.strip())
            if 1 <= idx <= state["max_idx"]:
                sheet = get_sheet()
                sheet.batch_clear([f"A{idx+1}:D{idx+1}"])
                del user_states[chat_id]
                send_message(chat_id, "✅ کاربر با موفقیت حذف شد و جایگاهش خالی ماند.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_mem_menu"}]]})
            else: send_message(chat_id, "❌ عدد وارد شده نامعتبر است.")
        except: send_message(chat_id, "❌ لطفا فقط عدد ارسال کنید.")

    elif state and state["step"] == "adm_deduct_pass":
        password = text.strip()
        sheet = get_sheet()
        col_p, col_b = sheet.col_values(1), sheet.col_values(2)
        user_idx = -1
        for i in range(1, len(col_p)):
            if str(col_p[i].strip()) == password: user_idx = i; break
        if user_idx != -1:
            balance = int(float(col_b[user_idx]))
            user_states[chat_id] = {"step": "adm_deduct_amount", "pass": password, "idx": user_idx, "balance": balance}
            send_message(chat_id, f"💎 موجودی کاربر: {balance:,} طوس کوین\n\nچقدر طوس کوین کم شود؟", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_ser_menu"}]]})
        else: send_message(chat_id, "❌ کاربری با این رمز یافت نشد.")

    elif state and state["step"] == "adm_deduct_amount":
        try:
            amount = int(text.strip())
            if amount <= 0: return send_message(chat_id, "❌ عدد باید بزرگتر از صفر باشد.")
            password, user_idx = state["pass"], state["idx"]
            ded_sheet = get_deduction_sheet()
            if ded_sheet:
                headers = ded_sheet.row_values(1)
                target_col_idx = -1
                for i, header in enumerate(headers):
                    if str(header).strip() == password: target_col_idx = i + 1; break
                if target_col_idx != -1:
                    col_values = ded_sheet.col_values(target_col_idx)
                    ded_sheet.update_cell(len(col_values) + 1, target_col_idx, amount)
            del user_states[chat_id]
            send_message(chat_id, f"✅ با موفقیت {amount:,} طوس کوین از حساب کاربر کسر شد.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_ser_menu"}]]})
        except: send_message(chat_id, "❌ لطفا یک عدد صحیح ارسال کنید.")

    # ✨ اصلاح اضافه کردن ادمین (دیگه O9 رو دست نمیزنه، فقط میبره تو شیت admins)
    elif state and state["step"] == "adm_add_adm_fullname":
        user_states[chat_id] = {"step": "adm_add_adm_pass", "fullname": text}
        send_message(chat_id, "لطفا رمز عبور ادمین جدید را بنویسید:")
        
    elif state and state["step"] == "adm_add_adm_pass":
        user_states[chat_id] = {"step": "adm_add_adm_isvip", "fullname": state["fullname"], "pass": text}
        send_message(chat_id, "آیا این ادمین ویژه می‌باشد؟ (بله/خیر)\n_(فقط ادمین‌های ویژه می‌توانند ادمین جدید اضافه کنند)_")
        
    elif state and state["step"] == "adm_add_adm_isvip":
        is_vip = text.strip().lower() == "بله"
        if is_vip and not check_perm(chat_id, 'vip'):
            return send_message(chat_id, "❌ شما دسترسی اضافه کردن ادمین ویژه را ندارید.")
        user_states[chat_id] = {"step": "adm_add_adm_confirm", "fullname": state["fullname"], "pass": state["pass"], "is_vip": is_vip}
        vip_tag = "(ویژه)" if is_vip else "(عادی)"
        msg = f"🔗 **اطلاعات ادمین جدید:**\nنام: {state['fullname']}\nرمز: {state['pass']}\nسطح دسترسی: {vip_tag}\n\nآیا تایید می‌کنید؟ (بله/خیر)"
        send_message(chat_id, msg)
        
    elif state and state["step"] == "adm_add_adm_confirm":
        if text.strip().lower() == "بله":
            try:
                sheet = get_sheet()
                # حذف از لیست کاربران عادی اگر قبلا ثبت شده بود
                col_p = sheet.col_values(1)
                for i in range(1, len(col_p)):
                    if str(col_p[i].strip()) == state["pass"]:
                        sheet.batch_clear([f"A{i+1}:D{i+1}"])
                        break
                
                # ✨ ثبت فقط در شیت ادمین ها
                adm_sheet = get_admins_sheet()
                if adm_sheet:
                    empty_row = get_first_empty_row(adm_sheet)
                    adm_sheet.update_cell(empty_row, 1, state["pass"])
                    adm_sheet.update_cell(empty_row, 2, state["fullname"])
                    adm_sheet.update_cell(empty_row, 3, "yes" if state["is_vip"] else "no")
                    
                del user_states[chat_id]
                send_message(chat_id, "✅ ادمین با موفقیت اضافه شد.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_adm_menu"}]]})
            except Exception as e: send_message(chat_id, f"❌ خطا: {str(e)}")
        else: handle_callback(chat_id, "adm_adm_add_start")

    elif state and state["step"] == "adm_del_adm_sel":
        try:
            idx = int(text.strip())
            if 1 <= idx <= state["max_idx"]:
                adm_sheet = get_admins_sheet()
                if adm_sheet:
                    target_pass = adm_sheet.col_values(1)[idx].strip()
                    target_vip = adm_sheet.col_values(3)[idx].strip().lower()
                    
                    if target_vip == 'yes':
                        if logged_in_users[chat_id]['pass'] != target_pass:
                            return send_message(chat_id, "❌ ادمین‌های ویژه فقط توسط خودشان قابل حذف هستند.")
                    
                    god_pass = get_sheet().acell('X2').value
                    if str(target_pass) == str(god_pass).strip():
                        return send_message(chat_id, "❌ شما نمی‌توانید ادمین اصلی سیستم را حذف کنید!")

                    adm_sheet.batch_clear([f"A{idx+1}:C{idx+1}"])
                    
                del user_states[chat_id]
                send_message(chat_id, "✅ ادمین با موفقیت حذف شد.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_adm_menu"}]]})
            else: send_message(chat_id, "❌ عدد وارد شده نامعتبر است.")
        except: send_message(chat_id, "❌ لطفا فقط عدد ارسال کنید.")

    elif state and state["step"] == "adm_prize_name":
        user_states[chat_id] = {"step": "adm_prize_coins", "name": text}
        send_message(chat_id, "لطفا تعداد طوس کوین این جایزه را بنویسید:")
        
    elif state and state["step"] == "adm_prize_coins":
        try:
            coins = int(text.strip())
            sheet = get_sheet()
            col_e = sheet.col_values(5)
            max_code = 100
            for val in col_e[1:]:
                if val.strip() and val.strip().isdigit():
                    if int(val.strip()) > max_code: max_code = int(val.strip())
            new_code = str(max_code + 1)
            user_states[chat_id] = {"step": "adm_prize_confirm", "name": state["name"], "coins": coins, "code": new_code}
            send_message(chat_id, f"🏆 کد محصول برای این جایزه: {new_code}\n\nآیا تایید می‌کنید؟ (بله/خیر)")
        except: send_message(chat_id, "❌ لطفا یک عدد صحیح برای کوین‌ها بنویسید.")
        
    elif state and state["step"] == "adm_prize_confirm":
        if text.strip().lower() == "بله":
            try:
                sheet = get_sheet()
                col_e = sheet.col_values(5)
                next_row = len(col_e) + 1
                sheet.update_cell(next_row, 5, state["code"])
                sheet.update_cell(next_row, 6, state["name"])
                sheet.update_cell(next_row, 7, state["coins"])
                del user_states[chat_id]
                send_message(chat_id, "✅ جایزه با موفقیت ثبت شد.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_prize_menu"}]]})
            except: send_message(chat_id, "❌ خطا در ثبت جایزه.")
        else: handle_callback(chat_id, "adm_prize_add_name")

    elif state and state["step"] == "adm_prize_get_code":
        code = text.strip()
        products = get_products()
        if code in products:
            prod = products[code]
            user_states[chat_id] = {"step": "adm_prize_edit_details", "code": code}
            send_message(chat_id, f"🛍 کالا: {prod['name']}\n💎 کوین: {prod['price']}\n\nکالا کاملا قابل ویرایش می‌باشد.\nلطفا در خط اول اسم کالا و در خط دوم امتیاز پیشنهادی را بنویسید:\n_(مثال: ماشین کنترولی\n50000)_")
        else: send_message(chat_id, "❌ کد کالا یافت نشد.")

    elif state and state["step"] == "adm_prize_edit_details":
        lines = text.strip().split('\n')
        if len(lines) == 2:
            try:
                new_name = lines[0].strip()
                new_price = int(lines[1].strip())
                sheet = get_sheet()
                col_e = sheet.col_values(5)
                for i in range(1, len(col_e)):
                    if str(col_e[i].strip()) == state["code"]:
                        sheet.update_cell(i+1, 6, new_name)
                        sheet.update_cell(i+1, 7, new_price)
                        break
                del user_states[chat_id]
                send_message(chat_id, "✅ جایزه با موفقیت ویرایش شد.", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "adm_prize_menu"}]]})
            except: send_message(chat_id, "❌ خطا در پردازش. مطمئن شو خط دوم فقط عدد باشد.")
        else: send_message(chat_id, "❌ لطفا دقیقاً به فرمت خواسته شده (دو خط) بنویسید.")

    if state and state["step"] == "waiting_for_products":
        products = get_products() 
        input_codes = text.replace(',', ' ').split()
        if not input_codes: return send_message(chat_id, "⚠️ لطفاً کد محصول را وارد کنید.")
        selected_products, total_price = [], 0
        for code in input_codes:
            if code in products: selected_products.append(products[code]); total_price += products[code]['price']
            else: return send_message(chat_id, f"❌ کد «{code}» نامعتبر است.")
        user_states[chat_id] = {"step": "waiting_for_pass_buy", "selected_products": selected_products, "total_price": total_price}
        prod_names = " و ".join([p['name'] for p in selected_products])
        send_message(chat_id, f"💳 **صورت حساب**\n━━━━━━━━━━━━━━━\n🛍 کالا: {prod_names}\n💎 مبلغ: {total_price:,} طوس کوین\n━━━━━━━━━━━━━━━\n🔐 لطفاً برای تایید نهایی، رمز عبور خود را ارسال کنید:", {"inline_keyboard": [[{"text": "« تغییر کالاها", "callback_data": "back_to_products"}]]})

    elif state and state["step"] == "waiting_for_pass_buy":
        password = text
        selected_products, total_price = state["selected_products"], state["total_price"]
        del user_states[chat_id]
        try:
            sheet = get_sheet()
            col_passwords, col_balances, col_names = sheet.col_values(1), sheet.col_values(2), sheet.col_values(3)
            user_idx = -1
            for i in range(1, len(col_passwords)):
                if str(col_passwords[i].strip()) == password: user_idx = i; break
            markup = {"inline_keyboard": [[{"text": "🏠 منوی اصلی", "callback_data": "back_to_main"}]]}
            if user_idx == -1: return send_message(chat_id, "❌ رمز اشتباه بود. سفارش لغو شد.", markup)
            balance = int(float(col_balances[user_idx]))
            user_name = col_names[user_idx].strip() 
            if balance >= total_price:
                new_balance = balance - total_price
                ded_sheet = get_deduction_sheet()
                if ded_sheet:
                    headers = ded_sheet.row_values(1)
                    target_col_idx = -1
                    for i, header in enumerate(headers):
                        if str(header).strip() == password: target_col_idx = i + 1; break
                    if target_col_idx != -1:
                        col_values = ded_sheet.col_values(target_col_idx)
                        ded_sheet.update_cell(len(col_values) + 1, target_col_idx, total_price)
                prod_names = "، ".join([p['name'] for p in selected_products])
                send_sticker(chat_id, SUCCESS_STICKER_ID)
                invoice_sheet = get_invoice_sheet()
                if invoice_sheet: invoice_sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_name, prod_names, total_price, new_balance])
                send_message(chat_id, f"✅ **تراکنش موفق**\n━━━━━━━━━━━━━━━\nمبلغ کسر شده: {total_price:,} طوس کوین\nموجودی جدید: {new_balance:,} طوس کوین", markup)
                send_message(ADMIN_CHAT_ID, f"🛒 **خرید جدید**\n👤 {user_name}\n📦 {prod_names}\n💰 {total_price:,} طوس کوین کسر شد.")
            else: send_message(chat_id, f"❌ **موجودی ناکافی**\n━━━━━━━━━━━━━━━\nموجودی شما: {balance:,} طوس کوین\nمبلغ خرید: {total_price:,} طوس کوین", markup)
        except: send_message(chat_id, "⚠️ خطا در پردازش سفارش.")

    elif state and state["step"] == "waiting_for_pass_check":
        del user_states[chat_id]
        fetch_and_send_balance(chat_id, text)

def fetch_and_send_balance(chat_id, password):
    try:
        sheet = get_sheet()
        col_p, col_b = sheet.col_values(1), sheet.col_values(2)
        for i in range(1, len(col_p)):
            if str(col_p[i].strip()) == password:
                balance = int(float(col_b[i]))
                return send_message(chat_id, f"━━━━━━━━━━━━━━━\n💰 **موجودی حساب شما:**\n🔸 {balance:,} طوس کوین\n━━━━━━━━━━━━━━━", {"inline_keyboard": [[{"text": "« بازگشت", "callback_data": "back_to_main"}]]})
        send_message(chat_id, "❌ کاربری با این رمز یافت نشد.")
    except: send_message(chat_id, "⚠️ خطا در دریافت اطلاعات.")

def show_main_menu(chat_id):
    if chat_id in logged_in_users and logged_in_users[chat_id]['role'] == 'user':
        markup = {"inline_keyboard": [[{"text": "🛒 ثبت سفارش", "callback_data": "order"}], [{"text": "💰 استعلام موجودی", "callback_data": "balance"}], [{"text": "⚙️ خدمات بیشتر", "callback_data": "show_more_menu"}]]}
        send_message(chat_id, "🏠 **منوی اصلی**\n━━━━━━━━━━━━━━━\nگزینه مورد نظر را انتخاب کنید:", markup)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```
