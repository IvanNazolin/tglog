#!/bin/bash
IP=$1
PORT=${2:-443}
TIMEOUT=${3:-120}

# Блокируем
iptables -A INPUT -s $IP -p tcp --dport $PORT -j DROP

# Запускаем таймер на разблокировку
(
    sleep ${TIMEOUT}
    iptables -D INPUT -s $IP -p tcp --dport $PORT -j DROP
) &