"""
Tool Registry — Auto-schema generation from typed Python functions.

Ported from the hyper-sentinel Python engine. Functions with type hints
and docstrings auto-generate JSON schemas for both LLM tool-use and
REST API endpoint documentation.

Usage:
    registry = ToolRegistry()
    registry.register(get_crypto_price, get_stock_quote, ...)
    
    # LLM formats
    anthropic_tools = registry.for_anthropic()
    openai_tools = registry.for_openai()
    
    # Execute by name
    result = registry.execute("get_crypto_price", {"coin_id": "bitcoin"})
"""

import inspect
import json
import traceback
from typing import Any, Callable, get_type_hints


# ── Type → JSON Schema mapping ──────────────────────────────

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json(annotation) -> str:
    """Convert a Python type annotation to a JSON Schema type string."""
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_json(non_none[0])
        return "string"
    return _TYPE_MAP.get(annotation, "string")


def _build_schema(func: Callable) -> dict:
    """Build a JSON Schema 'parameters' object from function signature + type hints."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        prop: dict[str, Any] = {}

        if param_name in hints:
            ann = hints[param_name]
            prop["type"] = _python_type_to_json(ann)
        else:
            prop["type"] = "string"

        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            origin = getattr(hints.get(param_name), "__origin__", None)
            is_optional = False
            if origin is not None:
                args = getattr(hints.get(param_name), "__args__", ())
                is_optional = type(None) in args
            if not is_optional:
                required.append(param_name)

        properties[param_name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _extract_description(func: Callable) -> str:
    """Extract the first line of a function's docstring as its description."""
    doc = inspect.getdoc(func) or ""
    return doc.split("\n")[0].strip() if doc else f"Tool: {func.__name__}"


class ToolRegistry:
    """Registry of tools with auto-generated schemas and dispatch."""

    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, *funcs: Callable, **named: Callable) -> "ToolRegistry":
        """Register functions as tools."""
        for func in funcs:
            name = func.__name__
            self._tools[name] = {
                "func": func,
                "schema": _build_schema(func),
                "description": _extract_description(func),
            }
        for alias, func in named.items():
            self._tools[alias] = {
                "func": func,
                "schema": _build_schema(func),
                "description": _extract_description(func),
            }
        return self

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    def specs(self) -> list[dict]:
        """Return tool specs in neutral format."""
        return [
            {"name": name, "description": t["description"], "parameters": t["schema"]}
            for name, t in self._tools.items()
        ]

    def for_anthropic(self) -> list[dict]:
        """Anthropic format: name + description + input_schema."""
        return [
            {"name": name, "description": t["description"], "input_schema": t["schema"]}
            for name, t in self._tools.items()
        ]

    def for_openai(self) -> list[dict]:
        """OpenAI/Gemini/Grok format."""
        return [
            {
                "type": "function",
                "function": {"name": name, "description": t["description"], "parameters": t["schema"]},
            }
            for name, t in self._tools.items()
        ]

    def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name, return JSON string result."""
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            func = tool["func"]
            sig = inspect.signature(func)
            valid_params = set(sig.parameters.keys())
            filtered = {k: v for k, v in args.items() if k in valid_params}
            result = func(**filtered)
            return json.dumps(result, indent=2, default=str)
        except TypeError as e:
            expected = list(inspect.signature(tool["func"]).parameters.keys())
            return json.dumps({"status": "error", "error": str(e), "hint": f"Expected: {expected}", "tool": name})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e), "tool": name})
