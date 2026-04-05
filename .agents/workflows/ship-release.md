---
description: How to ship a new SDK release to PyPI — mandatory pre-publish checklist
---

# Ship Release Workflow

**Rule: Never publish to PyPI without completing every step below.**

## 1. Pre-Flight: Test As A User

Before touching version numbers, test the CURRENT code as a fresh user would:

```bash
# Install from local source
pip install -e .

# Test the EXACT commands a new user runs:
sentinel --version
sentinel --help
sentinel auth                    # ← Must work with NO flags (interactive)
sentinel auth --key sk-ant-xxx   # ← Must work with flag too
sentinel auth --help             # ← Help text must be clear
```

// turbo-all

**If ANY of these fail, STOP. Fix first. Do not proceed.**

## 2. Test Core Flows

```bash
# After auth succeeds, test the next commands:
sentinel status
sentinel tools
sentinel call get_crypto_price --param coin_id=bitcoin
sentinel vault --help
```

// turbo-all

**All must work or show clear, actionable error messages (not stack traces).**

## 3. Bump Version

Only after steps 1-2 pass:

```bash
# Edit pyproject.toml: version = "X.Y.Z"
# Edit src/sentinel/__init__.py: __version__ = "X.Y.Z"
# Edit src/sentinel/__init__.py: docstring header
```

## 4. Build

```bash
rm -rf dist/ build/
python3 -m build
```

// turbo

## 5. Test The Built Package (Not Source)

```bash
# Install the BUILT wheel, not the source
pip install dist/hyper_sentinel-*.whl --force-reinstall

# Re-run the user flow tests
sentinel --version    # Must show new version
sentinel auth         # Must prompt interactively
```

// turbo-all

**If the built package fails, STOP. Do not publish.**

## 6. Publish

```bash
python3 -m twine upload dist/*
```

## 7. Verify From PyPI

```bash
pip install hyper-sentinel==X.Y.Z --no-cache-dir --force-reinstall
sentinel --version
sentinel auth
```

// turbo-all

## 8. Commit & Push

```bash
git add -A
git commit -m "chore: release vX.Y.Z — [one-line summary]"
git push origin main
```

---

## Anti-Patterns (Do NOT Do These)

| Bad | Why |
|-----|-----|
| Bump version → build → publish → "hope it works" | Skips ALL testing |
| Test only with `python3 -c "import sentinel"` | Proves import, not UX |
| Ship with `required=True` on CLI args without prompts | Crashes on basic usage |
| Publish then say "just install the next version" | User already lost trust |
| Test only the happy path | Edge cases = user's first experience |

---

*This workflow exists because v0.5.1 shipped with `sentinel auth` broken.*
*Never again.*
