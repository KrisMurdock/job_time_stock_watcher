# 01 — Fix broken stock search

Status: 📋 todo  
Labels: bug, phase-0

## Problem

`_parse_suggest_response()` in `fetcher.py` uses wrong field indices and wrong
market type mapping, causing **all search results to be silently discarded**.

Three bugs compound:
1. **Field order** (line 314–316): API returns `name,market_type,code` but code
   parses as `code,name,market`, so `_sina_market_to_prefix()` receives garbage.
2. **Wrong HK type** (line 335–338): maps `"13"` → `"hk"` but type 13 is not HK
   (API returns empty). Correct HK type is `"31"`.
3. **Missing type 31** (line 268): suggest URL `type=11,12,13,14,15` never includes
   `31`, so HK stocks are never returned even if parsing were fixed.

## Done when

- [ ] Field indices swapped: parts[0]=name, parts[1]=market_type, parts[2]=raw_code
- [ ] `_sina_market_to_prefix()`: add `"31": "hk"`, remove `"13"`
- [ ] Suggest URL includes `31` for HK stocks
- [ ] `search_stocks("腾讯")` returns `hk00700` as a result
- [ ] `search_stocks("平安")` returns A + HK matches
- [ ] Tests pass
