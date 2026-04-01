"""
Telegram Scraper — Sync wrappers for the Telegram Client API.

Provides tool-friendly functions that the agent swarm can call to read
Telegram channels, search messages, list dialogs, and send messages.

Uses the TelegramUserClient from automation/telegram.py under the hood.
Requires TELEGRAM_API_ID + TELEGRAM_API_HASH in .env and a completed
phone login (session file persisted after first auth).
"""

import os
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("scrapers.telegram")

# Singleton client instance — reused across tool calls
_client_instance = None


def _get_client():
    """Get or create the singleton TelegramUserClient."""
    global _client_instance

    if _client_instance is not None and _client_instance.is_connected:
        return _client_instance

    api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()

    if not api_id or not api_hash:
        return None

    try:
        from automation.telegram import TelegramUserClient
        _client_instance = TelegramUserClient(
            api_id=int(api_id),
            api_hash=api_hash,
            session_name="sentinel_session",
        )
        return _client_instance
    except Exception as e:
        logger.error(f"Failed to create TG client: {e}")
        return None


def _run_async(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _ensure_connected(client):
    """Ensure the client is connected (uses existing session file)."""
    if not client.is_connected:
        # Connect without phone — uses persisted session
        if client.client is None:
            from automation.telegram import TelegramUserClient
            try:
                from telethon import TelegramClient as TelethonClient
            except ImportError:
                raise ImportError("telethon not installed — run: uv pip install telethon")
            client.client = TelethonClient(
                client.session_name, client.api_id, client.api_hash
            )
        await client.client.connect()
        if not await client.client.is_user_authorized():
            raise RuntimeError(
                "Telegram session expired or not set up. Run 'add tg client' to re-authenticate."
            )


# ── Public API (sync, tool-friendly) ─────────────────────────────


def tg_read_channel(channel: str, limit: int = 10) -> list[dict]:
    """
    Read recent messages from a Telegram channel, group, or DM.

    Args:
        channel: Username (@channel), invite link, or chat name
        limit: Number of messages to fetch (default 10, max 100)

    Returns:
        List of message dicts with sender, text, date
    """
    client = _get_client()
    if not client:
        return [{"error": "Telegram Client not configured. Run 'add tg client' to set up."}]

    limit = min(limit, 100)

    async def _read():
        await _ensure_connected(client)
        return await client.read_channel(channel, limit)

    try:
        return _run_async(_read())
    except Exception as e:
        return [{"error": str(e)}]


def tg_search_messages(channel: str, query: str, limit: int = 20) -> list[dict]:
    """
    Search for messages containing a query string in a channel.

    Args:
        channel: Channel username or name
        query: Search string
        limit: Max results (default 20)

    Returns:
        List of matching message dicts
    """
    client = _get_client()
    if not client:
        return [{"error": "Telegram Client not configured. Run 'add tg client' to set up."}]

    async def _search():
        await _ensure_connected(client)
        return await client.search_messages(channel, query, limit)

    try:
        return _run_async(_search())
    except Exception as e:
        return [{"error": str(e)}]


def tg_list_channels(limit: int = 30) -> list[dict]:
    """
    List your recent Telegram chats, channels, and groups.

    Returns:
        List of dialog dicts with name, type, unread count, username
    """
    client = _get_client()
    if not client:
        return [{"error": "Telegram Client not configured. Run 'add tg client' to set up."}]

    async def _list():
        await _ensure_connected(client)
        return await client.list_dialogs(limit)

    try:
        return _run_async(_list())
    except Exception as e:
        return [{"error": str(e)}]


def tg_send_message(target: str, message: str) -> dict:
    """
    Send a message to a Telegram user, group, channel, or bot.

    ⚠️ This sends as YOUR account — use responsibly.

    Args:
        target: Username (@user), phone, or chat name
        message: Text to send

    Returns:
        Sent message info dict
    """
    client = _get_client()
    if not client:
        return {"error": "Telegram Client not configured. Run 'add tg client' to set up."}

    async def _send():
        await _ensure_connected(client)
        return await client.send_message(target, message)

    try:
        return _run_async(_send())
    except Exception as e:
        return {"error": str(e)}


def tg_get_config() -> dict:
    """Get Telegram Client configuration status."""
    api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    session_exists = os.path.exists("sentinel_session.session")

    return {
        "configured": bool(api_id and api_hash),
        "session_exists": session_exists,
        "api_id": api_id[:4] + "..." if api_id else None,
    }
