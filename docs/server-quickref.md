# 服务开关速查卡

> 153 = 算力服务器 (GPU) | 148 = 应用服务器 (无GPU)
> FunASR (语音识别) 常驻不动，不用管它

---

## 用数字人

**153 关掉：** PaddleOCR、MinerU、Rerank
**153 启动：** Ollama、CosyVoice、MetaHuman
**148 启动：** Fay、Reception Kiosk

```bash
# === 153 ===
cd /opt/paddleocr-vl && docker compose down
cd /opt/mineru-server && docker compose down
cd /opt/rerank-service && docker compose down
sudo systemctl start ollama
cd /opt/cosyvoice && docker compose up -d
cd /opt/metahuman-stream && docker compose up -d

# === 148 ===
cd /docker/fay && docker compose up -d
cd /opt/reception-kiosk && docker compose -f docker-compose.kiosk.yml up -d
```

---

## 用 RAG / OpenWebUI 对话

**153 关掉：** PaddleOCR、MinerU、CosyVoice、MetaHuman
**153 启动：** Ollama、Rerank
**148 启动：** RAGFlow、OpenWebUI

```bash
# === 153 ===
cd /opt/paddleocr-vl && docker compose down
cd /opt/mineru-server && docker compose down
cd /opt/cosyvoice && docker compose down
cd /opt/metahuman-stream && docker compose down
sudo systemctl start ollama
cd /opt/rerank-service && docker compose up -d

# === 148 ===
cd /opt/ragflow-deploy/docker && docker compose up -d
cd /opt/open-webui && docker compose up -d
```

---

## 用 OCR 文档识别 / PDF 双层化

**153 关掉：** Ollama、Rerank、CosyVoice、MetaHuman
**153 启动：** PaddleOCR、MinerU
**148 启动：** PDF2Searchable
**访问：** http://10.19.26.148:9008

```bash
# === 153 ===
sudo systemctl stop ollama
cd /opt/rerank-service && docker compose down
cd /opt/cosyvoice && docker compose down
cd /opt/metahuman-stream && docker compose down
cd /opt/paddleocr-vl && docker compose up -d
cd /opt/mineru-server && docker compose --profile api --profile gradio up -d

# === 148 ===
systemctl start pdf2searchable
```

---

## 查看状态

```bash
# GPU 使用
ssh root@10.19.26.153 "nvidia-smi"

# 153 容器
ssh root@10.19.26.153 "docker ps"

# 148 容器
ssh root@10.19.26.148 "docker ps"

# PDF2Searchable 状态/日志
systemctl status pdf2searchable
tail -f /opt/pdf2searchable/server.log
```
