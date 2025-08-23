import sqlite3
import time
import json
import os
from CONFIG import bdPath,bdName,logFile,trafficFile,BOT_TOKEN,CHAT_ID
import requests

active_sessions = {}


def send_session_end_message(name, start_time, end_time, duration, up_mb, down_mb):
    message = (
        f"📡 <b>Сессия завершена</b>\n"
        f"👤 Клиент: <b>{name}</b>\n"
        f"🕒 Период: {start_time} – {end_time}\n"
        f"⏱️ Длительность: {duration}\n"
        f"📊 Трафик: {format_traffic((up_mb + down_mb))}\n"
        f"⬆️ Upload: {format_traffic(up_mb)}\n"
        f"⬇️ Download: {format_traffic(down_mb)}"
    )
    send_telegram_message(message)

def send_telegram_message(message):
    for CHAT_Id in CHAT_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_Id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=payload)
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")

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

def load_traffic_totals():
    if os.path.exists(trafficFile):
        with open(trafficFile, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_traffic_totals(totals):
    with open(trafficFile, "w", encoding="utf-8") as f:
        json.dump(totals, f, ensure_ascii=False, indent=2)

def main():
    global active_sessions
    connection = sqlite3.connect(f'{bdPath}/{bdName}')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM inbounds")
    rows = cursor.fetchall()
    connection.close()

    current_time = time.time()
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time))

    print("=" * 74)
    print(f"{'Текущий статус':^74}")
    print(f"Время проверки: {current_time_str}")
    print("-" * 74)

    print(f"{'Активные сессии':^74}")
    print("-" * 74)
    print(f"{'Клиент':<15}{'Начало':<20}{'Длительность':<15}{'Трафик':<10}")
    print("-" * 74)

    updated_sessions = {}
    any_active = False
    telegram_message = ""

    for row in rows:
        name = row[5]
        up = float(row[2])
        down = float(row[3])

        if name in active_sessions:
            session = active_sessions[name]

            if up > session['last_up'] or down > session['last_down']:
                # Сессия продолжается
                duration_secs = int(current_time - session['start_time'])
                duration = format_duration(duration_secs)
                used_traffic = ((up - session['start_up']) + (down - session['start_down'])) / 2**20

                print(f"{name:<15}{time.strftime('%H:%M:%S', time.localtime(session['start_time'])):<20}{duration:<15}{format_traffic(used_traffic):<10}")
                print("_" * 74)

                # Добавим в телегу
                telegram_message += f"👤 <b>{name}</b>\n⏱️ {duration} | 📊 {format_traffic(used_traffic)}\n\n"

                any_active = True

                updated_sessions[name] = {
                    **session,
                    'last_up': up,
                    'last_down': down
                }
            else:
                # Сессия завершена
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
            # Новая сессия
            updated_sessions[name] = {
                'start_time': current_time,
                'start_up': up,
                'start_down': down,
                'last_up': up,
                'last_down': down
            }

    active_sessions = updated_sessions

    if not any_active:
        print("Нет активных сессий в данный момент.")
        send_telegram_message(f"<b>🔕 Нет активных сессий в данный момент.</b>")
    else:
        send_telegram_message(f"<b>📡 Активные сессии:</b>\n\n{telegram_message.strip()}")

    # Общий трафик
    print("-" * 74)
    print(f"{'Трафик':^74}")
    print("-" * 74)
    print(f"{'Клиент':<15}{'Отправлено':<15}{'Получено':<15}{'Всего':<15}")
    print("-" * 74)

    traffic_stats = []
    for row in rows:
        name = row[5]
        up = float(row[2]) / 2**20  # MB
        down = float(row[3]) / 2**20
        total = up + down
        traffic_stats.append((name, up, down, total))

    for name, up, down, total in sorted(traffic_stats, key=lambda x: x[3], reverse=True):
        print(f"{name:<15}{format_traffic(up):<15}{format_traffic(down):<15}{format_traffic(total):<15}")
        print("-" * 74)

    print("=" * 74)
    time.sleep(180)

if __name__ == "__main__":
    while time.ctime().split()[3][-2:] != "00":
        pass
    while True:
        main()