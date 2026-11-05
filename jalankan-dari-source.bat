@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Klik kanan file ini lalu pilih "Run as administrator".
  pause
  exit /b 1
)
cd /d "%~dp0"
python -m pip install -r requirements.txt
python main.py
