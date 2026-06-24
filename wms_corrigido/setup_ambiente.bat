@echo off
setlocal

:: Entra na pasta onde este arquivo está
cd /d C:\Users\Faturamento\Downloads\wms_supabase

echo ============================================
echo INICIANDO SETUP DO AMBIENTE
echo ============================================
echo.

:: Verifica se o Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python nao encontrado.
    echo Instale o Python e marque a opcao "Add Python to PATH".
    pause
    exit /b
)

echo ✅ Python encontrado.
echo.

:: Cria a .venv se nao existir
if not exist ".venv" (
    echo Criando ambiente virtual (.venv)...
    python -m venv .venv
) else (
    echo Ambiente virtual ja existe.
)

echo.

:: Ativa o ambiente virtual
echo Ativando ambiente virtual...
call .venv\Scripts\activate

echo.

:: Atualiza o pip
echo Atualizando pip...
python -m pip install --upgrade pip

echo.

:: Instala dependencias
if exist "requirements.txt" (
    echo Instalando dependencias do requirements.txt...
    pip install -r requirements.txt
) else (
    echo ❌ Arquivo requirements.txt nao encontrado.
    echo Crie o arquivo antes de rodar este setup.
    pause
    exit /b
)

echo.
echo ============================================
echo ✅ SETUP CONCLUIDO COM SUCESSO
echo ============================================
echo.
echo Agora voce pode rodar o sistema com:
echo rodar_wms.bat
echo.
pause