@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] 安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [2/3] 打包 exe...
python -m PyInstaller --noconfirm --clean ^
  --onefile ^
  --windowed ^
  --name DrinkRemind ^
  --add-data "config.json;." ^
  drink_remind.py
if errorlevel 1 exit /b 1

echo [3/3] 复制默认配置到 dist...
if not exist "dist\config.json" copy /Y "config.json" "dist\config.json" >nul

echo.
echo 完成：dist\DrinkRemind.exe
echo 首次运行会写入开机自启动，并在同目录生成/读取 config.json
pause
