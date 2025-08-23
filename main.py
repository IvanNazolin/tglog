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