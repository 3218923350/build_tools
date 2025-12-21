#!/usr/bin/env bash
set -euo pipefail

PREFIX="registry.dp.tech/davinci"
SUCCESS=0
FAIL=0

echo "[INFO] Host: $(hostname)"

# 找出符合前缀的镜像（repo:tag）
IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep "^${PREFIX}/" || true)

if [ -z "$IMAGES" ]; then
  echo "[INFO] No davinci images found"
  echo "PUSH_OK=0 PUSH_FAIL=0"
  exit 0
fi

for img in $IMAGES; do
  echo "[PUSH] $img"
  if docker push "$img"; then
    SUCCESS=$((SUCCESS + 1))
  else
    echo "[ERROR] push failed: $img" >&2
    FAIL=$((FAIL + 1))
  fi
done

echo "PUSH_OK=${SUCCESS} PUSH_FAIL=${FAIL}"
