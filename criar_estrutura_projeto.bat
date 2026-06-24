@echo off
setlocal

:: Entra na pasta onde este arquivo .bat está salvo
cd /d "%~dp0"

:: Cria as pastas principais do projeto
mkdir credenciais 2>nul
mkdir paginas 2>nul
mkdir funcoes_compartilhadas 2>nul
mkdir imagens 2>nul
mkdir .streamlit 2>nul

:: Cria também a pasta de backup, que é útil no padrão do projeto
mkdir z_backup 2>nul

:: Cria o arquivo de configuração do Streamlit, se ainda não existir
if not exist ".streamlit\config.toml" (
    echo runOnSave = true > ".streamlit\config.toml"
)

:: Cria o arquivo .env dentro da pasta credenciais, se ainda não existir
if not exist "credenciais\.env" (
    (
        echo SUPABASE_URL=https://SEU-PROJETO.supabase.co
        echo SUPABASE_KEY=SUA_CHAVE_ANON
    ) > "credenciais\.env"
)

:: Cria o arquivo requirements.txt, se ainda não existir
if not exist "requirements.txt" (
    (
        echo streamlit
        echo pandas
        echo supabase
        echo python-dotenv
    ) > "requirements.txt"
)

:: Cria arquivos __init__.py para garantir que as pastas funcionem como módulos Python
if not exist "paginas\__init__.py" (
    type nul > "paginas\__init__.py"
)

if not exist "funcoes_compartilhadas\__init__.py" (
    type nul > "funcoes_compartilhadas\__init__.py"
)

:: Mensagem final para o usuário
echo.
echo ============================================
echo Estrutura inicial do projeto criada com sucesso.
echo ============================================
echo.
echo Pastas criadas:
echo - credenciais
echo - paginas
echo - funcoes_compartilhadas
echo - imagens
echo - .streamlit
echo - z_backup
echo.
echo Arquivos criados, se nao existiam:
echo - .streamlit\config.toml
echo - credenciais\.env
echo - requirements.txt
echo - paginas\__init__.py
echo - funcoes_compartilhadas\__init__.py
echo.
pause