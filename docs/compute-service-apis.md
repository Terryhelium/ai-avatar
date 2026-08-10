# 算力接口调用说明

这份文档给需要单独接入 `153` 算力服务或自己搭前端/数字人的同事使用。

## 机器分工

### 153

算力与数字人服务：

- `Ollama`
- `CosyVoice`
- `FunASR`
- `metahuman-stream`

### 148

知识库与 kiosk 编排：

- `RAGFlow`
- `reception-kiosk`

### 136

入口代理：

- `https://avata.nbdag.lan`

## 推荐接法

如果只是想快速联调，优先接 `148` 的统一 kiosk API：

- `POST /api/chat`
- `POST /api/voice-chat`
- `POST /api/metahuman/offer`

如果是自己写前端、自己串链路，再直接调下面这些原始服务。

## 1. RAGFlow 检索

### 地址

- `http://10.19.26.148:19003/api/v1/retrieval`

### 说明

- 方法：`POST`
- 认证：`Authorization: Bearer <token>`
- 需要：
  - `question`
  - `dataset_ids`
  - `top_k`

### 请求示例

```bash
curl -X POST http://10.19.26.148:19003/api/v1/retrieval \
  -H 'Authorization: Bearer <RAGFLOW_TOKEN>' \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "question": "请介绍档案馆接待服务",
    "dataset_ids": ["<DATASET_ID>"],
    "top_k": 3
  }'
```

### 返回关注点

- `code == 0` 代表成功
- `data.chunks` 为检索结果

### 注意

- 这个服务目前偶发 OOM
- 失败时可能返回：
  - `code: 100`
  - `cudaMalloc failed: out of memory`

## 2. Ollama 对话

### 地址

- `http://10.19.26.153:11434/v1/chat/completions`

### 说明

- 兼容 OpenAI 风格 chat completions
- 当前 kiosk 使用模型：
  - `qwen2.5:7b`

### 请求示例

```bash
curl -X POST http://10.19.26.153:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "model": "qwen2.5:7b",
    "messages": [
      {"role": "system", "content": "你是接待助手。"},
      {"role": "user", "content": "请介绍档案馆接待服务"}
    ],
    "temperature": 0.3,
    "max_tokens": 800
  }'
```

## 3. CosyVoice 语音合成

### 地址

- `http://10.19.26.153:50000/inference_sft`

### 说明

- 方法：`POST`
- 表单方式提交
- 当前 kiosk 默认参数：
  - `tts_text`
  - `spk_id=中文女`

### 请求示例

```bash
curl -X POST http://10.19.26.153:50000/inference_sft \
  -F 'tts_text=欢迎来到档案馆，请问您想了解什么？' \
  -F 'spk_id=中文女' \
  --output cosyvoice_output.pcm
```

### 返回说明

- 当前返回的是原始 PCM 字节流
- kiosk 侧会再包成 WAV 后给浏览器播放

## 4. FunASR 语音识别

### 地址

- `ws://10.19.26.153:10096`

### 说明

- WebSocket 协议
- kiosk 当前用的是离线模式
- 音频需转为：
  - 16k
  - 单声道
  - PCM16LE

### 首包示例

```json
{
  "mode": "offline",
  "chunk_size": [0, 10, 5],
  "encoder_chunk_look_back": 4,
  "decoder_chunk_look_back": 1,
  "chunk_interval": 10,
  "wav_name": "microphone",
  "is_speaking": true
}
```

### 结束包

```json
{
  "is_speaking": false
}
```

### 注意

- 中间要按 chunk 连续发送 PCM 二进制数据
- 最终返回里关注 `text`

## 5. metahuman-stream WebRTC

### offer 地址

- `http://10.19.26.153:8010/offer`

### 说明

- 浏览器先创建本地 WebRTC offer
- 将 `sdp` 和 `type` 提交到该接口
- 返回 answer 后设置远端描述

### 请求示例

```bash
curl -X POST http://10.19.26.153:8010/offer \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "sdp": "<YOUR_SDP>",
    "type": "offer"
  }'
```

## 6. metahuman 文本推送

### 正确入口

- `ws://10.19.26.153:8001/humanecho`

### 用法

- WebSocket 连接后，直接发送已经生成好的播报文本
- 这是当前 kiosk 正在使用的入口

### 重要说明

不要用：

- `ws://10.19.26.153:8001/humanchat`

原因：

- `humanchat` 会让数字人容器自己再走一遍内部 LLM
- 当前该路由会触发依赖问题，不适合作为外部系统的播报入口

## 7. 统一 kiosk API

如果不想自己拼链路，直接调用 kiosk 即可。

### 地址

- `https://avata.nbdag.lan`

### 文本问答

```bash
curl -X POST https://avata.nbdag.lan/api/chat \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "question": "请介绍档案馆接待服务",
    "history": [],
    "synthesize_audio": true
  }'
```

### 语音问答

```bash
curl -X POST https://avata.nbdag.lan/api/voice-chat \
  -F 'audio=@recording.wav' \
  -F 'history=[]' \
  -F 'synthesize_audio=true'
```

### 返回字段

- `answer`
- `audio_base64`
- `audio_mime_type`
- `retrieval_chunks`
- `retrieval_status`
- `retrieval_detail`
- `timings_ms`
- `metahuman_dispatched`

## 8. 当前已知问题

### RAGFlow

- 偶发 OOM
- 失败不等于未命中

### metahuman-stream

- 画面能出
- 文本能推
- 但嘴型链路仍有剩余问题
- 当前卡点是 `tts='cosyvoice'` 时容器内部 `tts` 初始化不完整

### 录音

- 浏览器端必须走 HTTPS

## 9. 联调建议

最省事的顺序：

1. 先调 `Ollama`
2. 再调 `CosyVoice`
3. 再调 `RAGFlow`
4. 再连 `metahuman offer`
5. 最后接 `humanecho`

如果只是想快速出一个能演示的页面，直接调：

- `https://avata.nbdag.lan/api/chat`

即可。
