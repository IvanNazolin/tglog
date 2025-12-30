#!/bin/bash

pkill -f "python3.*Bot.py"
sleep 2

pkill -9 -f "python3.*Bot.py" 2>/dev/null

cd /var/tglog && nohup python3 Bot.py > output.log 2>&1 &
echo "Bot.py перезапущен"

