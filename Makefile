.PHONY: smoke test release clean dev-setup

PYTHON := python3
VERSION ?= $(shell $(PYTHON) -c "import re; print(re.search(r'version.*?\"(.+?)\"', open('pyproject.toml').read()).group(1))")

# ── Pre-ship smoke test (catches 90% of patch-release bugs) ──
smoke:
	@echo "🔍 Smoke testing v$(VERSION)..."
	@$(PYTHON) scripts/smoke_test.py
	@echo ""
	@echo "✅ All smoke tests passed — safe to ship"

# ── Full test suite ──────────────────────────────────────────
test: smoke
	@echo ""
	@echo "🧪 Running pytest..."
	@$(PYTHON) -m pytest tests/ -v --tb=short -x
	@echo ""
	@echo "✅ All tests passed"

# ── Build distribution ──────────────────────────────────────
build: test
	@echo ""
	@echo "📦 Building v$(VERSION)..."
	@rm -rf dist/ build/ *.egg-info src/*.egg-info
	@$(PYTHON) -m build
	@echo ""
	@echo "✅ Built: dist/"
	@ls -la dist/

# ── Tag + prep release (does NOT upload) ────────────────────
release: build
	@git add -A
	@git commit -m "v$(VERSION)" 2>/dev/null || echo "(nothing to commit)"
	@git tag -a "v$(VERSION)" -m "Release $(VERSION)" 2>/dev/null || echo "⚠️  Tag v$(VERSION) already exists"
	@echo ""
	@echo "════════════════════════════════════════════════════"
	@echo "  🚀 v$(VERSION) is ready to ship!"
	@echo ""
	@echo "  Upload to PyPI:"
	@echo "    twine upload dist/hyper_sentinel-$(VERSION)*"
	@echo ""
	@echo "  Push to GitHub:"
	@echo "    git push origin main --tags"
	@echo "════════════════════════════════════════════════════"

# ── Quick version bump helper ───────────────────────────────
# Usage: make bump V=0.4.0
bump:
ifndef V
	$(error Usage: make bump V=0.4.0)
endif
	@$(PYTHON) -c "\
import re;\
f='pyproject.toml'; t=open(f).read(); t=re.sub(r'version = \".*?\"', 'version = \"$(V)\"', t, 1); open(f,'w').write(t);\
f='src/sentinel/__init__.py'; t=open(f).read(); t=re.sub(r'__version__ = \".*?\"', '__version__ = \"$(V)\"', t); open(f,'w').write(t);\
print('✅ Version bumped to $(V) in pyproject.toml + __init__.py')"

# ── Clean build artifacts ───────────────────────────────────
clean:
	@rm -rf dist/ build/ *.egg-info src/*.egg-info
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"

# ── Dev setup ───────────────────────────────────────────────
dev-setup:
	@$(PYTHON) -m pip install -e ".[dev]" --quiet
	@echo "✅ Dev environment ready"
