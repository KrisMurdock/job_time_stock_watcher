#!/usr/bin/env bash
# stock_watcher — A-share & HK real-time stock price monitor
# Usage: ./run.sh [config.yaml]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${1:-$SCRIPT_DIR/config.yaml}"

if [ ! -f "$CONFIG" ]; then
    echo "错误: 配置文件不存在: $CONFIG"
    exit 1
fi

cd "$SCRIPT_DIR"
exec python3 -m stock_watcher.app "$CONFIG"
