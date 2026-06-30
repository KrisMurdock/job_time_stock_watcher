# 02 — Ctrl+N hot-reload + misc bug fixes

Status: 📋 todo  
Labels: bug, phase-0

## Problem

`config.yaml` line 4 documents "按 Ctrl+N 即可热加载" but no such keybinding exists.
Hot-reload is fully automatic (file mtime polling), but there's no way for the user
to force an immediate reload.

## Done when

- [ ] Add `Binding("ctrl+n", "reload_config", "热加载")` to `BINDINGS`
- [ ] Add `action_reload_config` that forces `_reload_config_if_changed()` logic
- [ ] Config comment on line 4 updated to say both auto and Ctrl+N
- [ ] Test: edit config.yaml, press Ctrl+N, changes applied immediately
