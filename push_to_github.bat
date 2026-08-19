@echo off
chcp 65001 > nul
echo ========================================================
echo   ⚡ Lossless Studio - Отправка на GitHub для сборки APK
echo ========================================================
echo.
set /p REPO_URL="Вставьте ссылку на ваш GitHub репозиторий (например, https://github.com/USER/repo.git): "

if "%REPO_URL%"=="" (
    echo [Ошибка] Ссылка не введена.
    pause
    exit /b
)

git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main
echo.
echo Отправка файлов в репозиторий...
git push -u origin main

echo.
echo ========================================================
echo ✓ Файлы успешно отправлены на GitHub!
echo Сборка APK началась автоматически.
echo Откройте вкладку "Actions" в вашем репозитории на GitHub,
echo чтобы скачать готовый файл LosslessStudio.apk.
echo ========================================================
pause
