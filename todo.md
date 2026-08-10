# ai-avatar 项目任务清单

## 当前状态（2026-06-04）

### 今日新增完成

- 已修 `153` 上 `metahuman-stream` 的热补丁脚本缺陷：
  - 之前只追加了 `CosyVoiceTTS`
  - 但没有把修改后的 `lipreal.py` 写回去
- 已将修复脚本纳入仓库：
  - `scripts/init_metahuman.py`
  - `scripts/patch_metahuman_compose.py`
- 已把修复部署到 `153:/opt/metahuman-stream`
- 已更新 compose 中内嵌的 base64 启动补丁并重建 `metahuman` 容器
- 已验证 `lipreal.py` 具备：
  - `CosyVoiceTTS` import
  - `tts='cosyvoice'` 初始化分支
- 已确认 `CosyVoice /inference_sft` 返回的是原始 PCM，不是 WAV
- 已把数字人侧 TTS 解码改为：
  - `numpy.frombuffer(..., dtype=int16)`
  - 按 `22050 -> 16000` 重采样
- 已在容器内做 smoke test：
  - `CosyVoiceTTS` 可正常生成音频帧
- 已补 `148` 上 `voice-chat` 稳定性修复并完成上线：
  - Docker 镜像已安装 `ffmpeg`
  - `16-bit PCM WAV` 已支持本地重采样
  - 音频预处理异常现在返回 `502`
- 已完成 `voice-chat` 后端闭环验证：
  - 浏览器等价 `16k WAV`：成功
  - `22050 WAV`：成功
  - 错误音频：返回受控错误，不再 `500`
- 已为数字人临时替换一版新的演示头像：
  - 来源：Pexels `28217403`
  - 方式：静态正装东方面孔图片 -> 8 秒循环视频 -> `wav2lip/genavatar.py`
  - 结果：已生成 `200` 帧 `full_imgs` 和 `200` 帧 `face_imgs`
  - 当前运行中的 `wav2lip_avatar1` 已替换为该素材
- 已定位“点连接数字人没画面”的直接原因：
  - `153` GPU 显存被 `Ollama + CosyVoice + rerank-service + metahuman` 同时占用
  - `metahuman` 重启时 `wav2lip` 模型加载不完整，导致 `/offer` 间歇性 `500`
  - 临时处理方式为卸掉 `ollama` 当前 GPU runners 后重启 `metahuman`
- 已确认当前状态：
  - 浏览器可恢复看到数字人画面
  - `153:/offer` 返回 `200`
  - `148:/api/metahuman/offer` 返回 `200`

### 仍需验证

- 需要继续用浏览器做真机观察，确认页面侧表现与嘴型清晰度是否满足现场要求：
  - WebRTC 连接
  - 文本播报
  - 语音播报
  - 观察嘴型是否清晰

### 已完成

- 主线已经切到独立 `kiosk_app`，不再以 Fay 作为接待机最终前端。
- `148` 已部署 kiosk 应用，主入口已切到 `https://avata.nbdag.lan`。
- `136` 已完成 Nginx Proxy Manager 反代与内网导航卡片接入。
- 前端主界面已调整为：
  - 数字人主画面居中
  - 右侧调试抽屉
  - 紧凑服务状态 badge
  - 知识库来源状态面板
- 文本问答主链路已跑通：
  - `RAGFlow` 检索
  - `Ollama` 回答
  - `CosyVoice` 语音返回
  - `metahuman-stream` WebRTC 出画面
- 浏览器录音权限问题已确认依赖 `HTTPS`，`avata.nbdag.lan` 已满足这一点。
- `kiosk_app` 已补充知识库状态字段：
  - `retrieval_status`
  - `retrieval_detail`
- 数字人文本推送入口已从错误的 `humanchat` 改为 `humanecho`，避免再次走数字人内部 LLM。

### 今日确认有效的线上结果

- `148` 上 `/api/chat` 已成功返回知识库命中结果。
- 当次实测返回：
  - `retrieval_status: "hit"`
  - `ragflow: 3372ms`
  - `ollama: 6826ms`
  - `cosyvoice: 14078ms`
  - `metahuman: 17ms`
- 说明当前 kiosk 编排层、文本链路、音频返回链路都基本可用。

## 当前遗留问题

### 1. 数字人当前已出画面，但嘴部发糊

- `148` 侧文本已经能成功推送到数字人。
- 旧问题已经定位并规避：
  - 之前推到了 `ws://10.19.26.153:8001/humanchat`
  - 该路由会触发数字人容器内部 LLM
  - 容器里缺 `openai` 模块，导致报错
- 当前已改为推送到：
  - `ws://10.19.26.153:8001/humanecho`
- `153` 上 `tts='cosyvoice'` 初始化缺失问题已修。
- 另外补修了一个隐藏问题：
  - `CosyVoice /inference_sft` 返回的是原始 PCM
  - 数字人侧不能再按 WAV 去解析
- 2026-06-04 最新浏览器实测：
  - 已有画面
  - 已能说话
  - 但嘴部区域发糊，观感像低质量重绘
- 当前更可能的原因：
  - `wav2lip` 本身就是局部嘴部重绘，不是高保真真人驱动
  - 当前演示头像来自单张静态图片生成的 avatar，天然不如真人视频源自然
  - `153` 是 `Tesla T4 15GB`，同时还在跑 `Ollama / CosyVoice / rerank-service`，显存非常紧
- 结论：
  - 当前状态适合“能演示”
  - 不适合作为最终观感方案

### 2. RAGFlow 不是稳定未命中，而是偶发上游失败

- 之前调试面板里出现“未命中知识库”并不总是真的未命中。
- 现已补充状态区分：
  - `hit`
  - `miss`
  - `error`
  - `disabled`
- 已抓到一次真实上游错误：
  - `RAGFlow code:100`
  - 内部错误为 `llama runner process has terminated: cudaMalloc failed: out of memory`
- 结论：
  - 当前问题不只是召回效果
  - 还包含 `RAGFlow` 自身偶发 OOM
- 下一步需要继续观察：
  - 是特定查询触发
  - 还是高并发/显存紧张时普遍触发

### 3. 数字人画面构图仍可继续优化

- 当前主界面已改成数字人居中的展示方式，比早期左右分栏明显更适合 kiosk。
- 前端已做过一轮构图修正：
  - `object-fit` 从 `cover` 调整为更适合完整展示的策略
  - 增加背景过渡，减轻留白观感
- 但人物构图是否达到现场要求，还需要持续实机观察。
- 如后续仍显得人物过小或远景感过重，需要再评估：
  - 前端裁切策略
  - 数字人源素材或近景输出方式

### 4. `153` 算力竞争已经影响数字人稳定性

- 当前 `153` 的 `Tesla T4 15GB` 同时承载：
  - `metahuman-stream`
  - `CosyVoice`
  - `Ollama`
  - `rerank-service`
- `148` 上公开 `OpenWebUI` 若发起问答，也会复用同一套：
  - `RAGFlow`
  - `Ollama qwen2.5:7b`
- 结论：
  - 开着 `OpenWebUI` 页面本身问题不大
  - 但只要在 `OpenWebUI` 里真正提问，也会把 `ollama` runner 拉起来，继续与数字人抢显存
- 本次已实测到：
  - `ollama qwen2.5:7b` 和 `bge-m3:latest` GPU runner 在场时
  - `metahuman` 重启后 `/offer` 会出现 `500`
  - 卸掉这两个 runner 后，WebRTC 恢复正常
- 这说明当前不是单纯“前端连接问题”，而是显存预算不足。
- 后续可选方向：
  - 给数字人单独机器或单独 GPU
  - 把 `Ollama` 改回 CPU / 降小模型 / 限制并发常驻
  - 将 `rerank-service` 或嵌入模型迁走
  - 直接升级显卡或新增算力节点

### 5. 语音链路还需要页面侧再做一轮完整联调

- 当前浏览器录音权限依赖 `HTTPS`，已解决入口问题。
- `voice-chat` 代码链路已在 `kiosk_app` 内落地：
  - 浏览器录音
  - 上传后端
  - 转码
  - `FunASR` 识别
  - 回到现有问答链路
- 服务侧已经完成一轮后端闭环验证。
- 但还需要页面侧再补一次“录音 -> 识别 -> 回答 -> 音频 -> 数字人播报”的真机确认。

## 当前部署现状

### 136（入口与导航）

- Nginx Proxy Manager 已配置：
  - 域名：`avata.nbdag.lan`
  - 目标：`10.19.26.148:18080`
- 导航卡片已加入：
  - 地址：`avata.nbdag.lan`
  - 名称：`AI数字人`

### 148（kiosk 应用）

- 路径：`/opt/reception-kiosk`
- Compose 文件：`docker-compose.kiosk.yml`
- 容器：`reception-kiosk-reception-kiosk-1`
- 端口：`18080`
- 当前对外主入口：
  - `https://avata.nbdag.lan`

### 153（算力与数字人）

- `Ollama`：`10.19.26.153:11434`
- `CosyVoice`：`10.19.26.153:50000`
- `FunASR`：`10.19.26.153:10096`
- `metahuman-stream`：
  - offer：`http://10.19.26.153:8010/offer`
  - 文本推送：`ws://10.19.26.153:8001/humanecho`
- 当前临时演示头像备份：
  - `153:/opt/metahuman-stream/custom_avatars/pexels_28217403`

## 明天优先级

1. 先决定算力方案：
   - 给数字人让显存
   - 或把数字人服务迁到更宽松的 GPU 环境
2. 在算力稳定后，再观察嘴部发糊是否改善。
3. 如果仍发糊，就需要换更适合的真人近景视频源，而不是继续用静态图 avatar。
4. 继续观察 `RAGFlow` 是否仍会偶发 OOM 或超时，并记录触发问题的提问样例。

## 新增文档

- 同事调算力接口请看：
  - [`docs/compute-service-apis.md`](docs/compute-service-apis.md)

## 备注

- 当前不建议再回 Fay 主线，除非用户明确要求。
- 当前最该动的是 `153` 上 `metahuman-stream`，不是 `148` 上 kiosk 编排层。
- 浏览器如果看不到最新状态，先强刷：
  - `Ctrl+F5`
