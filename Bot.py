import sqlite3
import time
import threading
from datetime import datetime
import telebot
from telebot import types
from CONFIG import bdPath, bdName, logFile, BOT_TOKEN,CHAT_ID

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

# --- отправка сообщений о завершении сессии ---
def send_telegram_message(message):
    for chat_id in CHAT_ID:
        bot.send_message(chat_id, message, parse_mode="HTML")

def send_session_end_message(name, start_time, end_time, duration, up_mb, down_mb):
    message = (
        f"📡 <b>Сессия завершена</b>\n"
        f"👤 Клиент: <b>{name}</b>\n"
        f"🕒 Период: {start_time} – {end_time}\n"
        f"⏱️ Длительность: {duration}\n"
        f"📊 Трафик: {format_traffic(up_mb + down_mb)}\n"
        f"⬆️ Upload: {format_traffic(up_mb)}\n"
        f"⬇️ Download: {format_traffic(down_mb)}"
    )
    send_telegram_message(message)

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
                    start_fmt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session['start_time']))
                    end_fmt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))
                    send_session_end_message(name, start_fmt, end_fmt, duration, up_mb, down_mb)
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

# --- статистика за всё время ---
def get_total_stats():
    connection = sqlite3.connect(f"{bdPath}/{bdName}")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM inbounds")
    rows = cursor.fetchall()
    connection.close()

    stats = {}
    for row in rows:
        name = row[5]
        up = float(row[2]) / 2**20
        down = float(row[3]) / 2**20
        if name not in stats:
            stats[name] = {"up": 0, "down": 0}
        stats[name]["up"] += up
        stats[name]["down"] += down

    report = "<b>📊 Статистика за всё время:</b>\n\n"
    for name, values in stats.items():
        total = values["up"] + values["down"]
        report += (f"👤 <b>{name}</b>\n"
                   f"⬆️ Upload: {format_traffic(values['up'])}\n"
                   f"⬇️ Download: {format_traffic(values['down'])}\n"
                   f"📊 Всего: {format_traffic(total)}\n\n")
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