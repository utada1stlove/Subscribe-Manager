#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

# 首次运行时自动创建 venv 并安装依赖
if [ ! -d "$VENV" ]; then
  echo "初始化虚拟环境…"
  python -m venv "$VENV"
  "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

exec "$VENV/bin/python" "$SCRIPT_DIR/web.py"
