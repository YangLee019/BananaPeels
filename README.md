# BananaPeels · LingBot-VLA 2.0 比赛工作区

用于 RoboTwin 2.0 Aloha-AgileX 的 50 任务比赛。训练只使用每任务 50 条 clean 数据；正式评测为 50 任务 × clean/randomized × 100 次。

本次安装与验证结果见 [基础环境验证记录](docs/setup_status.md)。

## 本地基础环境

使用 Python 3.12.13；通过 uv 与 `uv.lock` 安装。PowerShell 中进入此目录后运行：

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\Activate.ps1
banana-peels --help
python scripts\doctor.py --output outputs\environment.json
```

若尚未安装 uv：`winget install --id astral-sh.uv -e`。
Linux 的轻量准备环境可使用 `bash scripts/bootstrap.sh`。
两个平台各自创建 `.venv`，不要复制或共用 Windows/Linux 虚拟环境。

基础环境包含 Hugging Face 下载工具、PyYAML、pytest、ruff 和本项目 CLI。
Python 解释器在 `.runtime/python`，下载缓存位于 `.cache/uv`，均局限于项目。
这里不安装 PyTorch、CUDA、FlashAttention 或仿真器。

## 日常校验

```powershell
# 官方空模板的结构检查；此模式不能代表真实评测完成
banana-peels validate-results templates\results.template.json --template

# 实际结果：要求全部50任务、两种setting、每项100次，成功数为0–100整数
banana-peels validate-results outputs\results.json

python -m pytest
ruff check .
```

模板中的 0 和 team_id 占位值需在真实评测后替换，不生成虚假成绩。

## 数据与上游源码

```powershell
# 默认只打印50个clean包的下载计划，不联网、不下载
python scripts\download_data.py --output D:\BananaPeelsData\raw

# 确认目标磁盘空间后，显式开始下载；也可加 --task adjust_bottle 先取一个任务
python scripts\download_data.py --output D:\BananaPeelsData\raw --download

# 获取 configs/sources.lock.json 固定版本的源码快照到 vendor/
python scripts\fetch_upstream.py
```

下载程序只允许 `dataset/<官方任务>/aloha-agilex_clean_50.zip`，将远程 revision 解析成 SHA 并保存清单。
同一输出目录只允许同一个数据 revision，分批下载会合并已有清单；版本变化时需要新目录或显式指定旧 SHA。
下载前核对文件存在和压缩包总大小。解压、转换及权重还需额外空间。
Linux 服务器上将输出路径换成自己的持久盘目录。

按 [LingBot 官方数据准备指南](https://github.com/Robbyant/lingbot-vla-v2/blob/bc643d74a0127fab8788da993b261d4d64101138/experiment/robotwin/README.md)
把原始数据转成逐任务 LeRobot 数据。完成后在 Linux 上生成训练清单：

```bash
banana-peels make-train-list --data-root /data/lerobot --output configs/train_clean.txt
```

预期每任务目录为 `<task>-aloha-agilex_clean_50-50`，且 `meta/info.json` 的 `total_episodes` 为 50。
缺失目录或元数据会失败；仅规划时可显式添加 `--allow-missing`。
上游清单按空白拆分两列，所以数据路径不能包含空格。
不要照搬官方默认 `robotwin.txt`：它混有 randomized 数据和其他机器人数据。
新 `demo_clean.zip`/LeRobot 导出还包含替换轨迹，是否可代替比赛数据需以赛事说明为准。

## GPU 训练与仿真

详见 [GPU 环境说明](docs/gpu_environment.md)。本地 `.venv` 只表示准备工具可用，不表示模型训练或仿真已通过。

## 目录

```text
configs/       赛事限制、固定的上游版本
templates/     用户提供的官方材料模板
src/           本项目的校验与清单工具
scripts/       环境引导、诊断、源码获取、数据下载
tests/         数据限制与评测结果校验测试
docs/          GPU环境准备说明
vendor/        固定版本的上游代码（忽略）
outputs/       本机检查报告和实验产物（忽略）
```

本次初始化不会向 GitHub 推送，不会启动训练、购买云实例或自动下载模型/训练数据。
