@echo off
chcp 65001 >nul
set PY=python
where python >nul 2>nul || set PY=py
echo Установка библиотеки графического интерфейса PyQt5...
%PY% -m pip install -r "%~dp0requirements.txt"
echo.
echo Готово. Теперь запустите "1_Запустить_сервер.bat", затем "2_Запустить_программу.bat".
pause
