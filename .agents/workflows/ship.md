---
description: AI-powered SDLC workflow for shipping Sentinel SDK versions. Run /ship to see the full release pipeline with AI prompts for each stage.
---

# 🚀 Sentinel Ship Workflow — AI-Augmented SDLC

## Overview

This workflow defines the end-to-end process for shipping a new Sentinel SDK version.
Each stage has a specific **AI prompt** you can paste into Claude Code, Claude Cowork, or Antigravity.

The pipeline: **Plan → Build → Smoke → Test → Ship → Announce**

---

## Stage 1: PLAN — Define the Release Scope

**When:** Starting a new version (e.g., 0.4.0)
**Who:** You + AI (planning mode)

### Prompt (paste into Claude):

```
I'm planning Sentinel SDK v[VERSION]. Here's what I want:

1. [Feature 1]
2. [Feature 2]
3. [Feature 3]

Review the current codebase at /Users/morganm2max/Antigravity/Python/sentinel-sdk/
and create an implementation plan artifact with:
- File-level changes needed
- New tools to add (schemas + dispatch + DIRECT_TOOLS + client methods)
- Estimated complexity
- Execution order (what to build first)
- What to test

Reference the existing patterns in chat.py for tool schemas,
scrapers/ for module structure, and client.py for typed methods.
```

### Output: Implementation plan artifact (like impl_plan_040.md)

---

## Stage 2: BUILD — Write the Code

**When:** Implementation plan is approved
**Who:** You + AI (coding mode)

### Prompt (paste into Claude):

```
Execute Phase [N] of the v[VERSION] implementation plan at:
/Users/morganm2max/.gemini/antigravity/brain/[CONVERSATION_ID]/impl_plan_[VERSION].md

Follow the plan exactly. For each new tool:
1. Create the scraper function in src/sentinel/scrapers/
2. Add the tool schema to TOOL_SCHEMAS in chat.py
3. Add the dispatch handler in the execute_tool function in chat.py
4. Add to DIRECT_TOOLS set in chat.py
5. Add typed method to client.py
6. Add to EXPECTED_TOOLS in tests/test_client.py

After writing code, run: python3 scripts/smoke_test.py
Fix any failures before reporting done.
```

### Output: Working code + passing smoke test

---

## Stage 3: SMOKE — Pre-Ship Validation

**When:** Code is written, before any PyPI upload
**Who:** AI (automated)

### Command:

```bash
// turbo
cd /Users/morganm2max/Antigravity/Python/sentinel-sdk && make smoke
```

This runs `scripts/smoke_test.py` which checks:
- ✅ Version sync (pyproject.toml == __init__.py)
- ✅ All core modules import
- ✅ All 11+ scrapers import (with optional dep tolerance)
- ✅ Tool schema validation (all have name/description/parameters)
- ✅ Tool count >= minimum (only goes up)
- ✅ New tools wired into DIRECT_TOOLS
- ✅ No stale references (old version numbers, wrong tool counts)
- ✅ All .py files have valid syntax

**If anything fails → fix it before proceeding. This is what prevents patch releases.**

---

## Stage 4: TEST — Run the Full Suite

**When:** Smoke passes
**Who:** AI (automated)

### Command:

```bash
// turbo
cd /Users/morganm2max/Antigravity/Python/sentinel-sdk && make test
```

This runs smoke test + pytest (25+ assertions on client, exceptions, billing, tool methods).

### Prompt (if tests fail):

```
The following tests failed in sentinel-sdk:

[paste test output]

Fix the failures. Do NOT change test assertions unless the test is
genuinely stale (checking old version numbers, removed features, etc).
If the test is valid, fix the code, not the test.
```

---

## Stage 5: BUMP — Version Update

**When:** All tests pass, ready to ship
**Who:** You (confirm version number)

### Command:

```bash
cd /Users/morganm2max/Antigravity/Python/sentinel-sdk && make bump V=0.4.0
```

This updates version in:
- `pyproject.toml`
- `src/sentinel/__init__.py`

### Then update the __init__.py docstring:

```
Update the docstring in src/sentinel/__init__.py to reflect v0.4.0:
- Update tool count (e.g., "51 tools" → "55 tools")
- Update any feature descriptions
- Keep the Soli Deo Gloria dedication
```

---

## Stage 6: SHIP — Build + Tag + Upload

**When:** Version is bumped, docstring updated
**Who:** You (final approval)

### Command:

```bash
cd /Users/morganm2max/Antigravity/Python/sentinel-sdk && make release
```

This will:
1. Re-run smoke + pytest
2. Build the package (`python3 -m build`)
3. Git commit + tag
4. Print the twine upload command

### Then you manually run:

```bash
twine upload dist/hyper_sentinel-0.4.0*
git push origin main --tags
```

---

## Stage 7: VERIFY — Post-Ship Check

**When:** Package is on PyPI
**Who:** AI (browser verification)

### Prompt:

```
Verify the hyper-sentinel 0.4.0 release:
1. Check https://pypi.org/project/hyper-sentinel/ shows version 0.4.0
2. Run: pip install hyper-sentinel==0.4.0 --force-reinstall
3. Run: python3 -c "import sentinel; print(sentinel.__version__)"
4. Run: sentinel (check if it boots with correct version in banner)
5. Test one tool: type "bitcoin price" and verify it works
```

---

## Stage 8: DOCS — Update Documentation

**When:** After successful ship
**Who:** AI (docs mode)

### Prompt:

```
Update documentation for Sentinel SDK v[VERSION]:
1. Update sentinel-sdk/README.md with new tool count and changelog
2. Update hyper-sentinel/README.md if features affect the main program
3. Create a release brief artifact for the CTO
4. Update the teaser brief if it's a major feature

Reference the changes made in this session.
Keep the Soli Deo Gloria dedication in all docs.
```

---

## Stage 9: BACKPORT — Sync to hyper-sentinel (if needed)

**When:** New SDK features should also work in the private terminal
**Who:** AI (porting mode)

### Prompt:

```
Backport the v[VERSION] SDK changes to hyper-sentinel:
1. Copy relevant scraper logic to hyper-sentinel/scrapers/ or core/
2. Wire new tools into hyper-sentinel's main.py dispatch
3. Update hyper-sentinel/README.md
4. Test that hyper-sentinel still boots: python3 main.py

Use the SDK implementation as the reference but adapt to
hyper-sentinel's dispatch pattern (no ToolRegistry, uses direct
function calls in the main command loop).
```

---

## Quick Reference: The Full Pipeline

```
/ship 0.4.0

  1. PLAN     →  "Create impl plan for v0.4.0 with [features]"
  2. BUILD    →  "Execute Phase N of the plan"
  3. SMOKE    →  make smoke
  4. TEST     →  make test
  5. BUMP     →  make bump V=0.4.0
  6. SHIP     →  make release → twine upload
  7. VERIFY   →  Check PyPI + test install
  8. DOCS     →  Update READMEs + briefs
  9. BACKPORT →  Sync to hyper-sentinel (optional)
```

---

## Anti-Patterns (What NOT to do)

| ❌ Don't | ✅ Do Instead |
|---|---|
| `twine upload` without running smoke | `make release` (includes smoke + test) |
| Fix bugs by patching (0.3.15, 0.3.16...) | Fix before ship with `make smoke` |
| Commit directly to main | Work on `dev` branch, merge when ready |
| Hardcode version in tests | Read from pyproject.toml dynamically |
| Skip DIRECT_TOOLS wiring | Smoke test catches this automatically |
| Forget to update tool count in docs | Smoke test checks for stale claims |

---

## File Map

```
sentinel-sdk/
├── Makefile                    ← make smoke / test / release / bump
├── scripts/smoke_test.py      ← 23-check pre-ship validation
├── tests/test_client.py       ← 25 assertions (client, tools, billing)
├── tests/test_integration.py  ← Live gateway tests (run separately)
├── src/sentinel/
│   ├── __init__.py             ← version + first-run hint
│   ├── chat.py                 ← TOOL_SCHEMAS + dispatch + DIRECT_TOOLS
│   ├── client.py               ← typed methods for all tools
│   └── scrapers/               ← one file per data source
└── pyproject.toml              ← version + dependencies
```
