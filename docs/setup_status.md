# 基础环境验证记录

日期：2026-09-18。

| 检查 | 结果 |
|---|---|
| 独立 Git 仓库与 origin | 已初始化，指向 YangLee019/BananaPeels；未提交或推送 |
| 本地 Python | 3.12.13，项目 `.venv` |
| 依赖安装 | `uv.lock` 锁定；引导脚本重复运行通过 |
| 依赖一致性 | `uv pip check`：19 个已安装包兼容 |
| 校验和下载逻辑 | pytest 24 项通过；下载测试全部模拟网络 |
| 代码检查 | Ruff 检查与格式检查通过 |
| Linux 引导脚本 | bash 语法检查通过，未在 Linux 实际安装 |
| 官方结果模板 | 两种 setting、各 50 任务，结构检查通过；空模板不代表已评测 |
| LingBot 源码 | 已下载固定 revision `bc643d74a0127fab8788da993b261d4d64101138` |
| RoboTwin 源码 | 已下载固定 revision `13c3c47ff4312dd62484bcd51be034af55c062d1` |
| 源码目录权限 | 已恢复项目继承权限，读取与重复获取检查通过 |
| 训练 / 仿真 | 未安装 GPU 依赖，未运行模型或仿真 |

使用已安装的 Hugging Face 客户端实际查询过官方数据元信息：

- 仓库：`TianxingChen/RoboTwin2.0`。
- 查询到的 revision：`981c92aa34d8f94d4cff47e0d5bc2f7d4e0af042`。
- `dataset/<task>/aloha-agilex_clean_50.zip`：50 个均存在。
- 50 个压缩包合计：23,780,715,316 bytes，约 23.8 GB；未下载。
- 要下载这次验证过的版本，可为下载命令添加 `--revision 981c92aa34d8f94d4cff47e0d5bc2f7d4e0af042`。
- 解压、数据转换、模型权重、GPU 依赖还需要额外空间。

本机为 RTX 3060 Laptop 6 GiB，当前项目所在 C 盘约剩 2.6 GiB。
正式训练及评测需要另行准备符合上游依赖的 GPU 服务器；本次没有连接或配置云实例。

机器探测原始结果位于 `outputs/environment.json`，数据查询结果位于 `outputs/dataset_check.json`。
`outputs/`、`.venv/`、`.runtime/`、`.cache/` 和 `vendor/` 不纳入 Git。
