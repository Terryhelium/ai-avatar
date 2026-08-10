#!/bin/bash
PID_FILE=/var/run/cosyvoice.pid

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null && echo "✅ CosyVoice 已停止 (PID $PID)" || echo "进程不存在"
    rm -f "$PID_FILE"
else
    pkill -f "server.py.*50000" 2>/dev/null && echo "✅ 已终止" || echo "未找到运行中的进程"
fi
