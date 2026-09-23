@echo off
title Servidor Backend Aula Segura - Puerto 8010
echo ==============================================
echo   Iniciando Backend Aula Segura (Puerto 8010)
echo ==============================================
cd /d "%~dp0backend"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    python -m uvicorn main:app --reload --port 8010
) else (
    uvicorn main:app --reload --port 8010
)
pause
