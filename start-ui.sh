#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PARADOX_COURT_PORT:-8777}"
URL="http://127.0.0.1:${PORT}/index.html"

cd "$SCRIPT_DIR"

# 未配置 DeepSeek API Key 时提示用户；服务仍可启动，使用内置模板兜底
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "⚠️  未检测到 DEEPSEEK_API_KEY，将使用内置模板兜底（无模型推理）。"
  echo "   启用 AI 审判：export DEEPSEEK_API_KEY=你的密钥 后重新运行本脚本。"
fi

python3 server.py >/tmp/paradox-court-ui.log 2>&1 &
SERVER_PID=$!

sleep 1

# 自动打开浏览器：macOS 用 open，Linux 用 xdg-open，都没有就只打印地址
if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
fi

printf 'Paradox Court UI: %s\n' "$URL"
printf 'Backend: DeepSeek AI via /api/trial/run, with template fallback\n'
printf 'Press Ctrl+C to stop the local server.\n'

trap 'kill "$SERVER_PID" >/dev/null 2>&1 || true' EXIT INT TERM
wait "$SERVER_PID"
