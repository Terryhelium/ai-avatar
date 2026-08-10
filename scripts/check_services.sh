#!/bin/bash
echo "════════════════════════════════"
echo "  ai-avatar 服务巡检"
echo "════════════════════════════════"

check_http() {
    local name=$1 url=$2
    if curl -sf "$url" -o /dev/null --max-time 3; then
        echo "✅ $name ($url)"
    else
        echo "❌ $name ($url) — 无响应"
    fi
}

check_ws_port() {
    local name=$1 port=$2
    if ss -tlnp | grep -q ":$port "; then
        echo "✅ $name (ws://localhost:$port) — WebSocket 端口监听中"
    else
        echo "❌ $name — 端口 $port 未监听"
    fi
}

check_docker() {
    local name=$1
    if docker ps --format '{{.Names}}' | grep -q "^$name$"; then
        echo "✅ Docker: $name"
    else
        echo "❌ Docker: $name — 未运行"
    fi
}

echo ""
echo "── HTTP 接口 ──"
check_http "Ollama LLM"      "http://localhost:11434/api/tags"
check_http "CosyVoice TTS"   "http://localhost:50000/docs"
check_http "metahuman-stream" "http://localhost:8010"
check_http "MinerU API"      "http://localhost:8000/docs"

echo ""
echo "── WebSocket 端口 ──"
check_ws_port "FunASR" "10096"

echo ""
echo "── Docker 容器 ──"
check_docker "funasr"
check_docker "cosyvoice"
check_docker "metahuman"
check_docker "mineru-api"
check_docker "mineru-gradio"
check_docker "rerank-service"

echo ""
echo "── GPU 状态 ──"
nvidia-smi --query-gpu=name,memory.used,memory.free,utilization.gpu,temperature.gpu \
  --format=csv,noheader,nounits | \
  awk -F',' '{printf "型号:%-10s 显存已用:%sMB 空闲:%sMB GPU利用率:%s%% 温度:%s°C\n",$1,$2,$3,$4,$5}'

echo ""
echo "巡检完成 $(date '+%Y-%m-%d %H:%M:%S')"
