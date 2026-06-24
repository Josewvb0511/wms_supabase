@echo off
chcp 65001 >nul
echo.
echo ====================================
echo Atualizando WMS no GitHub...
echo ====================================
echo.

git add .
if errorlevel 1 (
    echo Erro ao adicionar arquivos!
    pause
    exit /b 1
)

git commit -m "Atualização do WMS"
if errorlevel 1 (
    echo Nenhuma mudança para fazer commit
    pause
    exit /b 1
)

git push
if errorlevel 1 (
    echo Erro ao fazer push!
    pause
    exit /b 1
)

echo.
echo ====================================
echo ✓ WMS atualizado com sucesso!
echo ✓ O app online vai atualizar em ~30-60 segundos
echo ====================================
echo.
pause