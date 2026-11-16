@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" payment_edge.py --server http://127.0.0.1:8000 --rows 1000 --delay 0.01 --feedback-delay 0
pause
