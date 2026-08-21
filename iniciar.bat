@echo off
setlocal

set "RAIZ=%~dp0"
set "PYTHON=%RAIZ%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo No se encontro el entorno virtual en "%RAIZ%.venv".
    echo Crealo primero con: python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    pause
    exit /b 1
)

echo Levantando backend en http://localhost:8000 ...
start "Backend - Django" cmd /k ""%PYTHON%" "%RAIZ%backend\manage.py" runserver 8000"

echo Levantando frontend en http://localhost:8080 ...
start "Frontend - NiceGUI" cmd /k ""%PYTHON%" "%RAIZ%frontend\main.py""

echo.
echo Backend y frontend se estan iniciando en ventanas separadas.
echo Cierra esas ventanas para detener cada proceso.
