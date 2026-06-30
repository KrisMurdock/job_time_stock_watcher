# Stock Watcher (股票监控)

> 终端里的实时股票行情看板 — 支持 A 股、港股、美股。

[English](README.md)

![Stock Watcher TUI](docs/image.png)

## 功能特性

- **多市场** — 上海A股 (`sh`)、深圳A股 (`sz`)、港股 (`hk`)、美股 (`us`)
- **实时轮询** — 交易时段自动刷新，休市自动暂停节省带宽
- **表头排序** — 点击表头按现价、涨跌幅、盈亏等排序
- **价格告警** — 可配置的阈值（上破/下破价格、涨跌幅），触发时响铃 + 系统通知
- **持仓管理** — 记录成本价、股数，实时显示浮动盈亏
- **详情弹窗** — 五档买卖盘口（A股）、市盈率（港股）、近期告警记录
- **飞书推送**（可选）— 告警卡片 + 定时行情摘要推送到飞书群
- **AI 对话**（可选）— 接入 DeepSeek，在飞书群内 @机器人 智能回复
- **隐私模式** — 一键伪装：所有股票名和数字隐藏，防止屏幕被窥
- **CSV 导出** — 当前表格一键导出到带时间戳的 `.csv` 文件
- **热加载** — 修改 `config.yaml` 或 `positions.yaml` 无需重启

## 环境要求

- **Python** ≥ 3.11
- **pip**（或你习惯的包管理器）

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/KrisMurdock/job_time_stock_watcher.git
cd job_time_stock_watcher

# 安装依赖
pip install -e .

# 复制示例配置文件
cp config.yaml.example config.yaml
cp positions.yaml.example positions.yaml

# 编辑自选股
# 打开 config.yaml，把 watchlist 里的代码换成你自己的

# 运行
python -m stock_watcher.app
```

或者用便捷脚本：

```bash
./run.sh
```

## 配置说明

所有配置在 `config.yaml` 中。带注释的示例文件见 [`config.yaml.example`](config.yaml.example)。

### 核心配置

| 字段 | 类型 | 默认值 | 说明 |
|-------|------|---------|------|
| `poll_interval` | float | `2.5` | 轮询间隔（秒），控制每隔多少秒拉取一只股票的行情 |
| `watchlist` | list | *示例* | 自选股列表，股票代码带市场前缀 |
| `alerts` | list | `[]` | 告警规则（见下方） |
| `proxies` | list | `[]` | HTTP 代理地址，留空表示直连 |

### 请求配置

| 字段 | 类型 | 默认值 | 说明 |
|-------|------|---------|------|
| `request.timeout` | int | `10` | HTTP 请求超时（秒） |
| `request.user_agent_pool` | list | *浏览器* | User-Agent 池，每次请求随机选一个 |

### 退避策略（指数退避）

| 字段 | 类型 | 默认值 | 说明 |
|-------|------|---------|------|
| `backoff.base` | float | `5` | 初始退避秒数 |
| `backoff.max` | float | `120` | 最大退避秒数（天花板） |
| `backoff.multiplier` | float | `2` | 每次失败的乘数 |

### 告警声音

| 字段 | 类型 | 默认值 | 说明 |
|-------|------|---------|------|
| `alert_sound_command` | string | `""` | 自定义音效 shell 命令（Linux: `paplay`，macOS: `afplay`） |

### 股票代码前缀

| 前缀 | 市场 | 示例 |
|--------|--------|---------|
| `sh` | 上海A股 | `sh600519`（贵州茅台） |
| `sz` | 深圳A股 | `sz000001`（平安银行） |
| `hk` | 港股 | `hk00700`（腾讯控股） |
| `us` | 美股 | `ustsla`（特斯拉）、`usaapl`（苹果） |

### 告警规则

告警规则放在 `alerts` 下，每条包含三个字段：

```yaml
alerts:
  - code: hk00700        # 股票代码
    type: price_above    # price_above（上破）/ price_below（下破）/ pct_above（涨幅超）/ pct_below（跌幅超）
    value: 433.0         # 阈值（价格用元，百分比用数字，如 5.0 表示 5%）
```

### 持仓信息

持仓数据单独存放在 `positions.yaml`。先复制示例：

```bash
cp positions.yaml.example positions.yaml
```

格式：

```yaml
hk00700:
  cost: 430.0       # 买入成本价（元）
  quantity: 100     # 持仓股数
  available: 100    # 可用股数
```

支持热加载 — 修改后无需重启。

## 使用说明

### 快捷键

| 按键 | 功能 |
|-----|--------|
| `a` | **添加股票** — 输入代码或名称搜索 |
| `d` | **删除股票** — 删除当前高亮的行 |
| `t` | **设置告警** — 格式：`pa 450`（价格上破450）、`pb 420`（价格下破420）、`ca 5`（涨幅超5%）、`cb 3`（跌幅超3%） |
| `v` | **查看告警** — 列出所有告警规则，选中后按 `d` 删除 |
| `h` | **告警历史** — 查看最近 200 条触发记录 |
| `p` | **设置持仓** — 格式：`420 200`（成本420元、200股），留空删除持仓 |
| `s` | **查看配置** — 显示当前配置参数 |
| `e` | **导出 CSV** |
| `r` | **手动刷新** — 强制立即刷新所有股票 |
| `x` | **隐私模式** — 一键隐藏所有股票名称和数字 |
| `Enter` | **详情弹窗** — 当前高亮股票的完整信息 |
| `Ctrl+N` | **重新加载配置** — 热加载 config.yaml 和 positions.yaml |
| `Esc` | **关闭/取消** — 关闭弹窗或取消输入 |
| `点击表头` | **排序** — 点击表头排序（升序 → 降序 → 取消排序） |
| `q` | **退出** |

### 顶部状态栏

显示市场状态（交易中/休市）、当前时间、抓取延迟、涨跌平统计数、错误和退避状态。

### 底部持仓栏

显示持仓数、总市值、总浮动盈亏（金额+百分比），盈利绿色、亏损红色。

## 可选集成

### 飞书/Lark 机器人

1. 在飞书群设置中添加**自定义机器人**（webhook）
2. 将 webhook 地址填入 `config.yaml`：
   ```yaml
   chat:
     feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook地址"
   ```
3. 机器人将自动推送告警卡片和定时行情摘要

如需双向 `@机器人` 对话，还需在飞书开放平台创建企业自建应用并开启 WebSocket：

```yaml
chat:
  feishu_app_id: "你的APP-ID"
  feishu_app_secret: "你的APP-SECRET"
```

### DeepSeek AI 对话

启用飞书双向机器人后，群内 @机器人 的问题将由 DeepSeek 回答：

```yaml
deepseek:
  api_key: "你的API-KEY"   # 在 https://platform.deepseek.com/api_keys 获取
  model: "deepseek-chat"
```

## 项目结构

```
.
├── config.yaml.example      # 带注释的配置模板
├── positions.yaml.example   # 持仓数据模板
├── run.sh                   # 便捷启动脚本
├── pyproject.toml           # 项目元数据和依赖声明
├── docs/
│   ├── image.png            # TUI 截图
│   └── adr/                 # 架构决策记录
├── src/stock_watcher/
│   ├── app.py               # TUI 应用（入口）
│   ├── config.py            # 配置加载、热加载、持久化
│   ├── fetcher.py           # 行情数据接口（新浪、腾讯）
│   ├── models.py            # 数据模型（Quote、Alert、Position 等）
│   ├── chat_sender.py       # 飞书 webhook 卡片发送
│   ├── bot_server.py        # 飞书 WebSocket 双向机器人
│   └── deepseek_chat.py     # DeepSeek AI 集成
└── tests/
    ├── test_app.py          # TUI 集成测试
    ├── test_config.py       # 配置解析和持久化测试
    ├── test_fetcher.py      # API 抓取测试
    ├── test_models.py       # 模型单元测试
    └── test_scheduler.py    # 轮询和退避测试
```

## 许可证

MIT
