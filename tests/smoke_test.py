#!/usr/bin/env python3
"""
Sentinel SDK Smoke Test — Run before every PyPI push.

Usage:
    cd ~/Antigravity/Python/sentinel-sdk
    python tests/smoke_test.py

If it says SHIP IT → push to PyPI.
If it says BLOCKED → fix the issue first.
"""

import sys
import inspect

passed = 0
failed = 0
errors = []


def check(name, fn):
    """Run a test, print result."""
    global passed, failed
    try:
        result = fn()
        if result is True or result is None:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}: {result}")
            errors.append(f"{name}: {result}")
            failed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        errors.append(f"{name}: {e}")
        failed += 1


print()
print("=" * 60)
print("  🛡️  SENTINEL SDK SMOKE TEST")
print("=" * 60)
print()

# ── 1. Version ────────────────────────────────────────────
print("  📦 Version")

def test_version():
    from sentinel import __version__
    print(f"     → {__version__}")
    if not __version__:
        return "No version found"
    return True

check("Version loads", test_version)

# ── 2. Core Imports ───────────────────────────────────────
print()
print("  📦 Imports")

def test_imports():
    from sentinel import Sentinel, SentinelAPI, SentinelAPIError, AuthenticationError
    from sentinel.api.client import SentinelAPI as API2
    from sentinel.api._http import load_api_key, load_ai_key, save_ai_key
    from sentinel.api.auth import authenticate_with_ai_key
    from sentinel.api.resources.chat import ChatResource
    from sentinel.api.resources.tools import ToolsResource
    return True

check("All core imports", test_imports)

def test_cli_imports():
    from sentinel.cli import cli, _add_service, _load_config, _save_config, detect_provider
    return True

check("CLI imports (add commands)", test_cli_imports)

# ── 3. Provider Detection ────────────────────────────────
print()
print("  🔑 Provider Detection")

def test_provider(prefix, expected):
    def _test():
        from sentinel.cli import detect_provider
        result = detect_provider(prefix)
        if result != expected:
            return f"Got '{result}', expected '{expected}'"
        return True
    return _test

check("sk-ant-xxx → anthropic", test_provider("sk-ant-test123", "anthropic"))
check("sk-xxx → openai", test_provider("sk-test123", "openai"))
check("AIzaxxx → google", test_provider("AIzatest123", "google"))
check("xai-xxx → xai", test_provider("xai-test123", "xai"))
check("garbage → unknown", test_provider("garbage", "unknown"))

# ── 4. Key Validation ────────────────────────────────────
print()
print("  🔐 Key Validation")

def test_key_validation():
    from sentinel.api._http import _is_valid_ai_key
    assert _is_valid_ai_key("sk-ant-api03-real-key-here") == True, "Should accept valid Anthropic key"
    assert _is_valid_ai_key("sk-proj-real-key-here") == True, "Should accept valid OpenAI key"
    assert _is_valid_ai_key("x" * 300) == False, "Should reject >200 char key"
    assert _is_valid_ai_key("") == False, "Should reject empty key"
    return True

try:
    check("_is_valid_ai_key exists and works", test_key_validation)
except ImportError:
    check("_is_valid_ai_key exists", lambda: "_is_valid_ai_key not found in _http.py")

# ── 5. Add Service Handlers ──────────────────────────────
print()
print("  ⚙️  Add Service Handlers")

def test_add_handlers():
    from sentinel.cli import ADD_HANDLERS
    expected = ["y2", "x", "fred", "elfa", "brave", "discord"]
    missing = [s for s in expected if s not in ADD_HANDLERS]
    if missing:
        return f"Missing handlers: {missing}"
    print(f"     → {len(ADD_HANDLERS)} services: {list(ADD_HANDLERS.keys())}")
    return True

check("ADD_HANDLERS registry", test_add_handlers)

def test_add_service_callable():
    from sentinel.cli import _add_service
    if not callable(_add_service):
        return "_add_service is not callable"
    return True

check("_add_service is callable", test_add_service_callable)

def test_step_functions():
    from sentinel.cli import _step_hyperliquid
    if not callable(_step_hyperliquid):
        return "_step_hyperliquid not callable"
    return True

check("_step_hyperliquid exists", test_step_functions)

# ── 6. ChatResource Signature ────────────────────────────
print()
print("  💬 Chat Architecture")

def test_chat_signature():
    from sentinel.api.resources.chat import ChatResource
    sig = inspect.signature(ChatResource.send)
    params = list(sig.parameters.keys())
    if "ai_key" in params:
        return "ChatResource.send() should NOT have ai_key parameter — it loads it internally"
    expected_params = ["self", "message", "stream", "model", "system"]
    for p in expected_params:
        if p not in params:
            return f"Missing parameter '{p}' in ChatResource.send()"
    return True

check("ChatResource.send() signature (no ai_key)", test_chat_signature)

def test_sentinel_chat_no_crash():
    from sentinel import Sentinel
    sig = inspect.signature(Sentinel.chat)
    params = list(sig.parameters.keys())
    if "message" not in params:
        return "Sentinel.chat() missing 'message' param"
    return True

check("Sentinel.chat() exists", test_sentinel_chat_no_crash)

def test_chat_loads_ai_key_internally():
    import ast
    with open("src/sentinel/api/resources/chat.py") as f:
        source = f.read()
    if "load_ai_key" not in source:
        return "ChatResource.send() doesn't call load_ai_key() — ai_key won't be sent to gateway"
    return True

check("ChatResource loads ai_key internally", test_chat_loads_ai_key_internally)

def test_chat_extracts_text():
    """Verify Sentinel.chat() extracts text from Anthropic response format, not returns empty."""
    from sentinel import Sentinel
    # Simulate Anthropic response
    class FakeChatResource:
        def send(self, message, stream=False):
            return {"content": [{"text": "Hello world", "type": "text"}], "role": "assistant"}
    s = Sentinel.__new__(Sentinel)
    s._chat_resource = FakeChatResource()
    result = s.chat("test")
    if result != "Hello world":
        return f"chat() returned '{result}' instead of 'Hello world' — response parsing broken"
    return True

check("chat() extracts text from Anthropic format", test_chat_extracts_text)

def test_chat_extracts_openai():
    """Verify Sentinel.chat() handles OpenAI format too."""
    from sentinel import Sentinel
    class FakeChatResource:
        def send(self, message, stream=False):
            return {"choices": [{"message": {"content": "Hi there"}}]}
    s = Sentinel.__new__(Sentinel)
    s._chat_resource = FakeChatResource()
    result = s.chat("test")
    if result != "Hi there":
        return f"chat() returned '{result}' instead of 'Hi there' — OpenAI format broken"
    return True

check("chat() extracts text from OpenAI format", test_chat_extracts_openai)

# ── 7. Chat Payload Format ──────────────────────────────
print()
print("  📡 Chat Payload (THE TEST THAT MATTERS)")

def test_chat_payload_format():
    """Verify ChatResource.send() builds the correct payload for the Go gateway."""
    with open("src/sentinel/api/resources/chat.py") as f:
        source = f.read()
    # Must use "messages" (plural, list format) not "message" (singular, string)
    if '"message"' in source and '"messages"' not in source:
        return 'Payload uses "message" (string) — gateway expects "messages" (list of objects). THIS WILL 400.'
    if '"messages"' not in source:
        return 'Payload missing "messages" key — gateway will reject with invalid_request_error'
    if '{"role": "user", "content": message}' not in source:
        return 'Payload not wrapping message in {"role": "user", "content": ...} — gateway expects OpenAI format'
    return True

check("Payload uses messages[] not message", test_chat_payload_format)

def test_chat_payload_has_ai_key():
    """Verify the payload includes ai_key for LLM routing."""
    with open("src/sentinel/api/resources/chat.py") as f:
        source = f.read()
    if '"ai_key"' not in source:
        return "Payload missing ai_key — gateway won't know which LLM to use"
    return True

check("Payload includes ai_key", test_chat_payload_has_ai_key)

# ── 8. Live Gateway Test ─────────────────────────────────
print()
print("  🌐 Live Gateway Test")

def test_gateway_chat():
    """Actually call the gateway and verify we get a response, not an error."""
    from sentinel.api._http import load_api_key, load_ai_key
    api_key = load_api_key()
    ai_key = load_ai_key()

    if not api_key:
        print("     → ⚠️  No API key — skipping live test (first-time user)")
        return True
    if not ai_key:
        print("     → ⚠️  No AI key — skipping live test")
        return True

    import httpx
    try:
        resp = httpx.post(
            "https://api.hyper-sentinel.com/api/v1/llm/chat",
            json={
                "messages": [{"role": "user", "content": "say hello in exactly 3 words"}],
                "ai_key": ai_key,
            },
            headers={"X-API-Key": api_key},
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Extract text — handle multiple response formats
            text = ""
            # Anthropic format: {"content": [{"text": "...", "type": "text"}]}
            content = data.get("content", "")
            if isinstance(content, list) and content:
                text = content[0].get("text", "")
            elif isinstance(content, str):
                text = content
            # Simple format: {"text": "..."}
            if not text:
                text = data.get("text", "")
            # OpenAI format: {"choices": [{"message": {"content": "..."}}]}
            if not text:
                choices = data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
            if text:
                preview = text[:60].replace("\n", " ")
                print(f"     → Gateway responded: \"{preview}\"")
                return True
            else:
                return f"Gateway returned 200 but no text in response: {str(data)[:200]}"
        elif resp.status_code == 400:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            return f"Gateway returned 400 — payload format wrong: {body}"
        elif resp.status_code == 401:
            return f"Gateway returned 401 — auth failed (bad API key?)"
        else:
            return f"Gateway returned {resp.status_code}: {resp.text[:200]}"
    except httpx.ConnectError:
        print("     → ⚠️  Gateway unreachable — skipping live test")
        return True
    except httpx.TimeoutException:
        print("     → ⚠️  Gateway timed out — skipping live test")
        return True

check("Chat actually works end-to-end", test_gateway_chat)

# ── 9. CLI Chat Call ──────────────────────────────────────
print()
print("  🖥️  CLI Chat Call")

def test_cli_chat_call():
    with open("src/sentinel/cli.py") as f:
        source = f.read()
    if "s.chat(user_input, ai_key=" in source:
        return "cli.py still passes ai_key= to s.chat() — THIS WILL CRASH"
    if "chat(user_input, ai_key" in source:
        return "cli.py still passes ai_key to chat() — THIS WILL CRASH"
    return True

check("cli.py does NOT pass ai_key to chat()", test_cli_chat_call)

# ── 10. Syntax Check ─────────────────────────────────────
print()
print("  📝 Syntax")

def test_syntax():
    import ast
    critical_files = [
        "src/sentinel/cli.py",
        "src/sentinel/__init__.py",
        "src/sentinel/api/client.py",
        "src/sentinel/api/_http.py",
        "src/sentinel/api/resources/chat.py",
        "src/sentinel/api/resources/tools.py",
        "src/sentinel/api/auth.py",
    ]
    for f in critical_files:
        try:
            with open(f) as fh:
                ast.parse(fh.read())
        except SyntaxError as e:
            return f"Syntax error in {f}: {e}"
    print(f"     → {len(critical_files)} files parsed clean")
    return True

check("All critical files parse", test_syntax)

# ── 11. No Self-Import ───────────────────────────────────
print()
print("  🔄 Import Hygiene")

def test_no_self_import():
    with open("src/sentinel/cli.py") as f:
        source = f.read()
    if "from sentinel.cli import _add_service" in source:
        return "cli.py has circular self-import of _add_service — use direct call"
    return True

check("No circular self-import in cli.py", test_no_self_import)

# ── 12. Algo Commands Deferred ───────────────────────────
print()
print("  🚫 Algo Commands (should be deferred)")

def test_no_strategy_calls():
    with open("src/sentinel/cli.py") as f:
        source = f.read()
    dangerous = ["strategy_set_algo", "strategy_start", "strategy_stop", "strategy_status"]
    found = [d for d in dangerous if d in source]
    if found:
        return f"cli.py still has gateway calls: {found} — these endpoints don't exist"
    return True

check("No strategy_* gateway calls in cli.py", test_no_strategy_calls)


# ── RESULTS ───────────────────────────────────────────────
print()
print("=" * 60)
total = passed + failed
if failed == 0:
    print(f"  ✅ {passed}/{total} PASSED — SHIP IT 🚀")
else:
    print(f"  ❌ {failed}/{total} FAILED — BLOCKED ⛔")
    print()
    for e in errors:
        print(f"     • {e}")
print("=" * 60)
print()

sys.exit(1 if failed else 0)
