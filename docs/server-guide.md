# AI 服务资源调度指南

## 服务器概览

| 服务器 | 主机名 | IP | 角色 | GPU | 内存 |
|--------|--------|-----|------|-----|------|
| 153 | ai-compute | 10.19.26.153 | 算力服务器 | Tesla T4 15GB | 32GB |
| 148 | ai-app | 10.19.26.148 | 应用服务器 | 无 | 32GB |

## 服务列表

### 153 算力服务器（有 GPU）

| 服务 | 用途 | 端口 | GPU 占用 | 启动目录 |
|------|------|------|----------|----------|
| PaddleOCR-VL | OCR 文字识别 | 8080 | ~9.4 GB | `/opt/paddleocr-vl/` |
| MinerU | 文档解析 | 8000, 7860 | ~4 GB | `/opt/mineru-server/` |
| Rerank Service | RAG 搜索重排序 | 7997 | ~2 GB | `/opt/rerank-service/` |
| FunASR | 语音识别 (ASR) | 10096 | **无** (CPU) | `/opt/funasr/` |
| CosyVoice | 语音合成 (TTS) | 50000 | ~4 GB | `/opt/cosyvoice/` |
| MetaHuman | 数字人流媒体 | 8001, 8010 | ~6 GB | `/opt/metahuman-stream/` |
| Ollama | LLM 大模型推理 | 11434 | 取决于模型 | systemd 服务 |

### 148 应用服务器（无 GPU）

| 服务 | 用途 | 端口 | 启动目录 |
|------|------|------|----------|
| Fay | 数字人交互 | 5000, 5443 | `/docker/fay/` |
| RAGFlow | RAG 知识库检索 | 19001-19004 | `/opt/ragflow-deploy/docker/` |
| OpenWebUI | AI 对话界面 | 3000 | `/opt/open-webui/` |
| OpenWebUI-Public | AI 对话（公开版） | 3001 | `/opt/openwebui-rag-proxy/` |
| Reception Kiosk | 接待终端 | 18080 | `/opt/reception-kiosk/` |
| Dify | 工作流平台 | 80, 443 | `/opt/dify/docker/` |
| N8N | 自动化工作流 | 5678 | `/opt/n8n-ai-ops/` |
| PDF2Searchable | PDF OCR 双层化 | 9008 ([访问](http://10.19.26.148:9008)) | systemd 服务 |
| Label Studio | 数据标注 | 8080, 9090 | — |
| Doc-Parser | 文档解析 | 8501, 8502 | — |

---

## GPU 资源冲突说明

153 服务器只有一张 **Tesla T4 (15GB)** 显存。当前 OCR 服务已占用约 10GB，剩余约 5GB。

**核心矛盾：多个服务都需要 GPU，但显存不够同时运行。**

| 服务组合 | GPU 需求 | 能否同时运行 |
|----------|----------|-------------|
| 仅 PaddleOCR | ~10 GB | 可以 |
| 仅 MinerU | ~4 GB | 可以 |
| 仅 Ollama (7B 模型) | ~5 GB | 可以 |
| 仅 CosyVoice | ~4 GB | 可以 |
| 仅 MetaHuman | ~6 GB | 可以 |
| PaddleOCR + FunASR | ~10 GB | 可以 (FunASR 不用 GPU) |
| Ollama + FunASR + CosyVoice | ~13 GB | 勉强可以 |
| Ollama + MetaHuman + CosyVoice | ~15 GB | 勉强可以（数字人全栈） |
| PaddleOCR + Ollama | ~15 GB | 勉强，可能 OOM |
| PaddleOCR + MinerU | ~14 GB | 非常紧张 |
| 以上任意三个 GPU 服务 | >15 GB | **不行** |

---

## 应用场景与资源调度

### 场景一：使用数字人

**需要的 153 服务：** Ollama + FunASR + CosyVoice + MetaHuman

**需要关闭的 153 服务：** PaddleOCR、MinerU、Rerank Service

**需要的 148 服务：** Fay + Reception Kiosk

```
153 停掉: PaddleOCR, MinerU, Rerank
153 启动: Ollama, CosyVoice, MetaHuman (FunASR 常驻不动)
148 启动: Fay, Reception Kiosk
```

### 场景二：使用 RAG 知识库 / OpenWebUI 对话

**需要的 153 服务：** Ollama + Rerank Service

**需要关闭的 153 服务：** PaddleOCR、MinerU、CosyVoice、MetaHuman

**需要的 148 服务：** RAGFlow + OpenWebUI (+ 可选 Dify)

```
153 停掉: PaddleOCR, MinerU, CosyVoice, MetaHuman
153 启动: Ollama, Rerank (FunASR 常驻不动)
148 启动: RAGFlow, OpenWebUI
```

### 场景三：使用 OCR 文档识别 / PDF 双层化

**需要的 153 服务：** PaddleOCR + MinerU

**需要关闭的 153 服务：** Ollama、Rerank、CosyVoice、MetaHuman

**需要的 148 服务：** PDF2Searchable（上传 PDF/图片生成可搜索双层 PDF）

**访问地址：** http://10.19.26.148:9008

```
153 停掉: Ollama, Rerank, CosyVoice, MetaHuman
153 启动: PaddleOCR, MinerU (FunASR 常驻不动)
148 启动: PDF2Searchable
```

> 支持上传 PDF、PNG、JPG、TIFF、BMP，OCR 识别后输出带文字层的可搜索 PDF。

### 场景四：使用 Dify 工作流

Dify 运行在 148，不依赖 153 的 GPU 服务。可以和其他场景并行使用。

```
148 启动: Dify (始终可用)
```

---

## 服务开关速查

### 153 算力服务器

```bash
# SSH 连接
ssh root@10.19.26.153

# ---- Ollama (LLM) ----
sudo systemctl start ollama
sudo systemctl stop ollama
sudo systemctl status ollama

# ---- PaddleOCR (OCR) ----
cd /opt/paddleocr-vl && docker compose up -d
cd /opt/paddleocr-vl && docker compose down

# ---- MinerU (文档解析) ----
cd /opt/mineru-server && docker compose --profile api --profile gradio up -d
cd /opt/mineru-server && docker compose down

# ---- Rerank Service ----
cd /opt/rerank-service && docker compose up -d
cd /opt/rerank-service && docker compose down

# ---- FunASR (语音识别, CPU, 常驻) ----
cd /opt/funasr && docker compose up -d
cd /opt/funasr && docker compose down

# ---- CosyVoice (TTS) ----
cd /opt/cosyvoice && docker compose up -d
cd /opt/cosyvoice && docker compose down

# ---- MetaHuman (数字人流媒体) ----
cd /opt/metahuman-stream && docker compose up -d
cd /opt/metahuman-stream && docker compose down
```

### 148 应用服务器

```bash
# SSH 连接
ssh root@10.19.26.148

# ---- Fay (数字人) ----
cd /docker/fay && docker compose up -d
cd /docker/fay && docker compose down

# ---- RAGFlow ----
cd /opt/ragflow-deploy/docker && docker compose up -d
cd /opt/ragflow-deploy/docker && docker compose down

# ---- OpenWebUI ----
cd /opt/open-webui && docker compose up -d
cd /opt/open-webui && docker compose down

# ---- Reception Kiosk ----
cd /opt/reception-kiosk && docker compose -f docker-compose.kiosk.yml up -d
cd /opt/reception-kiosk && docker compose -f docker-compose.kiosk.yml down

# ---- Dify ----
cd /opt/dify/docker && docker compose up -d
cd /opt/dify/docker && docker compose down

# ---- N8N ----
cd /opt/n8n-ai-ops && docker compose up -d
cd /opt/n8n-ai-ops && docker compose down

# ---- PDF2Searchable (systemd 服务，非 docker) ----
systemctl start pdf2searchable
systemctl stop pdf2searchable
systemctl restart pdf2searchable
systemctl status pdf2searchable
journalctl -u pdf2searchable -f          # 实时日志
tail -f /opt/pdf2searchable/server.log   # 也可以看这里
```

---

## 快速检查命令

```bash
# 查看 153 GPU 使用情况
ssh root@10.19.26.153 "nvidia-smi"

# 查看 153 所有运行中的容器
ssh root@10.19.26.153 "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# 查看 148 所有运行中的容器
ssh root@10.19.26.148 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

---

## 常见问题

**Q: Ollama 里有哪些模型？**
A: 已安装 deepseek-r1, qwen2.5, qwen2.5-coder, qwen3, qwen2.5vl, bge-m3, all-minilm, nomic-embed-text-long

**Q: FunASR 需要关吗？**
A: 不需要。FunASR 是 CPU 服务，不占 GPU，可以常驻。Fay 数字人依赖它做语音识别。

**Q: 148 上的服务会互相冲突吗？**
A: 148 没有 GPU，主要是内存和端口冲突。32GB 内存通常够用。如果内存紧张，可以关掉不用的服务。

**Q: 怎么确认某个服务是否在运行？**
A: `docker ps | grep 服务名` 或者访问对应端口看是否有响应。
