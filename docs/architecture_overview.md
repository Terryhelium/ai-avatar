# ai-avatar 数字人系统架构方案

## 一、系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户交互层                                    │
│  内网PC / 手机 / 浏览器 (WebRTC / HTTP)                             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  136 基础设施服务器                                                  │
│  ┌────────────────────────────────────────────────────┐             │
│  │  Nginx Proxy Manager (80/81/443)                   │             │
│  │  统一入口，按域名转发请求                             │             │
│  └────────────────────────────────────────────────────┘             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────────┐
          ▼                ▼                    ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ 148 应用服务     │ │ 136 基础设施 │ │ 153 算力服务      │
│                 │ │             │ │                  │
│ Fay 数字人客户端 │ │ Gitea/Nexus │ │ FunASR (ASR)     │
│ RAGFlow (19003) │ │ Semaphore   │ │ CosyVoice (TTS)  │
│ Dify (80/443)   │ │ Dootask     │ │ Ollama (LLM)     │
│ n8n (5678)      │ │ Docmost     │ │ metahuman-stream │
│ Open-WebUI(3000)│ │ Snipe-IT    │ │ MinerU (文档)    │
│ Label Studio    │ │ ELK/Zabbix  │ │ Rerank (重排序)  │
└─────────────────┘ └──────────────┘ └──────────────────┘
```

## 二、Fay 为核心的数据流

```
用户语音输入
    │
    ▼
┌──────────────┐     ┌─────────────────┐
│ Fay 客户端    │────▶│ FunASR (ASR)    │
│ (148)         │     │ 153:10096       │
│ 接收语音/文字  │     │ 语音→文本       │
└──────────────┘     └────────┬────────┘
         ▲                    │ 文本
         │                    ▼
         │            ┌─────────────────┐
         │            │ Ollama (LLM)    │
         │            │ 153:11434       │
         │            │ 理解+生成回复    │
         │            └────────┬────────┘
         │                    │ 回复文本
         │                    ▼
         │            ┌─────────────────┐
         │            │ CosyVoice (TTS) │
         │            │ 153:50000       │
         │            │ 文本→语音       │
         │            └────────┬────────┘
         │                    │ 音频流
         │                    ▼
         │            ┌─────────────────┐
         │            │ metahuman-stream│
         │            │ 153:8010        │
         │            │ 数字人渲染       │
         │            │ (WebRTC推流)    │
         │            └────────┬────────┘
         │                    │ 视频+音频
         └────────────────────┘
            Fay 展示数字人画面
```

## 三、服务部署拓扑

### 3.1 153（算力服务器）
| 服务 | 类型 | 端口 | 显存 | 状态 |
|------|------|:----:|:----:|:----:|
| FunASR | Docker | 10096 | ~1GB | ✅ |
| Ollama | Systemd | 11434 | ~4GB | ✅ |
| MinerU | Docker | 8000/7860 | ~2GB | ✅ |
| Rerank | Docker | 7997 | ~1GB | ✅ |
| CosyVoice | **Docker** | 50000 | ~2GB | 🔄 |
| metahuman-stream | Docker | 8001/8010 | ~3.5GB | ✅ |

### 3.2 148（应用服务器）
| 服务 | 端口 | 说明 |
|------|:----:|------|
| Dify | 80/443 | AI 应用平台 |
| RAGFlow | 19001-19004 | 知识库 + 文档问答 |
| n8n | 5678 | 工作流自动化 |
| Open-WebUI | 3000 | LLM 对话界面 |
| **Fay** | 5000/10001-10003 | 数字人客户端 |

### 3.3 网络拓扑
```
内网用户 → 148:5000 (Fay管理界面)
         → 148:10001 (Fay音频桥接)
         → 148:10002 (Fay数字人接口)
         → 148:10003 (Fay控制接口)
                 ↓
         Fay调用 → 153 各服务 (容器间直连)
```

## 四、CosyVoice Docker 方案历程

### 4.1 遇到的障碍
| # | 问题 | 根因 |
|---|------|------|
| 1 | torchaudio 版本冲突 | 基础镜像已含 torch，Dockerfile 又显式安装导致冲突 |
| 2 | pkg_resources 缺失 | setuptools≥82 移除了 pkg_resources，降级到 69.5.1 |
| 3 | 阿里云镜像超时 | onnxruntime-gpu(199MB) 反反复复 Read timed out |
| 4 | g++ 缺失 | pyworld 编译需要 g++，基础镜像不含 |
| 5 | transformers 版本不兼容 | 新版需要 torch.compiler（torch≥2.1） |
| 6 | Docker Hub / PyTorch 被墙 | 国内网络问题，华为云中转解决 |

### 4.2 最终方案
```
基础镜像: harryliu888/cosyvoice (华为云拉取)
   ├── PyTorch 2.1.0 + CUDA 预装 ✅
   ├── spk2info.pt 预置 ✅
   └── CosyVoice SDK 预装 ✅
追加:
   ├── g++ (编译 pyworld) ✅
   ├── setuptools 69.5.1 (兼容 pkg_resources) ✅
   ├── 全部 Python 依赖 (from requirements_filtered.txt) ✅
   └── API server (runtime/python/fastapi/server.py) ✅
```

## 五、配置参考

### 5.1 Fay 关键配置 (system.conf)
```ini
ASR_mode = funasr
local_asr_ip = 10.19.26.153
local_asr_port = 10096
chat_module = chatgpt
```

### 5.2 CosyVoice docker-compose.yml
```yaml
services:
  cosyvoice:
    image: cosyvoice:prod
    ports: ["50000:50000"]
    volumes:
      - /opt/cosyvoice/models:/data/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

## 六、显存预算（T4 16GB）
| 服务 | 显存 | 说明 |
|------|:----:|------|
| Ollama (Qwen2.5) | ~4GB | 按需加载 |
| metahuman-stream | ~3.5GB | Docker 常驻 |
| CosyVoice | ~2GB | Docker 常驻 |
| MinerU | ~2GB | Docker 常驻 |
| FunASR | ~1GB | CPU 模式 |
| **合计** | **~12.5GB** | 余 ~3.5GB |
