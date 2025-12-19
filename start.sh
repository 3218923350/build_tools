#!/usr/bin/env bash
set -e

APP_DIR="/root/build_tools"


cd "$APP_DIR"

echo "📥 Pulling latest code..."
git fetch origin
git checkout main
git reset --hard origin/main

# ===============================
# 停旧服务
# ===============================
if [ -f run.pid ] && kill -0 "$(cat run.pid)" 2>/dev/null; then
    echo "🛑 Stopping old process"
    kill "$(cat run.pid)"
    sleep 2
fi



# ===============================
# 安装依赖（必须用 venv 的 pip）
# ===============================
echo "📦 Installing requirements..."
pip install -r requirements.txt

# ===============================
# 启动服务
# ===============================
echo "🚀 Starting service..."
nohup /opt/mamba/bin/python run.py --all > log 2>&1 &

echo $! > run.pid
echo "✅ Done"
