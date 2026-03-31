#!/usr/bin/env python3
"""
Pre-ship smoke test — catches the bugs that used to require patch releases.

Run:  python3 scripts/smoke_test.py
  or: make smoke

Every check here exists because a real bug slipped through in 0.3.1–0.3.14.
"""

import sys
import re
import ast
import importlib.util

PASS = "✅"
FAIL = "❌"
errors = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS} {label}")
    else:
        msg = f"{label}: {detail}" if detail else label
        errors.append(msg)
        print(f"  {FAIL} {label} — {detail}")


def main():
    print("─" * 50)
    print("  Sentinel SDK — Pre-Ship Smoke Test")
    print("─" * 50)
    print()

    # ── 1. Version sync (caused 0.3.7) ───────────────────────
    print("📋 Version")
    with open("pyproject.toml") as f:
        pyproject = f.read()
    with open("src/sentinel/__init__.py") as f:
        init = f.read()

    toml_ver = re.search(r'version\s*=\s*"(.+?)"', pyproject)
    init_ver = re.search(r'__version__\s*=\s*"(.+?)"', init)

    toml_v = toml_ver.group(1) if toml_ver else "NOT FOUND"
    init_v = init_ver.group(1) if init_ver else "NOT FOUND"

    check("pyproject.toml version", toml_ver is not None, f"Got: {toml_v}")
    check("__init__.py version", init_ver is not None, f"Got: {init_v}")
    check("Versions match", toml_v == init_v, f"pyproject={toml_v} vs init={init_v}")
    print()

    # ── 2. Core imports (caused 0.3.8, 0.3.12) ──────────────
    print("📦 Core Imports")
    core_modules = [
        ("sentinel", "Package root"),
        ("sentinel.client", "SentinelClient"),
        ("sentinel.chat", "CLI/REPL"),
        ("sentinel.exceptions", "Error classes"),
    ]
    for mod, label in core_modules:
        try:
            importlib.import_module(mod)
            check(f"import {mod}", True)
        except Exception as e:
            check(f"import {mod}", False, str(e)[:80])
    print()

    # ── 3. Scraper imports (caused 0.3.2, 0.3.6, 0.3.8) ────
    print("🔌 Scraper Imports")
    scrapers = [
        "sentinel.scrapers.crypto",
        "sentinel.scrapers.dexscreener",
        "sentinel.scrapers.hyperliquid",
        "sentinel.scrapers.aster",
        "sentinel.scrapers.polymarket",
        "sentinel.scrapers.fred",
        "sentinel.scrapers.ta",
        "sentinel.scrapers.portfolio",
        "sentinel.scrapers.elfa",
        "sentinel.scrapers.y2",
        "sentinel.scrapers.x",
    ]
    for mod in scrapers:
        try:
            importlib.import_module(mod)
            check(f"import {mod.split('.')[-1]}", True)
        except ImportError as e:
            # Some scrapers have optional deps — that's OK
            err_str = str(e)
            if "No module named" in err_str:
                missing = err_str.split("'")[1] if "'" in err_str else err_str
                # Optional deps are OK (hyperliquid, py_clob_client, etc.)
                optional = ["hyperliquid", "py_clob_client", "telethon", "discord", "upsonic"]
                if any(o in missing for o in optional):
                    check(f"import {mod.split('.')[-1]}", True)
                else:
                    check(f"import {mod.split('.')[-1]}", False, f"Missing: {missing}")
            else:
                check(f"import {mod.split('.')[-1]}", False, err_str[:80])
        except Exception as e:
            check(f"import {mod.split('.')[-1]}", False, str(e)[:80])
    print()

    # ── 4. Tool schema validation ────────────────────────────
    print("🔧 Tool Schemas")
    try:
        from sentinel.chat import TOOL_SCHEMAS
        check(f"TOOL_SCHEMAS list loads ({len(TOOL_SCHEMAS)} tools)", True)

        # Every tool must have name + description + parameters
        bad_tools = []
        for t in TOOL_SCHEMAS:
            if not t.get("name") or not t.get("description") or "parameters" not in t:
                bad_tools.append(t.get("name", "UNNAMED"))
        check("All tools have name/description/parameters", len(bad_tools) == 0,
              f"Bad: {bad_tools}" if bad_tools else "")

        # Check minimum tool count (should only go up)
        check(f"Tool count >= 51", len(TOOL_SCHEMAS) >= 51, f"Found {len(TOOL_SCHEMAS)}")

    except Exception as e:
        check("TOOLS list loads", False, str(e)[:80])
    print()

    # ── 5. DIRECT_TOOLS coverage ─────────────────────────────
    print("🎯 DIRECT_TOOLS Coverage")
    try:
        with open("src/sentinel/chat.py") as f:
            chat_source = f.read()

        # Extract tool names from TOOLS schema list
        tool_names = set(re.findall(r'"name":\s*"([a-z_]+)"', chat_source[:40000]))

        # Extract DIRECT_TOOLS names
        dt_match = re.search(r'DIRECT_TOOLS\s*=\s*\{([^}]+)\}', chat_source, re.DOTALL)
        if dt_match:
            direct_names = set(re.findall(r'"([a-z_]+)"', dt_match.group(1)))
            # Not all tools need to be in DIRECT_TOOLS (some use gateway)
            # But check that new tools we added are wired
            new_tools = {"get_portfolio_summary", "get_portfolio_risk"}
            missing = new_tools - direct_names
            check("New tools in DIRECT_TOOLS", len(missing) == 0,
                  f"Missing: {missing}" if missing else "")
        else:
            check("DIRECT_TOOLS found", False, "Could not parse DIRECT_TOOLS")

    except Exception as e:
        check("DIRECT_TOOLS check", False, str(e)[:80])
    print()

    # ── 6. No stale version references ───────────────────────
    print("🧹 Stale References")
    try:
        with open("src/sentinel/chat.py") as f:
            chat_content = f.read()

        # Check the banner/boot section doesn't hardcode old versions
        stale_patterns = [
            (r'Version 0\.3\.\d+', "Hardcoded 0.3.x in chat.py"),
            (r'80\+ tools', "Stale '80+ tools' claim"),
            (r'70\+ tools', "Stale '70+ tools' claim"),
        ]
        for pattern, desc in stale_patterns:
            found = re.search(pattern, chat_content)
            check(f"No '{desc}'", found is None, f"Found at char {found.start()}" if found else "")

    except Exception as e:
        check("Stale reference check", False, str(e)[:80])
    print()

    # ── 7. Syntax check on all Python files ──────────────────
    print("📝 Syntax Check")
    import glob
    py_files = glob.glob("src/sentinel/**/*.py", recursive=True)
    syntax_errors = []
    for f in py_files:
        try:
            with open(f) as fh:
                ast.parse(fh.read())
        except SyntaxError as e:
            syntax_errors.append(f"{f}: {e}")
    check(f"All {len(py_files)} .py files parse", len(syntax_errors) == 0,
          "; ".join(syntax_errors) if syntax_errors else "")
    print()

    # ── Summary ──────────────────────────────────────────────
    print("─" * 50)
    if errors:
        print(f"  {FAIL} {len(errors)} issue(s) found:")
        for e in errors:
            print(f"     • {e}")
        print()
        print("  Fix these before shipping!")
        sys.exit(1)
    else:
        print(f"  {PASS} All checks passed — ready to ship v{toml_v}")
        sys.exit(0)


if __name__ == "__main__":
    main()
