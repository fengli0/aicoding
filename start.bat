@echo off
chcp 65001 >nul
title AI 短剧生成工作台

echo ========================================
echo   AI 短剧生成工作台 - 一键启动
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境 venv\Scripts\activate.bat
    echo.
    echo 请先创建虚拟环境并安装依赖：
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r backend\requirements.txt
    echo   cd frontend ^&^& npm install
    echo.
    pause
    exit /b 1
)

echo [1/4] 激活虚拟环境...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败
    pause
    exit /b 1
)

echo [2/4] 检查后端依赖...
python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo [警告] 后端依赖不完整，正在安装...
    pip install -r backend\requirements.txt --quiet
)

echo [3/4] 启动后端服务 (FastAPI :8000)...
start "AI 短剧 - 后端服务" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000"

REM 等待后端启动
echo      等待后端服务启动...
timeout /t 3 /nobreak >nul

echo [4/4] 启动前端服务 (Vite :5173)...
start "AI 短剧 - 前端界面" cmd /k "cd /d %~dp0\frontend && call ..\venv\Scripts\activate.bat && npm run dev"

echo.
echo ========================================
echo   服务启动中...
echo.
echo   后端：http://127.0.0.1:8000
echo   前端：http://127.0.0.1:5173
echo   API 文档：http://127.0.0.1:8000/docs
echo.
echo   按任意键关闭此窗口（不会停止服务）
echo   停止服务请关闭对应的命令行窗口
echo ========================================
echo.

pause >nul
