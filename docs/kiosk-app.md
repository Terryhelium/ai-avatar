# Kiosk 独立应用说明

## 目标

将接待机应用从历史 Fay 路线中拆出，形成一套独立的 kiosk 应用：

- `148` 跑页面与轻后端编排
- `153` 只提供模型与数字人服务
- `136` 提供统一 HTTPS 入口

## 当前入口

- 正式入口：`https://avata.nbdag.lan`
- `148` 直连地址：`http://10.19.26.148:18080`

说明：

- 浏览器录音需要安全上下文，因此日常联调应优先走 `HTTPS` 入口。

## 当前架构

```text
浏览器
  -> reception-kiosk
  -> RAGFlow (148)
  -> Ollama (153)
  -> CosyVoice (153)
  -> metahuman-stream (153)
```

语音链路为：

```text
浏览器录音
  -> /api/voice-chat
  -> FunASR (153)
  -> RAGFlow (148)
  -> Ollama (153)
  -> CosyVoice (153)
  -> metahuman-stream (153)
```

## 当前已实现

- 文本提问
- 数字人居中主画面布局
- 调试抽屉
- 服务状态 badge
- 知识库来源状态面板
- WebRTC 连接数字人
- 回答文本同步推送到数字人
- `voice-chat` 后端接口
- `FunASR` WebSocket 调用
- `retrieval_status` / `retrieval_detail` 返回

## 当前接口

### 页面

- `GET /`

### 健康检查

- `GET /api/health`

### 文本问答

- `POST /api/chat`

返回关键字段：

- `answer`
- `audio_base64`
- `audio_mime_type`
- `retrieval_chunks`
- `retrieval_status`
- `retrieval_detail`
- `timings_ms`
- `metahuman_dispatched`

### 语音问答

- `POST /api/voice-chat`

表单字段：

- `audio`
- `history`
- `synthesize_audio`

### 数字人 WebRTC

- `POST /api/metahuman/offer`

## 2026-06-03 已确认结果

- `/api/chat` 已在线返回过知识库命中结果。
- 一次实测结果为：
  - `retrieval_status: "hit"`
  - `ragflow: 3372ms`
  - `ollama: 6826ms`
  - `cosyvoice: 14078ms`
  - `metahuman: 17ms`

说明当前：

- kiosk 编排层可用
- 知识库链路可用
- TTS 返回可用
- 数字人文本分发也已成功到达下游

## 已修正的问题

### 1. 录音权限

- 之前浏览器会提示不支持录音，本质是因为使用了 `http`。
- 现已切到 `https://avata.nbdag.lan`。

### 2. 知识库误报“未命中”

- 之前前端只看 `retrieval_chunks.length === 0`。
- 现在已区分：
  - `hit`
  - `miss`
  - `error`
  - `disabled`
- 因此可以明确区分：
  - 真未命中
  - 检索服务失败
  - 未配置

### 3. 数字人推送目标错误

- 之前默认推送到：
  - `ws://10.19.26.153:8001/humanchat`
- 该路由会再次触发数字人容器内部 LLM。
- 当前已改为：
  - `ws://10.19.26.153:8001/humanecho`
- 这样 kiosk 直接把已经生成好的文本送去播报，不再多绕一层内部问答。

## 当前剩余问题

### 1. 数字人嘴型还没最终恢复

- `153` 上 `metahuman-stream` 仍有剩余错误：
  - `AttributeError: 'LipReal' object has no attribute 'tts'`
- 当前已知方向：
  - 运行参数使用了 `tts='cosyvoice'`
  - `lipreal.py` 没有对应初始化分支

### 2. RAGFlow 偶发 OOM

- 已实际抓到过上游返回：
  - `code:100`
  - `cudaMalloc failed: out of memory`
- 因此知识库不稳定时，不能简单判断成“没命中”。

### 3. 数字人画面还可以继续微调

- 当前布局已经比早期左右分栏明显更适合 kiosk。
- 但人物构图与视觉距离仍可能需要继续调。

## 当前配置重点

`.env` 里的关键项：

```env
RAGFLOW_URL=http://10.19.26.148:19003/api/v1/retrieval
OLLAMA_URL=http://10.19.26.153:11434/v1/chat/completions
COSYVOICE_URL=http://10.19.26.153:50000/inference_sft
FUNASR_WS_URL=ws://10.19.26.153:10096
METAHUMAN_OFFER_URL=http://10.19.26.153:8010/offer
METAHUMAN_WS_URL=ws://10.19.26.153:8001/humanecho
```

## 运行方式

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn kiosk_app.main:app --host 0.0.0.0 --port 18080
```

或：

```bash
cp .env.example .env
docker compose -f docker-compose.kiosk.yml up -d --build
```

## 当前部署位置

### 148

- 路径：`/opt/reception-kiosk`
- Compose：`docker-compose.kiosk.yml`
- 容器：`reception-kiosk-reception-kiosk-1`

### 136

- 域名：`avata.nbdag.lan`
- 反代目标：`10.19.26.148:18080`

## 下一步

1. 修 `153` 上数字人 `tts='cosyvoice'` 初始化问题
2. 回归验证录音问答闭环
3. 继续观察 RAGFlow OOM 触发条件
4. 再做数字人构图与 UI 收尾
