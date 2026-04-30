@echo off
cd /d "%~dp0"
echo Iniciando Monitor de Velocidad...
echo.
streamlit run monitor_velocidad.py --server.headless true --server.port 8501
pause
