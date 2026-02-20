<div align="center">
  <img src="assets/logo.svg" alt="Telegram Signal Analyzer" width="680"/>

  # Telegram Signal Analyzer

  **Telegram 交易信号监控与自动化交易系统**

  [![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
  [![Telegram](https://img.shields.io/badge/Telegram-API-0088cc?style=flat-square&logo=telegram)](https://core.telegram.org)
  [![Gate.io](https://img.shields.io/badge/Gate.io-Futures-00d4aa?style=flat-square)](https://www.gate.io)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
</div>

---

## 项目概述

Telegram Signal Analyzer 是一个基于 Telethon + AI 大模型的 Telegram 交易信号监控与自动化交易系统。系统实时监听指定 Telegram 频道/超级群组话题中的消息，通过 SiliconFlow AI（Qwen3-235B 模型）从中文交易信号文本中提取结构化交易数据（交易对、方向、入场价、目标价、止损价），使用 Pydantic 进行严格的数据验证和价格逻辑校验，并可选地通过 Gate.io 合约 API 自动执行交易（市价/限价开仓、止损止盈设置）。

项目包含两个版本：
- **tgqd**: 基础版，仅监听 + AI 信号提取 + JSON 保存
- **gate**: 增强版，集成 Gate.io 合约交易自动执行

## 技术栈

- **Telethon**: Telegram MTProto 异步客户端
- **SiliconFlow API**: AI 大模型（Qwen3-235B-A22B-Instruct）
- **Pydantic v2**: 数据验证与交易信号模型
- **gate-api**: Gate.io 合约交易 SDK
- **asyncio**: 异步消息处理与并行任务
- **OpenAI SDK**: 兼容 SiliconFlow 的 Chat Completions 接口

## 功能特性

### 信号监听与提取
- **实时频道监听** -- 通过 Telethon 监听指定 Telegram 频道和超级群组话题的新消息
- **AI 信号提取** -- 使用 Qwen3-235B 模型从中文交易信号文本中提取结构化数据（JSON 格式输出）
- **Few-Shot Prompt** -- 内置 4 个示例（范围价格、现价、条件性指令、缺少方向），指导 AI 精确提取
- **Pydantic 验证** -- 严格的数据模型验证，包括多空方向价格逻辑校验（多单目标价 > 入场价 > 止损价）
- **"现价"支持** -- 入场价支持"现价"字符串，自动转为市价单
- **消息过滤** -- 自动跳过媒体消息、回复消息、无文本消息
- **信号持久化** -- 提取的信号保存到 `trading_signals.json`，包含原始文本、时间戳、消息 ID

### 自动交易（gate 版本）
- **Gate.io 合约交易** -- 通过 gate-api SDK 执行 USDT 永续合约交易
- **市价/限价开仓** -- 含"现价"时使用市价单，否则使用均价限价单
- **固定保证金计算** -- 根据保证金金额和杠杆倍数自动计算仓位大小
- **止损止盈** -- 自动创建价格触发的止损止盈单，支持多种止盈模式
- **异步执行** -- 交易执行不阻塞消息监听，使用 `asyncio.create_task` 并行处理

### 连接管理
- **指数退避重连** -- 网络错误时自动重连，指数退避 + 随机抖动
- **保活机制** -- 每 30 秒发送 GetStateRequest 保持连接
- **限流处理** -- 自动处理 Telegram FloodWaitError
- **频道权限验证** -- 启动时验证所有目标频道/群组的访问权限

### 辅助工具
- **历史消息导出** -- 导出指定频道话题的完整历史消息到文本文件
- **群组/频道列表** -- 列出所有已加入的群组和频道，包含话题列表、成员数等详细信息

## 安装说明

1. 克隆仓库到本地：
   ```bash
   git clone https://github.com/Past-Tang/telegram-signal-analyzer.git
   cd telegram-signal-analyzer
   ```

2. 安装依赖：
   ```bash
   pip install telethon openai pydantic gate-api
   ```

3. 配置参数：
   - **基础版**: 编辑 `tgqd/monitor_telegram_trading.py` 中的 API 配置
   - **增强版**: 编辑 `gate/config.py` 中的所有配置

## 使用方法

### 基础版（仅信号提取）
```bash
cd tgqd
python monitor_telegram_trading.py
```

### 增强版（信号提取 + 自动交易）
```bash
cd gate
python monitor_telegram_trading.py
```

### 导出历史消息
```bash
cd tgqd
python export_topic_history.py
```

### 查看已加入的群组和频道
```bash
cd tgqd
python leave_all_groups.py
```

## 配置说明

### Telegram API (`gate/config.py`)

| 参数 | 说明 |
|:---|:---|
| `API_ID` | Telegram API ID（从 my.telegram.org 获取） |
| `API_HASH` | Telegram API Hash |
| `PHONE_NUMBER` | 登录手机号 |
| `TARGET_CHANNEL_IDS` | 监听的频道 ID 列表 |
| `TARGET_TOPICS` | 超级群组话题映射（群组 ID -> 话题 ID 列表） |

### AI 模型 (`gate/config.py`)

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `API_KEY` | - | SiliconFlow API 密钥 |
| `BASE_URL` | `https://api.siliconflow.cn/v1` | API 基础地址 |
| `MODEL` | `Qwen/Qwen3-235B-A22B-Instruct-2507` | AI 模型 |

### Gate.io 交易 (`gate/config.py`)

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `API_KEY` | - | Gate.io API Key |
| `API_SECRET` | - | Gate.io API Secret |
| `HOST` | `https://fx-api-testnet.gateio.ws/api/v4` | API 地址（默认测试网） |
| `LEVERAGE` | `10` | 默认杠杆倍数 |
| `MARGIN_AMOUNT` | `50` | 固定保证金金额（USDT） |

### 交易策略 (`gate/config.py`)

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `TAKE_PROFIT_MODE` | `first_price` | 止盈模式（`first_price` / `percentage`） |
| `TAKE_PROFIT_PERCENTAGE` | `2.0` | 止盈百分比 |
| `STOP_LOSS_PERCENTAGE` | `1.5` | 备用止损百分比 |

## 项目结构

```
telegram-signal-analyzer/
├── tgqd/                                    # 基础版（仅信号提取）
│   ├── monitor_telegram_trading.py          # 主监听程序（391行）
│   ├── export_topic_history.py              # 历史消息导出工具（113行）
│   ├── leave_all_groups.py                  # 群组/频道列表工具（101行）
│   ├── test.py                              # 信号提取测试
│   ├── trading_signals.json                 # 提取的交易信号
│   └── channel_*_history.txt                # 导出的历史消息
├── gate/                                    # 增强版（信号提取 + 自动交易）
│   ├── monitor_telegram_trading.py          # 主监听程序（536行）
│   ├── gate_trading.py                      # Gate.io 合约交易模块（387行）
│   ├── config.py                            # 统一配置文件
│   └── down.py                              # 辅助脚本
├── assets/
│   └── logo.svg                             # 项目 Logo
├── LICENSE                                  # MIT 许可证
└── README.md
```

## 交易信号格式

### 输入示例（Telegram 消息）
```
BTC 116000-115500附近多
目标 ；117000-118000附近
止损: 114800附近
```

### AI 提取输出
```json
{
  "trading_pair": "BTC/USDT",
  "direction": "long",
  "entry_price": [116000, 115500],
  "target_price": [117000, 118000],
  "stop_loss": 114800
}
```

### 支持的信号类型
- **范围价格**: `BTC 116000-115500附近多` -> 限价单（均价）
- **现价入场**: `ETH 现价轻仓进多` -> 市价单
- **条件性指令**: `留意117100附近不破区间留意多单` -> 自动忽略（返回空 JSON）

## 核心流程

```
启动 -> 连接 Telegram -> 验证频道权限
     -> 注册消息监听器 + 启动保活任务
     -> 收到新消息:
        ├── 过滤（媒体/回复/无文本）
        ├── 调用 AI 提取交易信号
        ├── Pydantic 验证（价格逻辑校验）
        ├── 保存信号到 JSON 文件
        └── [gate 版本] 执行 Gate.io 合约交易:
            ├── 获取合约信息
            ├── 计算仓位大小
            ├── 创建入场订单（市价/限价）
            ├── 创建止损单
            └── 创建止盈单
     -> 断线自动重连（指数退避）
```

## 依赖项

| 包 | 用途 |
|:---|:---|
| telethon | Telegram MTProto 异步客户端 |
| openai | SiliconFlow AI API 客户端 |
| pydantic | 数据验证与交易信号模型 |
| gate-api | Gate.io 合约交易 SDK |

## 常见问题

### Telegram 连接失败？
检查 API_ID 和 API_HASH 是否正确，确保网络可以访问 Telegram 服务器。首次运行需要输入验证码。

### AI 提取结果不准确？
系统使用 Few-Shot Prompt 指导 AI，对于非标准格式的信号可能提取失败。可以修改 `extract_trade_signal` 函数中的 Prompt 来适配不同信号格式。

### Gate.io 交易失败？
默认使用测试网（testnet），确保 API Key 和 Secret 对应测试网。生产环境需修改 `HOST` 为 `https://fx-api.gateio.ws/api/v4`。

### 如何监听多个频道？
在 `config.py` 的 `TARGET_CHANNEL_IDS` 列表中添加多个频道 ID，`TARGET_TOPICS` 中添加超级群组话题映射。

## 安全注意事项

- Telegram API 凭据和手机号存储在代码/配置文件中，请勿提交到公开仓库
- SiliconFlow API 密钥需要保密
- Gate.io API 密钥具有交易权限，务必妥善保管
- 默认使用 Gate.io 测试网，生产环境使用前请充分测试
- 建议将所有敏感配置迁移到环境变量

## 许可证

[MIT License](LICENSE)

## 免责声明

本工具仅供学习研究使用，不构成任何投资建议。加密货币合约交易存在极高风险，可能导致全部本金损失。自动化交易系统可能因网络延迟、AI 误判等原因导致非预期交易。使用者需自行承担所有交易风险和损失。