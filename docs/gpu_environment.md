# GPU 环境与本地基础环境的边界

本地主机：Windows 11、32 GiB 内存、RTX 3060 Laptop 6 GiB；已有 Ubuntu 22.04 WSL/ROS2。
初始化时 C 盘约剩 2.8 GiB，D 盘约剩 85 GiB。以上为当时探测值，可重新运行 `scripts/doctor.py`。

## 模型训练环境

目标为具备 NVIDIA GPU 的 Linux 服务器。与 ROS2、仿真环境隔离，用上游提供的独立 Conda 环境：

```bash
python scripts/fetch_upstream.py --only lingbot-vla-v2
cd vendor/lingbot-vla-v2
bash tools/create_train_env.sh --env-name banana-lingbot
```

这会安装大型 GPU 依赖，只有在服务器 GPU、CUDA、磁盘和 Conda 已准备好时再执行。
官方脚本的核心版本：Python 3.12、torch 2.8.0、torchvision 0.23.0、torchaudio 2.8.0、flash-attn 2.8.3。
使用官方脚本的版本组合；本地 `uv.lock` 仅锁定准备工具，不是训练依赖锁。
脚本会加载 CUDA 并检查可用性，FlashAttention 没有匹配 wheel 时可能编译，需要相容的 CUDA toolkit 和编译器。

AMD Radeon Cloud 使用 ROCm，不能直接套用上述 CUDA 安装；需要单独完成兼容性验证。
当前没有已连接的云实例，也没有验证 AMD 训练或仿真链路。

## RoboTwin 仿真环境

固定源码 commit：`13c3c47ff4312dd62484bcd51be034af55c062d1`。
按固定版本的安装文档安装独立的 `banana-robotwin` Conda 环境，勿把当前 main 的新 XPolicyLab 脚本与此版本混用。

核心依赖参考：Python 3.10、torch 2.4.1、NumPy 1.26.x、SAPIEN 3.0.0b1、mplib 0.2.1、cuRobo v0.7.8。
还需仿真资产、Vulkan 渲染、ffmpeg 和正确的 NVIDIA 驱动。
官方支持表将 WSL 渲染列为不支持；现有 WSL ROS2 不能作为仿真已可用的证明。

LingBot 官方指南报告：其软件栈下一个 FP32 推理服务加仿真约需 32 GB 显存；BF16 会改变结果。
本机 6 GB 显卡不作为该正式评测配置的目标，不在本次初始化中加载 6B 模型。

## 权重与检查

基础权重：[robbyant/lingbot-vla-v2-6b](https://huggingface.co/robbyant/lingbot-vla-v2-6b)。
官方训练配置还涉及 Qwen3-VL、MoGe、LingBot-Depth 和 DINO-VIDEO，按所选配置逐一准备。
不要把已经做过 RoboTwin 后训练的权重误当成比赛允许的基础预训练权重。

安装后依次验证 Python/依赖版本、`torch.cuda.is_available()`、FlashAttention 导入、SAPIEN 渲染、单任务训练/推理链路。
上游安装脚本会容忍部分 `pip check` 元数据冲突；出现冲突时需记录实际情况，不能报告依赖完全无冲突。
正式比赛的评测细则以赛事通知为准，不能以公开项目 README 代替。

来源：

- [LingBot 固定版本安装脚本](https://github.com/Robbyant/lingbot-vla-v2/blob/bc643d74a0127fab8788da993b261d4d64101138/tools/create_train_env.sh)
- [LingBot 固定版本 RoboTwin 指南](https://github.com/Robbyant/lingbot-vla-v2/blob/bc643d74a0127fab8788da993b261d4d64101138/experiment/robotwin/README.md)
- [RoboTwin 安装与系统支持](https://robotwin-platform.github.io/doc/usage/robotwin-install.html)
- [RoboTwin 固定版本依赖](https://github.com/RoboTwin-Platform/RoboTwin/blob/13c3c47ff4312dd62484bcd51be034af55c062d1/script/requirements.txt)
