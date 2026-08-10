#!/bin/bash
set -e

VENV=/opt/cosyvoice/venv
APP=/opt/cosyvoice/app
MODEL=/opt/cosyvoice/models/CosyVoice2-0.5B
LOG=/var/log/cosyvoice.log
PID_FILE=/var/run/cosyvoice.pid

# 检查是否已在运行
if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
    echo "⚠️  CosyVoice 已在运行，PID: $(cat $PID_FILE)"
    exit 0
fi

echo "启动 CosyVoice..."
source "$VENV/bin/activate"
nohup python "$APP/runtime/python/fastapi/server.py" \
    --port 50000 \
    --model_dir "$MODEL" \
    > "$LOG" 2>&1 &

echo $! > "$PID_FILE"
echo "CosyVoice 已启动，PID: $!, 日志: $LOG"
echo "等待模型加载（约 15 秒）..."
sleep 15
curl -sf http://localhost:50000/docs -o /dev/null \
    && echo "✅ 服务就绪" \
    || echo "❌ 服务未响应，查日志: tail -30 $LOG"
