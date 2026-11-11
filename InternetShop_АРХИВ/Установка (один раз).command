#!/bin/bash
cd "$(dirname "$0")" && python3 -m pip install -r requirements.txt
echo "Готово. Запустите 1_Запустить_сервер.command, затем 2_Запустить_программу.command"
