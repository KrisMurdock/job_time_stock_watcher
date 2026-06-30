# Stock Watcher — User Journeys

## UJ-1: Launch & Monitor
**As a** user,
**I want to** launch the stock watcher and see live stock prices for my configured watchlist,
**so that** I can monitor my portfolio at a glance without opening multiple apps.

**Acceptance criteria:**
- App reads `config.yaml` and displays all stocks from the watchlist
- Each row shows: code, name, current price, change%, change amount, high, low
- Prices auto-refresh on a per-stock queued schedule (2-3s between requests)
- Color coding: red for price up, green for price down, white for unchanged
- Top bar shows refresh status and last update time
- Bottom bar shows available keyboard shortcuts

---

## UJ-2: Add Stock at Runtime
**As a** user,
**I want to** add a new stock code while the app is running,
**so that** I can expand my watchlist without restarting.

**Acceptance criteria:**
- Press `a` to trigger add mode
- Input field accepts a market-prefixed code (sh000001 / sz000001 / hk00700)
- Validates the prefix before accepting
- New stock appears in the table and starts polling immediately
- Watchlist is persisted to config.yaml on add

---

## UJ-3: Remove Stock at Runtime
**As a** user,
**I want to** remove a stock from the watchlist,
**so that** I can keep my dashboard focused on what matters.

**Acceptance criteria:**
- Press `d` to remove the currently highlighted stock
- Confirmation prompt before removal
- Stock stops polling immediately
- Watchlist is persisted to config.yaml on removal

---

## UJ-4: Price Change Visual Feedback
**As a** user,
**I want to** see at a glance which stocks are up or down,
**so that** I can quickly assess market movement.

**Acceptance criteria:**
- Positive change% displayed in red with ↑ arrow
- Negative change% displayed in green with ↓ arrow
- Zero change displayed in default color with →
- Row highlight changes momentarily when price updates

---

## UJ-5: Graceful Error Handling
**As a** user,
**I want to** the app to handle network and API errors without crashing,
**so that** I can rely on it during volatile market conditions.

**Acceptance criteria:**
- Individual stock fetch failures show "N/A" for that stock, others keep updating
- Consecutive failures trigger exponential backoff (5s → 10s → 20s → ... → max 120s)
- Backoff resets on first successful fetch
- Status bar shows error count or "⚠ API Error" when all stocks are failing
- App never crashes due to network errors

---

## UJ-6: Trading Hours Awareness
**As a** user,
**I want to** the app to pause polling when markets are closed,
**so that** it doesn't waste requests or risk IP bans during off-hours.

**Acceptance criteria:**
- A-share polling stops outside 9:30-11:30, 13:00-15:00 Beijing time (Mon-Fri)
- HK polling stops outside 9:30-12:00, 13:00-16:00 HKT (Mon-Fri)
- Status bar shows "休市" (market closed) during off-hours
- Polling auto-resumes when market opens

---

## UJ-7: Manual Refresh
**As a** user,
**I want to** manually trigger a refresh even during off-hours,
**so that** I can check the last known price when markets are closed.

**Acceptance criteria:**
- Press `r` to force-refresh all stocks regardless of trading hours
- Manual refresh does not reset the auto-polling backoff state
- Status bar briefly shows "手动刷新..." during manual refresh
- Failed manual refresh shows error state but still doesn't crash

---

## UJ-8: Persistent Configuration
**As a** user,
**I want to** my watchlist changes to survive app restarts,
**so that** I don't have to re-enter stocks every time.

**Acceptance criteria:**
- Adding a stock writes the updated list to config.yaml immediately
- Removing a stock writes the updated list to config.yaml immediately
- Config file preserves YAML structure and comments on update (best effort)
- Corrupted config file shows a clear error on startup
