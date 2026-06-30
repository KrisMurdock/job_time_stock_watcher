# Stock Watcher

> Real-time stock monitor in the terminal — A-shares, HK, and US markets.

[中文](README_CN.md)

![Stock Watcher TUI](docs/image.png)

## Features

- **Multi-market** — Shanghai (`sh`), Shenzhen (`sz`), Hong Kong (`hk`), and US (`us`) stocks
- **Live polling** — auto-refreshes during trading hours, pauses when markets close
- **Sortable table** — click column headers to sort by price, change%, P&L, and more
- **Price alerts** — configurable thresholds (price above/below, change% above/below) with bell + system notification
- **Position tracking** — record cost, quantity, and see unrealized P&L per stock
- **Detail panel** — bid/ask order book (A-shares), PE ratio (HK), recent alert history
- **Feishu push** (optional) — alert cards and periodic summaries to a Feishu/Lark group
- **AI chat** (optional) — DeepSeek-powered `@bot` replies inside Feishu groups
- **Privacy mode** — one-key disguise: all stock names and numbers hidden
- **CSV export** — dump the current table to a timestamped `.csv` file
- **Hot reload** — edit `config.yaml` or `positions.yaml` without restarting

## Prerequisites

- **Python** ≥ 3.11
- **pip** (or your favourite package manager)

## Quick Start

```bash
# Clone
git clone https://github.com/KrisMurdock/job_time_stock_watcher.git
cd job_time_stock_watcher

# Install dependencies
pip install -e .

# Copy example config files
cp config.yaml.example config.yaml
cp positions.yaml.example positions.yaml

# Edit watchlist
# Open config.yaml and replace the stock codes with your own

# Run
python -m stock_watcher.app
```

Or use the convenience script:

```bash
./run.sh
```

## Configuration

All settings live in `config.yaml`. A documented example is at [`config.yaml.example`](config.yaml.example).

### Core settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `poll_interval` | float | `2.5` | Seconds between each stock fetch |
| `watchlist` | list | *example* | Stock codes with market prefixes |
| `alerts` | list | `[]` | Alert rules (see below) |
| `proxies` | list | `[]` | HTTP proxy URLs (e.g. `http://127.0.0.1:7890`) |

### Request tuning

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `request.timeout` | int | `10` | HTTP timeout (seconds) |
| `request.user_agent_pool` | list | *browsers* | UA strings, one picked per request |

### Backoff (exponential retry)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backoff.base` | float | `5` | Initial delay (seconds) |
| `backoff.max` | float | `120` | Maximum delay |
| `backoff.multiplier` | float | `2` | Exponent factor per failure |

### Alert sound

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `alert_sound_command` | string | `""` | Shell command for custom audio (Linux: `paplay`, macOS: `afplay`) |

### Stock codes

Prefixes map to markets:

| Prefix | Market | Example |
|--------|--------|---------|
| `sh` | Shanghai A-share | `sh600519` (Kweichow Moutai) |
| `sz` | Shenzhen A-share | `sz000001` (Ping An Bank) |
| `hk` | Hong Kong | `hk00700` (Tencent) |
| `us` | US | `ustsla` (Tesla), `usaapl` (Apple) |

### Alerts

Alert rules live under the `alerts` key. Each rule has three fields:

```yaml
alerts:
  - code: hk00700        # stock code
    type: price_above    # price_above | price_below | pct_above | pct_below
    value: 433.0         # threshold (yuan for price, number for %)
```

### Positions

Positions are stored in a separate file — `positions.yaml`. Copy the example:

```bash
cp positions.yaml.example positions.yaml
```

Format:

```yaml
hk00700:
  cost: 430.0       # buy-in average cost (yuan)
  quantity: 100     # total shares held
  available: 100    # tradable shares
```

Hot-reloaded — no restart needed.

## Usage

### Key bindings

| Key | Action |
|-----|--------|
| `a` | **Add stock** — enter code or name to search |
| `d` | **Delete stock** — remove the highlighted row |
| `t` | **Set alert** — `pa 450` (price above), `pb 420` (price below), `ca 5` (change% above), `cb 3` (change% below) |
| `v` | **View alerts** — list all alert rules, press `d` to delete one |
| `h` | **Alert history** — last 200 fired alerts |
| `p` | **Set position** — `420 200` (cost 420 yuan, 200 shares). Empty to delete. |
| `s` | **Settings** — show current config |
| `e` | **Export CSV** |
| `r` | **Manual refresh** — force-refresh all stocks |
| `x` | **Privacy mode** — hide all stock names and numbers |
| `Enter` | **Detail popup** — full info for highlighted stock |
| `Ctrl+N` | **Reload config** — hot-reload `config.yaml` and `positions.yaml` |
| `Esc` | **Close / cancel** — dismiss any popup or prompt |
| `Click header` | **Sort** — click column header to sort (asc → desc → unsort) |
| `q` | **Quit** |

### Status bar (top)

Shows market status (trading / closed), clock, fetch latency, stock counts (↑ / ↓ / →), and error/backoff state.

### Portfolio bar (bottom)

Shows total positions, total market value, and total unrealized P&L (amount + %), green for profit, red for loss.

## Integrations (optional)

### Feishu / Lark bot

1. In your Feishu group, add a **custom bot** (webhook)
2. Copy the webhook URL into `config.yaml`:
   ```yaml
   chat:
     feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-WEBHOOK"
   ```
3. The bot will send alert cards and periodic market summaries

For bidirectional `@bot` chat, you also need a Feishu app with WebSocket enabled:

```yaml
chat:
  feishu_app_id: "YOUR-APP-ID"
  feishu_app_secret: "YOUR-APP-SECRET"
```

### DeepSeek AI

When Feishu bidirectional bot is enabled, `@bot` mentions are answered by DeepSeek:

```yaml
deepseek:
  api_key: "YOUR-API-KEY"   # get from https://platform.deepseek.com/api_keys
  model: "deepseek-chat"
```

## Project Layout

```
.
├── config.yaml.example      # annotated config template
├── positions.yaml.example   # position data template
├── run.sh                   # convenience launch script
├── pyproject.toml           # project metadata and dependencies
├── docs/
│   ├── image.png            # TUI screenshot
│   └── adr/                 # architecture decision records
├── src/stock_watcher/
│   ├── app.py               # TUI application (entry point)
│   ├── config.py            # config loading, hot-reload, persistence
│   ├── fetcher.py           # market data API clients (Sina, Tencent)
│   ├── models.py            # data models (Quote, Alert, Position, etc.)
│   ├── chat_sender.py       # Feishu webhook card sender
│   ├── bot_server.py        # Feishu WebSocket bidirectional bot
│   └── deepseek_chat.py     # DeepSeek AI integration
└── tests/
    ├── test_app.py          # TUI integration tests
    ├── test_config.py       # config parsing and persistence tests
    ├── test_fetcher.py      # API fetcher tests
    ├── test_models.py       # model unit tests
    └── test_scheduler.py    # polling and backoff tests
```

## License

MIT
