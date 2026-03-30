---
description: Full SDK test, audit, fix, and release cycle for hyper-sentinel
---

# Sentinel SDK Release Cycle

## Context

You are working on `hyper-sentinel`, a Python SDK + AI trading agent published to PyPI.

**Repo**: `/Users/morganm2max/Antigravity/Python/sentinel-sdk`
**Package**: `hyper-sentinel` on PyPI
**Current version**: Check `src/sentinel/__init__.py` for `__version__`
**Docs repo**: `/Users/morganm2max/Antigravity/Python/hyper-sentinel-docs`

## Phase 1: Install & Smoke Test

// turbo-all

1. Install the latest version from PyPI:
```bash
pip install --no-cache-dir hyper-sentinel && sentinel -v
```

2. Launch `sentinel-chat` and test these commands IN ORDER. Copy the full terminal output for each:
```
status
add
add hl        # Enter test wallet: 0xTEST123 → then Enter to skip private key
add fred      # Enter test key: test_fred_key
add x         # Enter test key: test_x_key
add y2        # Enter test key: test_y2_key
add elfa      # Enter test key: test_elfa_key
```

3. After each `add` command, verify:
   - ✅ Key saves without error
   - ✅ Prompt returns immediately (no hang)
   - ✅ No traceback

4. Exit and relaunch to verify dashboard:
```
quit
sentinel-chat
```
   - ✅ Dashboard shows green "● Ready" for configured sources
   - ✅ Source count is accurate (not stuck at 3)

5. Test Fast Path queries:
```
price of btc
price of btc and eth and sol
top 10 crypto
```
   - ✅ Instant response (< 1 second)
   - ✅ No "Sentinel thinking..." message
   - ✅ Real price data returned

6. Test LLM query:
```
what is the market cap of bitcoin
```
   - ✅ Shows "Sentinel thinking..."
   - ✅ Returns real data
   - ✅ Ctrl+C during thinking returns to prompt (no crash)

7. Test error cases:
```
price of invalidcoin123
get hl positions
```

## Phase 2: Code Audit

Read and audit these critical files:

1. `src/sentinel/chat.py` — Focus on:
   - `_fast_path()` function: regex patterns, coin alias map completeness
   - `_execute_direct()` function: all scraper dispatch tables
   - `DIRECT_TOOLS` set: must match every function in `_execute_direct`
   - `TOOL_SCHEMAS` list: all tools must have valid JSON schemas
   - Dashboard status: config key names must match what `add` commands save
   - SYSTEM_PROMPT: no hardcoded dates, accurate version info

2. `src/sentinel/cli.py` — Focus on:
   - `ADD_HANDLERS` dict: config key names
   - `_step_hyperliquid`, `_step_polymarket`, `_step_aster`, `_step_telegram`: config key names saved
   - `_verify_after_save`: must NOT create SentinelClient (causes gateway hang)

3. `src/sentinel/scrapers/*.py` — For each scraper:
   - Verify function signatures match what `_execute_direct` calls
   - Verify config/env var names match what `add` commands save
   - Check for import errors or missing dependencies

4. Cross-reference audit:
   - Every function in `_execute_direct` dispatch → must be in `DIRECT_TOOLS`
   - Every config key in dashboard → must match what `_add_service` saves
   - Every scraper function → must have a matching TOOL_SCHEMA entry

## Phase 3: Fix Issues

For any issues found in Phase 2:
1. Fix the code
2. Verify syntax: `python3 -c "import ast; ast.parse(open('FILE').read())"`
3. Document what you fixed

## Phase 4: Update Documentation

1. Update `README.md` if any tools/features changed
2. Update `/Users/morganm2max/Antigravity/Python/hyper-sentinel-docs/sdk/README.md` to match
3. Ensure tool counts are accurate
4. Ensure architecture diagram reflects current state

## Phase 5: Build & Publish

1. Bump version in BOTH files:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `src/sentinel/__init__.py` → `__version__ = "X.Y.Z"`

2. Build:
```bash
cd /Users/morganm2max/Antigravity/Python/sentinel-sdk
rm -rf dist/ build/
python3 -m build
```

3. Publish to PyPI:
```bash
python3 -m twine upload dist/*
```

4. Git commit and push:
```bash
git add -A
git commit -m "vX.Y.Z — [summary of changes]"
git push origin main
```

5. Push docs if updated:
```bash
cd /Users/morganm2max/Antigravity/Python/hyper-sentinel-docs
git add -A
git commit -m "docs: update for vX.Y.Z"
git push origin main
```

## Phase 6: Verify Published Version

```bash
pip install --no-cache-dir hyper-sentinel==X.Y.Z
sentinel -v
sentinel-chat
# Run smoke tests from Phase 1 again
```

## Output

After completing all phases, provide:
1. **Test Results**: Pass/fail for each smoke test
2. **Bugs Found**: List of issues discovered during audit
3. **Fixes Applied**: What was changed and why
4. **Version Published**: New version number
5. **Remaining Issues**: Anything that needs follow-up
