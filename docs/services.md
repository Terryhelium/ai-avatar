# 服务状态与端口

## 当前分工

### 136

- Nginx Proxy Manager
- 内网导航页
- `avata.nbdag.lan` 入口

### 148

- `reception-kiosk`
- `RAGFlow`

### 153

- `Ollama`
- `FunASR`
- `CosyVoice`
- `metahuman-stream`

## 153 算力服务器

| 服务 | 端口 | 当前状态 | 启动方式 | 备注 |
|------|------|----------|----------|------|
| Ollama | 11434 | ✅ 运行中 | systemd | kiosk 当前调用 `qwen2.5:7b` |
| FunASR | 10096 | ✅ 运行中 | docker-compose | WebSocket ASR |
| CosyVoice | 50000 | ✅ 运行中 | docker-compose | 当前 kiosk 走 `/inference_sft` |
| metahuman-stream offer | 8010 | ✅ 运行中 | docker-compose | WebRTC answer |
| metahuman-stream text ws | 8001 | ✅ 运行中 | docker-compose | 外部应走 `humanecho` |
| MinerU API | 8000 | ✅ 运行中 | compose.yaml | 非 kiosk 主链路 |
| MinerU Gradio | 7860 | ✅ 运行中 | compose.yaml | 非 kiosk 主链路 |
| Rerank | 7997 | ✅ 运行中 | docker-compose | 非 kiosk 主链路 |

## 148 应用服务器

| 服务 | 端口 | 当前状态 | 备注 |
|------|------|----------|------|
| reception-kiosk | 18080 | ✅ 运行中 | 对外主入口经 `136` 反代 |
| RAGFlow retrieval | 19003 | ✅ 可用但偶发 OOM | `POST /api/v1/retrieval` |

## 136 基础设施服务器

| 服务 | 状态 | 备注 |
|------|------|------|
| Nginx Proxy Manager | ✅ | `avata.nbdag.lan -> 10.19.26.148:18080` |
| 内网导航卡片 | ✅ | 标题为 `AI数字人` |

## 关键地址

- 正式入口：`https://avata.nbdag.lan`
- kiosk 直连：`http://10.19.26.148:18080`
- RAGFlow：`http://10.19.26.148:19003/api/v1/retrieval`
- Ollama：`http://10.19.26.153:11434/v1/chat/completions`
- CosyVoice：`http://10.19.26.153:50000/inference_sft`
- FunASR：`ws://10.19.26.153:10096`
- metahuman offer：`http://10.19.26.153:8010/offer`
- metahuman text push：`ws://10.19.26.153:8001/humanecho`

## 管理命令

```bash
# 153 上查看容器
docker ps

# 单服务控制
cd /opt/<service> && docker compose up -d
cd /opt/<service> && docker compose down
cd /opt/<service> && docker compose logs -f

# 148 上重建 kiosk
cd /opt/reception-kiosk
docker compose -f docker-compose.kiosk.yml up -d --build

# 查看 GPU 占用
nvidia-smi
```

## 当前已知问题

### RAGFlow

- 能正常返回检索结果
- 但偶发 OOM
- 错误表现可能是：
  - `code:100`
  - `cudaMalloc failed: out of memory`

### metahuman-stream

- WebRTC 画面能出
- 文本推送已改为 `humanecho`
- 当前嘴型问题还没完全修完
- 剩余问题集中在 `tts='cosyvoice'` 初始化
