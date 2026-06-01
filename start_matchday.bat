@echo off
setlocal
cd /d "%~dp0"
title Matchday Brain World Cup

echo ==============================================================
echo  Matchday Brain World Cup
echo ==============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -m venv .venv
)

call .venv\Scripts\activate
python -m pip install -r requirements.txt

echo.
echo PC link:
echo   http://127.0.0.1:5055
echo.
echo Try these phone links while your phone is on the same Wi-Fi:
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /i "IPv4"') do (
  echo   http://%%A:5055
)
echo.
echo If the phone link fails, right-click allow_firewall_5055.ps1 and Run with PowerShell as Administrator.
echo.
python app.py
pause
