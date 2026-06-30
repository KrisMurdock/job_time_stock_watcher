# 10 — Settings panel

Status: 📋 todo  
Labels: feature, phase-5

## Summary

A modal dialog to edit core configuration values from within the TUI,
without touching config.yaml directly.

## Trigger

Key `s` → modal overlay with editable fields.

## Editable settings

| Label | Config key | Type | Default | Range |
|-------|-----------|------|---------|-------|
| 轮询间隔(秒) | `poll_interval` | float | 2.5 | 0.5–60 |
| 请求超时(秒) | `request.timeout` | float | 10.0 | 1–60 |
| 退避基数(秒) | `backoff.base` | float | 5.0 | 1–300 |
| 退避上限(秒) | `backoff.max` | float | 120.0 | 10–600 |
| 退避乘数 | `backoff.multiplier` | float | 2.0 | 1.1–10 |
| 告警音效命令 | `alert_sound_command` | str | "" | — |

## UX

- Navigate settings with Tab/Shift+Tab
- Edit in-place (Textual Input widgets)
- Enter on a field: edit; Enter again: confirm; Escape: cancel edit
- `Ctrl+S` or a "保存" button: validate + write to config.yaml + hot-reload
- `Escape`: discard changes, close

## Validation

- Numeric fields: must be within range, show error inline if invalid
- Sound command: free text, no validation

## Persistence

Write changed values back to `config.yaml` using text-level patching
(preserve comments). Trigger `_reload_config_if_changed()` after save.

## Done when

- [ ] Settings panel opens on `s` key
- [ ] All 6 settings editable with validation
- [ ] Save writes to config.yaml
- [ ] Cancel discards changes
- [ ] Hot-reload applies new values immediately
