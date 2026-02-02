import re
import time
from os import system

attempts = {}

WINDOW = 5 * 60      # 5 минут
BAN_TIME = 1 * 60    # 2 минуты
CHECK_INTERVAL = 60  # 1 минута

LOG_FILE = "3xui.log"
PORT = 443

pattern = re.compile(r'IP:\s*"([\d\.]+)"')

def freez(ip, port, ban_time):
    system(f"./ban.sh {ip} {port} {ban_time}")

def process_line(line):
    if "wrong username:" not in line:
        return

    match = pattern.search(line)
    if not match:
        return

    ip = match.group(1)
    now = time.time()

    attempts.setdefault(ip, [])
    attempts[ip] = [t for t in attempts[ip] if now - t <= WINDOW]
    attempts[ip].append(now)

    if len(attempts[ip]) >= 2:
        print(f"[BAN] {ip} заблокирован на 2 минуты")
        freez(ip, PORT, BAN_TIME)
        del attempts[ip]

with open(LOG_FILE, "r", encoding="utf-8") as f:
    f.seek(0, 2)

    while True:
        where = f.tell()
        line = f.readline()

        if not line:
            f.seek(where)
            time.sleep(CHECK_INTERVAL)
            continue

        process_line(line)
