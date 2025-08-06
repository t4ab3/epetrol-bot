import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import json
import threading
import time
from datetime import datetime, timedelta


import os
TOKEN = os.environ.get("8257362952:AAEWjYMGT2uEnpDjo2EbOxLG8g5Z9RzAyhA")
bot = telebot.TeleBot(TOKEN)

ROLES_FILE = 'roles.json'
BOOKINGS_FILE = 'bookings.json'

STATIONS = ['1', '2', '3']
POWER_TYPES = ['16', '32']
TIME_ZONES = ['7:30-11:30', '11:30-15:30', '15:30+']

# --- Зчитування та збереження ролей ---
def load_roles():
    try:
        with open(ROLES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_roles(roles):
    with open(ROLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(roles, f, ensure_ascii=False, indent=2)

roles = load_roles()

def get_role(user_id):
    return roles.get(str(user_id), 'new')

def set_role(user_id, role):
    roles[str(user_id)] = role
    save_roles(roles)

# --- Зчитування та збереження бронювань ---
def load_bookings():
    try:
        with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_bookings(bookings):
    with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

# --- Формування клавіатури ---
def get_main_keyboard(role):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if role == 'new':
        kb.add(KeyboardButton("Запросити роль"))
    else:
        kb.add(KeyboardButton("Забронювати місце"))
        kb.add(KeyboardButton("Розклад на сьогодні"))
        kb.add(KeyboardButton("Хто зараз заряджається?"))
        kb.add(KeyboardButton("Моє бронювання"))
        if role == 'admin':
            kb.add(KeyboardButton("Розсилка"))
    return kb

# --- Кнопки для бронювання ---
def format_booking_buttons():
    bookings = load_bookings()
    today = datetime.now().strftime('%Y-%m-%d')
    today_bookings = bookings.get(today, {})

    markup = InlineKeyboardMarkup(row_width=2)

    for tz in TIME_ZONES:
        for station in STATIONS:
            for power in POWER_TYPES:
                slot_name = f"{station}/{power}_{tz}"
                if slot_name in today_bookings:
                    markup.add(InlineKeyboardButton(f"❌ {slot_name}", callback_data=f"taken_{slot_name}"))
                else:
                    markup.add(InlineKeyboardButton(f"✅ {slot_name}", callback_data=f"free_{slot_name}"))
        # Розділювач
        markup.add(InlineKeyboardButton("────────────", callback_data="noop"))
    return markup

# --- Обробка /start ---
@bot.message_handler(commands=['start', 'my_role'])
def start(message):
    user_id = message.from_user.id
    if str(user_id) not in roles:
        set_role(user_id, 'new')
    role = get_role(user_id)
    kb = get_main_keyboard(role)
    if message.text == "/my_role":
        bot.send_message(message.chat.id, f"Твоя роль: {role}")
    else:
        bot.send_message(message.chat.id, f"Вітаю! Твоя роль: {role}", reply_markup=kb)
# --- Скидання бронювань щодня о 6:30 ---
def reset_bookings_daily():
    while True:
        now = datetime.now()
        next_reset = (now + timedelta(days=1)).replace(hour=6, minute=30, second=0, microsecond=0)
        seconds_to_sleep = (next_reset - now).total_seconds()
        time.sleep(seconds_to_sleep)
        save_bookings({})
        print("[INFO] Бронювання скинуто о 6:30")

threading.Thread(target=reset_bookings_daily, daemon=True).start()

# --- Обробка текстових повідомлень ---
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    user_id = message.from_user.id
    role = get_role(user_id)
    text = message.text

    if text == "Запросити роль":
        bot.send_message(message.chat.id, "Заявку на роль надіслано. Чекайте підтвердження.")
    elif text == "Забронювати місце":
        if role in ['manager', 'admin']:
            bot.send_message(message.chat.id, "Оберіть слот:", reply_markup=format_booking_buttons())
        else:
            bot.send_message(message.chat.id, "Бронювання доступне тільки менеджерам та адміністраторам.")
    elif text == "Розклад на сьогодні":
        bookings = load_bookings()
        today = datetime.now().strftime('%Y-%m-%d')
        today_bookings = bookings.get(today, {})
        msg = "Розклад на сьогодні:\n"
        for tz in TIME_ZONES:
            msg += f"\nТайм-зона {tz}:\n"
            for station in STATIONS:
                for power in POWER_TYPES:
                    slot = f"{station}/{power}_{tz}"
                    if slot in today_bookings:
                        u = today_bookings[slot]
                        if 'username' in u and u['username']:
                            username = f"@{u['username']}"
                        else:
                            username = u.get('name', 'Невідомо')
                        msg += f"❌ {slot} — заброньовано {username}\n"
                    else:
                        msg += f"✅ {slot} — вільно\n"
        bot.send_message(message.chat.id, msg)
    elif text == "Хто зараз заряджається?":
        now = datetime.now()
        bookings = load_bookings()
        today = now.strftime('%Y-%m-%d')
        today_bookings = bookings.get(today, {})
        current = []
        for slot, info in today_bookings.items():
            _, time_range = slot.split('_')
            start_str, end_str = time_range.split('-')
            start = int(start_str.split(':')[0])
            end = int(end_str.split(':')[0])
            if start <= now.hour < end:
                current.append(info)
        if current:
            msg = "Зараз заряджаються:\n"
            for u in current:
                username = f"@{u['username']}" if u.get('username') else u.get('name', f"id {u['id']}")
                msg += f"{username}\n"
            bot.send_message(message.chat.id, msg)
        else:
            bot.send_message(message.chat.id, "Ніхто зараз не заряджається.")
    elif text == "Моє бронювання":
        bookings = load_bookings()
        today = datetime.now().strftime('%Y-%m-%d')
        today_bookings = bookings.get(today, {})
        user_slots = [slot for slot, val in today_bookings.items() if val['id'] == user_id]
        if not user_slots:
            bot.send_message(message.chat.id, "У вас немає бронювань на сьогодні.")
        else:
            for slot in user_slots:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("Скасувати бронювання", callback_data=f"cancel_{slot}"))
                bot.send_message(message.chat.id, f"Ваше бронювання: {slot}", reply_markup=markup)
    elif text == "Розсилка":
        if role == 'admin':
            msg = bot.send_message(message.chat.id, "Введіть текст для розсилки:")
            bot.register_next_step_handler(msg, broadcast_message)
        else:
            bot.send_message(message.chat.id, "Ця команда доступна лише адміністратору.")
    else:
        bot.send_message(message.chat.id, "Невідома команда.")

# --- Обробка callback від кнопок бронювання ---
@bot.callback_query_handler(func=lambda c: c.data.startswith(('free_', 'taken_', 'cancel_')))
def callback_booking(call):
    user_id = call.from_user.id
    username = call.from_user.username
    full_name = call.from_user.full_name
    role = get_role(user_id)
    data = call.data

    bookings = load_bookings()
    today = datetime.now().strftime('%Y-%m-%d')
    if today not in bookings:
        bookings[today] = {}

    if data.startswith('free_'):
        slot = data[5:]

        # Перевірка обмеження: 1 слот на таймзону
        _, tz = slot.split('_')
        user_slots_in_tz = [
            s for s, u in bookings[today].items()
            if u['id'] == user_id and s.endswith(tz)
        ]
        if user_slots_in_tz:
            bot.answer_callback_query(call.id, "У цій тайм-зоні ви вже маєте бронювання.")
            return

        bookings[today][slot] = {
            "id": user_id,
            "name": full_name,
            "username": username
        }
        save_bookings(bookings)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=format_booking_buttons())
        bot.answer_callback_query(call.id, f"Ви забронювали слот {slot}.")
        threading.Thread(target=send_reminder, args=(user_id, slot), daemon=True).start()

    elif data.startswith('cancel_'):
        slot = data[7:]
        if slot in bookings[today] and bookings[today][slot]['id'] == user_id:
            del bookings[today][slot]
            save_bookings(bookings)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=format_booking_buttons())
            bot.answer_callback_query(call.id, "Ваше бронювання скасовано.")
        else:
            bot.answer_callback_query(call.id, "Ви не можете скасувати це бронювання.")

    elif data.startswith('taken_'):
        bot.answer_callback_query(call.id, "Цей слот вже зайнятий.")

# --- Нагадування за 10 хв ---
def send_reminder(user_id, slot):
    _, tz = slot.split('_')
    start_str = tz.split('-')[0]
    start_hour, start_min = map(lambda x: int(x.replace('+', '')), start_str.split(':'))
    now = datetime.now()
    slot_start = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    if slot_start < now:
        return
    reminder_time = slot_start - timedelta(minutes=10)
    wait_seconds = (reminder_time - now).total_seconds()
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    try:
        bot.send_message(user_id, f"Нагадування: через 10 хвилин починається ваше бронювання {slot}.")
    except Exception as e:
        print(f"[ERROR] Не вдалося надіслати нагадування: {e}")

# --- Розсилка ---
def broadcast_message(message):
    text = message.text
    roles_data = load_roles()
    sent = 0
    for uid_str, role in roles_data.items():
        try:
            bot.send_message(int(uid_str), text)
            sent += 1
        except:
            continue
    bot.send_message(message.chat.id, f"Розіслано {sent} повідомлень.")

# --- Запуск ---
bot.infinity_polling()

