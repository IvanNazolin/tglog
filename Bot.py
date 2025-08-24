import sqlite3
import time
import threading
import telebot
from telebot import types
from CONFIG import bdPath, bdName, logFile, BOT_TOKEN,CHAT_ID
from datetime import datetime

# --- инициализация бота ---
bot = telebot.TeleBot(BOT_TOKEN)
chat_ids = CHAT_ID
active_sessions = {}
last_totals = {}

# --- форматирование ---
def format_traffic(mb):
    return f"{mb:.2f} MB" if mb < 1024 else f"{mb/1024:.2f} GB"

def format_duration(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{int(hours):02}:{int(mins):02}:{int(secs):02}"

def log_session(name, start_time, used_traffic, duration):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
    with open(logFile, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {name} | {format_traffic(used_traffic)} | Длительность: {duration}\n")

# --- мониторинг сессий ---
def check_sessions():
    global active_sessions, last_totals
    connection = sqlite3.connect(f"{bdPath}/{bdName}")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM inbounds")
    rows = cursor.fetchall()
    connection.close()

    current_time = time.time()
    updated_sessions = {}
    telegram_message = ""
    any_active = False

    # считаем текущий трафик
    current_totals = {}
    for row in rows:
        name = row[5]
        up = float(row[2]) / 2**20
        down = float(row[3]) / 2**20
        total = up + down
        current_totals[name] = total

    # считаем разницу с прошлым замером
    traffic_diff = {}
    if last_totals:
        for name, total in current_totals.items():
            if name in last_totals:
                diff = total - last_totals[name]
                if diff > 0:
                    traffic_diff[name] = diff

    for row in rows:
        name = row[5]
        up = float(row[2])
        down = float(row[3])

        if name in active_sessions:
            session = active_sessions[name]
            if up > session['last_up'] or down > session['last_down']:
                duration_secs = int(current_time - session['start_time'])
                duration = format_duration(duration_secs)
                used_traffic = ((up - session['start_up']) + (down - session['start_down'])) / 2**20

                # добавляем прирост за последние 3 минуты
                extra = ""
                if name in traffic_diff:
                    extra = f" | + {format_traffic(traffic_diff[name])}"

                telegram_message += f"👤 <b>{name}</b>\n⏱️ {duration} | 📊 {format_traffic(used_traffic)}{extra}\n\n"
                any_active = True

                updated_sessions[name] = {
                    **session,
                    'last_up': up,
                    'last_down': down
                }
            else:
                # сессия завершена
                duration_secs = int(current_time - session['start_time'])
                duration = format_duration(duration_secs)
                up_mb = (session['last_up'] - session['start_up']) / 2**20
                down_mb = (session['last_down'] - session['start_down']) / 2**20
                total_mb = up_mb + down_mb

                if total_mb > 0:
                    log_session(name, session['start_time'], total_mb, duration)
        else:
            updated_sessions[name] = {
                'start_time': current_time,
                'start_up': up,
                'start_down': down,
                'last_up': up,
                'last_down': down
            }

    active_sessions = updated_sessions
    last_totals = current_totals

    if not any_active:
        return "<b>🔕 Нет активных сессий</b>"
    else:
        return f"<b>📡 Активные сессии:</b>\n\n{telegram_message.strip()}"

# --- поток рассылки ---
def send_periodic():
    while True:
        time.sleep(180)  # каждые 3 минуты
        report = check_sessions()
        for chat_id in chat_ids:
            bot.send_message(chat_id, report, parse_mode="HTML")

# --- команды ---
@bot.message_handler(commands=['start'])
def start_message(message):
   # chat_ids.add(message.chat.id)
    bot.reply_to(message, "✅ Мониторинг подключен!\nЯ буду присылать тебе отчеты каждые 3 минуты.")

@bot.message_handler(commands=['menu'])
def menu(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("За все время")
    btn2 = types.KeyboardButton("Отчет за сегодня")
    keyboard.add(btn1, btn2)
    bot.send_message(message.chat.id,"Выбери отчёт:", reply_markup=keyboard)

def get_total_stats():
    connection = sqlite3.connect(f"{bdPath}/{bdName}")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM inbounds")
    rows = cursor.fetchall()
    connection.close()

    stats = {}
    for row in rows:
        name = row[5]
        up = float(row[2]) / 2**20   # в MB
        down = float(row[3]) / 2**20
        if name not in stats:
            stats[name] = {"up": 0, "down": 0}
        stats[name]["up"] += up
        stats[name]["down"] += down

    # формируем текст
    report = "<b>📊 Статистика за всё время:</b>\n\n"
    for name, values in stats.items():
        total = values["up"] + values["down"]
        report += (f"👤 <b>{name}</b>\n"
                   f"⬆️ Upload: {format_traffic(values['up'])}\n"
                   f"⬇️ Download: {format_traffic(values['down'])}\n"
                   f"📊 Всего: {format_traffic(total)}\n\n")
    return report.strip()

def get_today_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    stats = {}

    try:
        with open(logFile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(f"[{today}"):
                    # формат строки: [YYYY-MM-DD HH:MM:SS] name | traffic | ...
                    try:
                        parts = line.strip().split("] ")[1]  # отрезаем дату
                        name, traffic, *_ = parts.split("|")
                        name = name.strip()
                        traffic_value = traffic.strip().split()[0]  # только число
                        traffic_unit = traffic.strip().split()[1]   # MB или GB

                        # приводим в MB
                        if traffic_unit == "GB":
                            traffic_mb = float(traffic_value) * 1024
                        else:
                            traffic_mb = float(traffic_value)

                        if name not in stats:
                            stats[name] = 0
                        stats[name] += traffic_mb
                    except Exception:
                        continue
    except FileNotFoundError:
        return "<b>⚠️ Лог файл не найден.</b>"

    if not stats:
        return "<b>🔕 За сегодня сессий нет.</b>"

    report = "<b>📊 Отчет за сегодня:</b>\n\n"
    for name, mb in stats.items():
        report += f"👤 <b>{name}</b> | 📊 {format_traffic(mb)}\n"
    return report.strip()

@bot.message_handler(func=lambda message: message.text in ["За все время", "Отчет за сегодня"])
def handle_buttons(message):
    if message.text == "За все время":
        report = get_total_stats()
        bot.send_message(message.chat.id, report, parse_mode="HTML")
    elif message.text == "Отчет за сегодня":
        report = get_today_stats()
        bot.send_message(message.chat.id, report, parse_mode="HTML")

# --- запуск ---
threading.Thread(target=send_periodic, daemon=True).start()
bot.infinity_polling()