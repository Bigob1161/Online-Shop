@echo off
chcp 65001 >nul
set PY=python
where python >nul 2>nul || set PY=py
cd /d "%~dp0client"
%PY% client.py
