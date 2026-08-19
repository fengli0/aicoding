#!/bin/bash

# AI 短剧生成工作台 - Linux/Mac 启动脚本

echo "======================================"
echo "AI 短剧生成工作台"
echo "======================================"

# Activate virtual environment
source venv/bin/activate

# Check and install backend dependencies
echo "检查后端依赖..."
pip install -q -r backend/requirements.txt

# Start backend in background
echo "启动后端服务 (端口 8000)..."
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "启动前端服务 (端口 5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================"
echo "服务已启动!"
echo "- 前端：http://127.0.0.1:5173"
echo "- 后端 API: http://127.0.0.1:8000"
echo "- API 文档：http://127.0.0.1:8000/docs"
echo "======================================"
echo "按 Ctrl+C 停止所有服务"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
