# 飞书机器人 Webhook 通知

**日期:** 2025-06-30
**状态:** 设计中

## 概述

在现有邮件通知基础上，新增飞书（Lark）自定义机器人 webhook 推送。
告警触发时实时发送卡片消息，每日收盘后发送汇总卡片。

## 配置

`config.yaml` 新增 `chat` 段：

```yaml
chat:
  feishu_webhook: ""    # 飞书机器人 webhook URL
  feishu_secret: ""     # 签名密钥（可选，留空不签名）
```

## 模块设计

### `chat_sender.py`（新增）

| 函数 | 用途 |
|------|------|
| `send_feishu_text(webhook_url, secret, text)` | 发送纯文本消息 |
| `send_feishu_card(webhook_url, secret, card_dict)` | 发送卡片消息 |
| `build_alert_card(code, name, rule_desc, price)` → card_dict | 构建告警卡片 |
| `build_summary_card(quotes)` → card_dict | 构建每日汇总卡片 |

签名：如 `feishu_secret` 非空，对 `timestamp + "\n" + secret` 做 HMAC-SHA256 后 Base64，放入请求体 `sign` 字段。

### `config.py`

新增 `ChatConfig` dataclass：

```python
@dataclass
class ChatConfig:
    feishu_webhook: str = ""
    feishu_secret: str = ""
    
    @property
    def is_configured(self) -> bool:
        return bool(self.feishu_webhook)
    
    @classmethod
    def from_dict(cls, d) -> "ChatConfig": ...
    def to_dict(self) -> dict: ...
```

`AppConfig` 新增字段 `chat: Optional[ChatConfig] = None`。

### `app.py`

| 位置 | 改动 |
|------|------|
| `on_mount()` | 初始化 `self._chat_cfg = self._cfg.chat` |
| `_fire_alert()` | 末尾追加飞书卡片发送（`asyncio.create_task`，非阻塞） |
| `_daily_summary_loop()` | 邮件发送后追加飞书汇总卡片 |
| `_reload_config_if_changed()` | 同步 `self._chat_cfg` |

## 卡片消息格式

### 告警卡片

```
Header: ⚠️ 股票告警

Elements:
  - 代码: ustsla
  - 名称: 特斯拉
  - 现价: $305.50
  - 触发条件: 价格上破 300
  - 涨跌幅: +2.35%
  - 时间: 2025-06-30 14:30:00
```

### 每日汇总卡片

```
Header: 📊 每日持仓汇总 — 2025-06-30

Elements:
  - ustsla  特斯拉    $305.50   +2.35%
  - usgoog  谷歌      $180.20   -0.50%
  - ...
```

## 文件清单

| 文件 | 操作 |
|------|------|
| `src/stock_watcher/chat_sender.py` | 新增 |
| `src/stock_watcher/config.py` | 修改：加 ChatConfig |
| `src/stock_watcher/app.py` | 修改：3 处追加 |
| `config.yaml` | 修改：加 chat 段 |
| `tests/test_chat_sender.py` | 新增 |

## 测试策略

- `test_build_alert_card` — 卡片结构正确
- `test_build_summary_card` — 汇总卡片结构正确
- `test_sign_generation` — HMAC-SHA256 签名正确
- `test_send_feishu_mocked` — HTTP 请求格式正确（用 respx mock）
- `test_chat_config_loading` — 从 YAML 加载 ChatConfig

现有 168 个测试应继续全部通过。
