"""
Discord Scraper — Sync wrappers for the Discord bot.

Provides tool-friendly functions that the agent swarm can call to read
Discord channels, search messages, list servers, and send messages.

Uses the DiscordClient from automation/discord_client.py under the hood.
Requires DISCORD_BOT_TOKEN in .env.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("scrapers.discord")

# Singleton client instance — runs in background thread
_client_instance = None
_started = False


def _get_client():
    """Get or create the singleton DiscordClient, starting it in background."""
    global _client_instance, _started

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        return None

    if _client_instance is not None and _client_instance.is_connected:
        return _client_instance

    if _started:
        # Already tried to start but not connected yet
        return _client_instance

    try:
        from automation.discord_client import DiscordClient
        _client_instance = DiscordClient(token=token)
        _client_instance.start_background()
        _started = True
        return _client_instance
    except Exception as e:
        logger.error(f"Failed to create Discord client: {e}")
        return None


# ── Public API (sync, tool-friendly) ─────────────────────────────


def discord_read_channel(channel_id: int, limit: int = 50) -> list[dict]:
    """
    Read recent messages from a Discord channel.

    Args:
        channel_id: The Discord channel ID (right-click -> Copy ID)
        limit: Number of messages (default 50, max 100)

    Returns:
        List of message dicts with author, content, timestamp
    """
    client = _get_client()
    if not client:
        return [{"error": "Discord bot not configured. Run 'add discord' to set up."}]

    if not client.is_connected:
        return [{"error": "Discord bot is connecting... try again in a few seconds."}]

    try:
        return client.read_channel_sync(channel_id, limit)
    except Exception as e:
        return [{"error": str(e)}]


def discord_search_messages(channel_id: int, query: str, limit: int = 20) -> list[dict]:
    """
    Search for messages containing a query in a Discord channel.

    Args:
        channel_id: Channel ID to search
        query: Search text
        limit: Max results (default 20)

    Returns:
        List of matching messages
    """
    client = _get_client()
    if not client:
        return [{"error": "Discord bot not configured. Run 'add discord' to set up."}]

    if not client.is_connected:
        return [{"error": "Discord bot is connecting... try again in a few seconds."}]

    try:
        return client.run_async(client.search_messages(channel_id, query, limit))
    except Exception as e:
        return [{"error": str(e)}]


def discord_list_guilds() -> list[dict]:
    """
    List all Discord servers the bot is in.

    Returns:
        List of guild dicts with name, member count, channel count
    """
    client = _get_client()
    if not client:
        return [{"error": "Discord bot not configured. Run 'add discord' to set up."}]

    if not client.is_connected:
        return [{"error": "Discord bot is connecting... try again in a few seconds."}]

    try:
        return client.list_guilds_sync()
    except Exception as e:
        return [{"error": str(e)}]


def discord_list_channels(guild_id: int = None) -> list[dict]:
    """
    List text channels in a Discord server.

    Args:
        guild_id: Server ID (optional — lists all servers if omitted)

    Returns:
        List of channel dicts with name, category, topic
    """
    client = _get_client()
    if not client:
        return [{"error": "Discord bot not configured. Run 'add discord' to set up."}]

    if not client.is_connected:
        return [{"error": "Discord bot is connecting... try again in a few seconds."}]

    try:
        return client.list_channels_sync(guild_id)
    except Exception as e:
        return [{"error": str(e)}]


def discord_send_message(channel_id: int, content: str) -> dict:
    """
    Send a message to a Discord channel via the bot.

    ⚠️ Sends as the Sentinel bot account.

    Args:
        channel_id: Target channel ID
        content: Message text

    Returns:
        Sent message info
    """
    client = _get_client()
    if not client:
        return {"error": "Discord bot not configured. Run 'add discord' to set up."}

    if not client.is_connected:
        return {"error": "Discord bot is connecting... try again in a few seconds."}

    try:
        return client.send_message_sync(channel_id, content)
    except Exception as e:
        return {"error": str(e)}


def discord_get_config() -> dict:
    """Get Discord bot configuration status."""
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    client = _client_instance

    return {
        "configured": bool(token),
        "connected": client.is_connected if client else False,
        "guilds": len(client.bot.guilds) if client and client.is_connected else 0,
        "bot_name": str(client.bot.user) if client and client.is_connected else None,
    }
