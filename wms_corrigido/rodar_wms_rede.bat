@echo off
setlocal

:: Entra na pasta do projeto
cd /d "%~dp0"

:: Ativa o ambiente virtual
call .venv\Scripts\activate

:: Mostra os IPs da máquina
echo ============================================
echo IPS DESTA MAQUINA:
ipconfig | findstr /i "IPv4"
echo ============================================
echo.

:: Roda o Streamlit aceitando acesso da rede local
streamlit run app.py --server.address 0.0.0.0 --server.port 8501

pause