# ai-avatar

当前仓库主线已经不是 Fay，而是档案馆接待 kiosk：

- `148` 部署独立 `kiosk_app`
- `153` 提供算力与数字人服务
- `136` 提供 HTTPS 入口与内网导航

当前主入口：

- `https://avata.nbdag.lan`

## 当前重点

已跑通：

- 文本问答
- RAGFlow 检索
- Ollama 回答
- CosyVoice 语音返回
- metahuman-stream WebRTC 出画面
- 数字人文本推送

当前主要遗留问题：

1. `153` 上数字人虽然已恢复画面和播报，但嘴部发糊，当前只适合演示
2. `153` 的 `Tesla T4 15GB` 已出现明显显存竞争，影响 `metahuman` 稳定性
3. `RAGFlow` 偶发 OOM，需要继续观察
4. 语音录音链路需要再做一轮真机闭环验证

## 文档入口

- kiosk 应用说明：[`docs/kiosk-app.md`](docs/kiosk-app.md)
- 接待方案与现场结论：[`docs/reception-kiosk-plan.md`](docs/reception-kiosk-plan.md)
- 算力接口调用说明：[`docs/compute-service-apis.md`](docs/compute-service-apis.md)
- 当前任务清单：[`todo.md`](todo.md)

## 当前角色分工

### 136

- Nginx Proxy Manager
- 内网导航页
- 域名入口 `avata.nbdag.lan`

### 148

- `reception-kiosk` 编排应用
- 对外暴露 `18080`
- 承接浏览器页面、API、知识库状态展示

### 153

- `Ollama`
- `CosyVoice`
- `FunASR`
- `metahuman-stream`

## 当前线上部署

### kiosk

- 路径：`/opt/reception-kiosk`
- Compose：`/opt/reception-kiosk/docker-compose.kiosk.yml`
- 容器：`reception-kiosk-reception-kiosk-1`

### 数字人

- 路径：`/opt/metahuman-stream`
- 容器：`metahuman`

## 已确认的关键结论

- 浏览器录音必须走 `HTTPS`，因此主入口已切到 `avata.nbdag.lan`。
- 数字人文本推送不能用 `humanchat`，应使用：
  - `ws://10.19.26.153:8001/humanecho`
- kiosk 已补 `retrieval_status`，不再把所有知识库失败都误报成“未命中”。
- `153` 的 `metahuman-stream` TTS 初始化问题已修。
- 当前新的主要问题是：
  - `wav2lip` 静态 avatar 的嘴部发糊
  - `153` 算力竞争导致数字人重启后可能出现 `/offer` 失败

## 下一步

1. 先评估并调整 `153` 的算力分配，优先保证数字人稳定运行
2. 复测数字人嘴部发糊是否随算力释放改善
3. 若仍不满足，再换真人近景视频源重做 avatar
4. 回归验证录音问答闭环
5. 观察 `RAGFlow` OOM 条件
