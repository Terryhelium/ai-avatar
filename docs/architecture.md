# 架构说明

## 整体架构

```
内网PC
  └─ Fay 数字人客户端 (新PVE虚拟机)
       ├── 音视频交互层
       │    ├── ASR: FunASR (10.19.26.153:10096)
       │    ├── TTS: CosyVoice2 (10.19.26.153:50000)
       │    └── 数字人: metahuman-stream (10.19.26.153:8010)
       ├── LLM 推理
       │    └── Ollama (10.19.26.153:11434)
       │         ├── 主模型: Qwen2.5
       │         └── 嵌入模型: bge-m3
       └── Nginx 反向代理
            └── 统一入口
```

## 各服务目录布局 (153)

所有服务统一在 `/opt/` 下各自目录，通过 `docker-compose` 编排：

```
/opt/
├── cosyvoice/          # TTS — CosyVoice2 (FastAPI, 端口 50000)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── app/            # 从 GitHub 克隆的 CosyVoice 源码
│   └── models/         # CosyVoice2-0.5B 模型
│
├── funasr/             # ASR — FunASR (WebSocket, 端口 10096)
│   ├── docker-compose.yml
│   └── models/         # 语音识别模型 (Paraformer, VAD, 标点)
│
├── metahuman-stream/   # 数字人 — metahuman-stream (WebRTC, 端口 8010)
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── mineru-server/      # 文档解析 — MinerU
│   ├── Dockerfile
│   └── compose.yaml
│
└── rerank-service/     # 重排序 — BGE-Reranker (端口 7997)
    └── docker-compose.yml
```

## 算力分配（T4 16GB）

| 服务 | 显存占用 | 调度方式 |
|------|----------|----------|
| Ollama (Qwen2.5) | ~4GB | 按需加载 |
| CosyVoice2 | ~2GB | Docker 常驻 |
| FunASR | ~1GB | Docker 常驻 (CPU 模式) |
| metahuman-stream | ~3.5GB | Docker 常驻 |
| MinerU | ~2GB | Docker 常驻 |

T4 总共 16GB，以上服务不能同时全量运行，显存不足时需分时调度。

## 网络说明

- 服务器位于国内网络，Docker Hub 被墙
- 基础镜像从 `nvcr.io` (NVIDIA) 和阿里云 registry 拉取
- PyPI 使用阿里云镜像 `mirrors.aliyun.com`
- apt 使用阿里云镜像 `mirrors.aliyun.com`
