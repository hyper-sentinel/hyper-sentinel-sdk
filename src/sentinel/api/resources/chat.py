"""
Sentinel API — Chat Resource (LLM Proxy).

    response = client.chat("analyze BTC outlook")
    print(response["text"])
    print(response["usage"])

    # Streaming
    for chunk in client.chat("deep dive NVDA", stream=True):
        print(chunk["text"], end="", flush=True)
"""

from typing import Generator, Optional, Union


class ChatResource:
    """LLM chat endpoint — metered and billed per your tier."""

    def __init__(self, http):
        self._http = http

    def send(
        self,
        message: str,
        stream: bool = False,
        model: str = None,
        system: str = None,
    ) -> Union[dict, Generator[dict, None, None]]:
        """Send a message to the Sentinel AI agent.

        Every call is metered and billed at your tier's markup:
        - Free: 40% markup
        - Pro: 20% markup
        - Enterprise: 10% markup

        Args:
            message: Your message/question/command
            stream: If True, yields SSE chunks for real-time rendering
            model: Override the LLM model (optional)
            system: Override the system prompt (optional)

        Returns:
            dict with 'text', 'usage' (tokens, cost), and 'meta'
            If stream=True, yields dicts with 'text' and 'done' keys
        """
        payload = {"message": message}

        # Include AI provider key for LLM routing (REQUIRED)
        from sentinel.api._http import load_ai_key
        ai_key = load_ai_key()
        if not ai_key:
            raise Exception(
                "No AI provider key found. Run 'sentinel' to set up your LLM key.\n"
                "  Expected file: ~/.sentinel/ai_key"
            )
        payload["ai_key"] = ai_key

        if model:
            payload["model"] = model
        if system:
            payload["system"] = system

        if stream:
            return self._http.post_stream("/api/v1/llm/chat", payload)

        return self._http.post("/api/v1/llm/chat", payload)

    def usage(self) -> dict:
        """Get your LLM usage stats — total calls, tokens, cost."""
        return self._http.get("/api/v1/llm/usage")
