#!/usr/bin/env bash
set -e

APP_DIR="/root/build_tools"
VENV="$APP_DIR/.venv"
PYTHON_BIN="$VENV/bin/python"
PIP_BIN="$VENV/bin/pip"

cd "$APP_DIR"

echo "📥 Syncing code (force overwrite)..."
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
# 创建虚拟环境（用 mamba / conda python）
# ===============================
if [ ! -x "$PYTHON_BIN" ]; then
    echo "🐍 Creating virtualenv..."
    PYTHON_SYS="/opt/mamba/bin/python"
    "$PYTHON_SYS" -m venv "$VENV"
fi

# ===============================
# 安装依赖（只装到 venv）
# ===============================
echo "📦 Installing requirements..."
"$PIP_BIN" install --upgrade pip
"$PIP_BIN" install -r requirements.txt

# ===============================
# 启动服务
# ===============================
echo "🚀 Starting service..."
nohup "$PYTHON_BIN" run.py --all > log 2>&1 &

echo $! > run.pid
echo "✅ Done"
