@echo off
chcp 65001 >nul
set PY=python
where python >nul 2>nul || set PY=py
title Сервер интернет-магазина
cd /d "%~dp0server"
%PY% server.py
pause
