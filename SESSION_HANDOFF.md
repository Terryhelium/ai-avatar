# SESSION HANDOFF

## 2026-06-04 进展

- 已修 `153` 上 `metahuman-stream` 的启动热补丁脚本：
  - 之前脚本只给 `ttsreal.py` 追加了 `CosyVoiceTTS`
  - 但没有把修改后的 `lipreal.py` 写回文件
  - 导致运行时持续报：
    - `AttributeError: 'LipReal' object has no attribute 'tts'`
- 已新增仓库脚本：
  - `scripts/init_metahuman.py`
  - `scripts/patch_metahuman_compose.py`
- 已把修复后的脚本部署到 `153:/opt/metahuman-stream`
- 已更新 `docker-compose.yml` 里的内嵌 base64 启动补丁
- 已重建容器：
  - `metahuman`
- 已验证：
  - 容器内 `lipreal.py` 已出现：
    - `from ttsreal import EdgeTTS,VoitsTTS,XTTS,CosyVoiceTTS`
    - `elif opt.tts == "cosyvoice":`
  - 容器内 `CosyVoiceTTS` 可直接调用 `inference_sft`
  - 已确认 `inference_sft` 返回的是原始 PCM，不是 WAV
  - 已把补丁实现改为 `numpy.frombuffer(..., dtype=int16)` 解码，而不是 `soundfile.read(...)`
- 当前结论：
  - `self.tts` 初始化缺失问题已修
  - CosyVoice 原始 PCM 解码路径已单独 smoke test 通过
- `148` 上 `voice-chat` 也已补一轮修复并上线：
  - 容器镜像已安装 `ffmpeg`
  - `audio_to_pcm16le()` 已支持对 `16-bit PCM WAV` 做本地重采样
  - 音频预处理失败现在会返回 `502`，不再裸报 `500`
- 已完成的后端闭环验证：
  - `POST /api/chat`：
    - `metahuman_dispatched: true`
  - `POST /api/voice-chat`（浏览器等价的 `16k WAV`）：
    - 成功识别原句
    - 成功返回回答
    - `metahuman_dispatched: true`
  - `POST /api/voice-chat`（`22050 WAV`）：
    - 现已可直接处理
  - 错误音频：
    - 现返回 `502` 和明确错误详情
- 现在剩下的主要是浏览器真机确认：
  - WebRTC 连接
  - 页面录音
  - 数字人实际嘴型观感
- 已补一版新的临时演示数字人形象：
  - 源图：Pexels `28217403`
  - 方式：静态正装东方面孔图片生成 `wav2lip` avatar
  - 生成结果：`200` 帧 `full_imgs` + `200` 帧 `face_imgs`
  - 当前运行中的 `wav2lip_avatar1` 已被临时替换
  - 额外备份在：
    - `153:/opt/metahuman-stream/custom_avatars/pexels_28217403`
- 已确认浏览器现在能重新看到数字人画面。
- 但最新现场观感是：
  - 会说话
  - 嘴部发糊
  - 更像 `wav2lip` 局部重绘痕迹，不是高保真数字人
- 已定位“连接数字人没画面”的根因不是按钮，而是 `153` GPU 显存竞争：
  - `Ollama qwen2.5:7b`
  - `Ollama bge-m3:latest`
  - `CosyVoice`
  - `rerank-service`
  - `metahuman`
  - 同时占用 `Tesla T4 15GB`
- 直接现象是：
  - `metahuman` 重启时 `wav2lip` 模型加载不完整
  - `148 -> /api/metahuman/offer` 间歇性 `502`
  - `153:/offer` 间歇性 `500`
- 临时恢复手段：
  - 卸掉 `ollama` 当前 GPU runners
  - 重启 `metahuman`
  - 之后已验证：
    - `153:/offer` 返回 `200`
    - `148:/api/metahuman/offer` 返回 `200`

## 项目

- 仓库：`ai-avatar`
- 当前主线：档案馆接待 kiosk
- 正式入口：`https://avata.nbdag.lan`

## 当前架构

- `136`
  - Nginx Proxy Manager
  - 内网导航卡片
  - 域名 `avata.nbdag.lan`
- `148`
  - `reception-kiosk`
  - `RAGFlow`
- `153`
  - `Ollama`
  - `CosyVoice`
  - `FunASR`
  - `metahuman-stream`

## 当前部署状态

### 136

- 已配置反代：
  - `avata.nbdag.lan -> 10.19.26.148:18080`
- 导航卡片已加入：
  - 名称：`AI数字人`

### 148

- 路径：`/opt/reception-kiosk`
- Compose：`docker-compose.kiosk.yml`
- 容器：`reception-kiosk-reception-kiosk-1`
- kiosk 已部署并重建过

### 153

- `Ollama`：`10.19.26.153:11434`
- `CosyVoice`：`10.19.26.153:50000`
- `FunASR`：`10.19.26.153:10096`
- `metahuman offer`：`http://10.19.26.153:8010/offer`
- `metahuman text ws`：`ws://10.19.26.153:8001/humanecho`
- GPU：`Tesla T4 15GB`

## 已完成

- kiosk 前端主布局已重构为数字人居中主画面
- 调试面板已改为右侧抽屉
- 连接状态区已压缩为 badge
- 文本问答链路已跑通
- 语音返回链路已跑通
- WebRTC 数字人画面已接通
- 浏览器录音权限问题已通过 HTTPS 入口解决
- 知识库来源状态已拆分为：
  - `hit`
  - `miss`
  - `error`
  - `disabled`
- 数字人文本推送已从错误的 `humanchat` 改为 `humanecho`
- 临时演示头像已替换成正装东方面孔版本
- WebRTC 数字人连接在卸载 `ollama` GPU runners 后已恢复

## 今日最后确认的有效结果

- `148` 上 `/api/chat` 已成功命中过知识库
- 一次实测返回：
  - `retrieval_status: "hit"`
  - `ragflow: 3372ms`
  - `ollama: 6826ms`
  - `cosyvoice: 14078ms`
  - `metahuman: 17ms`

## 当前核心问题

### 1. 数字人已有画面，但嘴部发糊

- `148` 已经把文本发给数字人
- `humanchat` 误用问题已规避，当前 kiosk 走的是：
  - `ws://10.19.26.153:8001/humanecho`
- `153` 上 `tts='cosyvoice'` 初始化缺失问题已修
- CosyVoice 原始 PCM 解码也已修正
- 当前浏览器端端到端确认结果：
  - 已能连上 WebRTC
  - 已有画面
  - 已能说话
  - 但嘴部区域发糊
- 当前判断：
  - 这和 `wav2lip` 的局部重绘特性有关
  - 也和当前临时 avatar 来自静态图片有关
  - 同时受 `153` 显存紧张影响，整体没有富余算力做更稳定渲染

### 2. RAGFlow 偶发 OOM

- 之前部分“未命中知识库”其实是误报
- 已抓到真实错误：
  - `code:100`
  - `cudaMalloc failed: out of memory`
- 当前前端和接口已能区分“检索失败”和“未命中”

### 3. `153` 算力已经开始互相抢占

- 当前 `153` 的 GPU 负载组合已经比较危险：
  - `metahuman`
  - `CosyVoice`
  - `rerank-service`
  - `Ollama`
- `148` 上公开 `OpenWebUI` 如发起真实问答，也会复用：
  - `RAGFlow`
  - `Ollama qwen2.5:7b`
- 所以：
  - 打开 `OpenWebUI` 页面本身不是大问题
  - 但只要在里面提问，就会把同一套 `ollama` runner 再次拉起，继续抢这张卡的显存
- 本次已实测：
  - `ollama` 两个 GPU runner 在场时，`metahuman` 重启后会导致 `/offer` 失败
  - 卸掉 runner 后，WebRTC 即恢复
- 这说明当前如果继续追嘴型和画质，优先级已经不是前端，而是算力隔离或升级。

### 4. 语音闭环还要再回归一轮

- `voice-chat` 代码链路已在 `kiosk_app` 里落地
- 但仍建议下次先做一次完整真机验证：
  - 录音
  - 识别
  - 问答
  - TTS
  - 数字人播报

## 下次优先级

1. 先评估 `153` 的算力方案：
   - 为数字人腾显存
   - 或把 `metahuman` 独立到新的 GPU 环境
2. 算力稳定后，再复测数字人嘴部发糊是否改善
3. 如果仍不满足，就换更适合的真人近景视频源，不再继续放大静态图 avatar 的投入
4. 再做完整语音闭环和 `RAGFlow` OOM 观察

## 关键文档

- [todo.md](/mnt/d/SynologyDrive/AG_Workspace/Work/ai-avatar/todo.md)
- [docs/kiosk-app.md](/mnt/d/SynologyDrive/AG_Workspace/Work/ai-avatar/docs/kiosk-app.md)
- [docs/reception-kiosk-plan.md](/mnt/d/SynologyDrive/AG_Workspace/Work/ai-avatar/docs/reception-kiosk-plan.md)
- [docs/compute-service-apis.md](/mnt/d/SynologyDrive/AG_Workspace/Work/ai-avatar/docs/compute-service-apis.md)

## 下次怎么说

任意一句都可以：

- “继续 ai-avatar，按 handoff 接着来”
- “继续 avata.nbdag.lan kiosk 主线”
- “接着修 153 上 metahuman 嘴型”
- “按 SESSION_HANDOFF 继续”
