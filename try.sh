#!/bin/bash
echo "Проверка IP адресов Telegram:"

# Основные IP Telegram
IPS="149.154.167.220 149.154.167.199 91.108.56.130 91.108.56.131"

for ip in $IPS; do
    echo -n "$ip: "
    
    # Проверка ICMP
    if ping -c 1 -W 1 $ip &>/dev/null; then
        echo -n "ping ✓ "
    else
        echo -n "ping ✗ "
    fi
    
    # Проверка TCP 443
    if timeout 3 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null; then
        echo "TCP:443 ✓"
    else
        echo "TCP:443 ✗"
    fi
done