# 已知问题与解决方案

## CosyVoice

### 问题1：Float32 vs BFloat16 dtype 不匹配
- 报错：RuntimeError: mat1 and mat2 must have the same dtype, but got Float and BFloat16
- 位置：cosyvoice/llm/llm.py → from_pretrained
- 修复：加 torch_dtype=torch.bfloat16

### 问题2：Conv1d kernel size 超出输入长度
- 报错：RuntimeError: Kernel size can't be greater than actual input size
- 位置：cosyvoice/frontend/frontend.py → _extract_speech_feat
- 修复：返回前 pad speech_feat 到最小 9 帧

### 问题3：Docker 构建时 deepspeed 编译失败
- 报错：deepspeed 需要 CUDA_HOME / nvcc 编译
- 原因：pytorch:runtime 镜像不含 CUDA toolkit
- 修复：从 requirements 中排除 deepspeed（推理不需要它）

### 问题4：容器启动后不断重启
- Docker 容器启动后立刻退出，restart 策略导致循环
- 可能原因：
  - pip install 在容器启动时装依赖（太慢）→ 改在 Dockerfile 中构建时安装
  - 缺失 Python 包 → 装完整 requirements（去掉 deepspeed）

## Ollama
- 巡检脚本误报"未检测到11434"，实际 ss -tlnp 显示 *:11434 正常监听
- 原因：巡检脚本只匹配 0.0.0.0:11434，实为误判，无需处理

## Docker 构建网络问题

由于服务器在国内，Docker Hub 被墙，拉取外部镜像需使用国内镜像源：

| 源 | 用途 | 是否可用 |
|----|------|:--------:|
| `nvcr.io` | NVIDIA CUDA 基础镜像 | ✅ 可用 |
| `docker.m.daocloud.io` | DaoCloud 镜像（Docker Hub 代理） | ✅ 可用 |
| `registry.cn-*.aliyuncs.com` | 阿里云容器镜像 | ✅ 可用 |
| `mirrors.aliyun.com` | PyPI / apt 包 | ✅ 可用 |
| `download.pytorch.org` | PyTorch 官方下载 | ❌ 被墙 |

注意事项：
- Docker 构建通过 SSH 长期运行会因 SSH 超时而中断 → 使用 `nohup` 或 `tmux` 保持后台运行
- 阿里云镜像对特定大文件可能限速，必要时尝试不同的镜像源
