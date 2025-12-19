#!/usr/bin/env bash
set -e

APP_DIR="/root/build_tools"
VENV="$APP_DIR/.venv"
PYTHON_BIN="$VENV/bin/python"
PIP_BIN="$VENV/bin/pip"

cd "$APP_DIR"

echo "📥 Pulling latest code..."
git fetch origin &&
git checkout main &&
git reset --hard origin/main &&
git pull origin main

# ===============================
# 创建虚拟环境（如果不存在）
# ===============================
if [ ! -x "$PYTHON_BIN" ]; then
    echo "🐍 Creating virtualenv..."
    python3 -m venv "$VENV"
fi

# ===============================
# 安装依赖
# ===============================
echo "📦 Installing requirements..."
"$PIP_BIN" install -r requirements.txt

# ===============================
# 启动服务
# ===============================
echo "🚀 Starting service..."
nohup "$PYTHON_BIN" run.py --all > log 2>&1 &

echo $! > run.pid
echo "✅ Done"
