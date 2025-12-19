#!/usr/bin/env bash

PID=$(ps aux | grep "python run.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
  echo "⚠️ Service not running"
  exit 0
fi

echo "🛑 Stopping service PID=$PID"
kill "$PID"
