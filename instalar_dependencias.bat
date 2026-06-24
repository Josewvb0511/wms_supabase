@echo off
:: Entra na pasta onde este arquivo está
cd /d C:\Users\Faturamento\Downloads\wms_supabase

:: Ativa o ambiente virtual
call .venv\Scripts\activate

:: Instala tudo que está no requirements.txt
pip install -r requirements.txt

:: Pausa a tela para você ver se deu certo
pause