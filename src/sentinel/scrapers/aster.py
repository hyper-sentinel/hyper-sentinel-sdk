"""
Aster DEX Scraper — Futures Trading via Aster Finance API (V1 HMAC)

Direct REST integration for the Aster perpetual futures exchange.
Supports HMAC-SHA256 signed authenticated requests for trading.
Public market data (ticker, orderbook, klines, funding) requires no auth.

V1 API: HMAC-SHA256 signing (API Key + Secret)
V3 API: Web3 EIP-712 signing (API Wallet + Private Key) — see ASTER_API_GUIDE.md

API Base: https://fapi.asterdex.com
Docs: https://github.com/asterdex/api-docs
"""

import hashlib
import hmac
import logging
import math
import os
import threading
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("sentinel.aster")

ASTER_FAPI_BASE = "https://fapi.asterdex.com"

# ═══════════════════════════════════════════════════════════════
# ERROR CODE MAP — from Aster API docs
# ═══════════════════════════════════════════════════════════════
_ERROR_HINTS = {
    -1002: "Unauthorized — check API key is correct",
    -1003: "Rate limit exceeded — slow down requests",
    -1011: "IP not whitelisted — add your IP at asterdex.com API settings",
    -1021: "Timestamp drift — your clock is out of sync with Aster's server",
    -1022: "Invalid signature — check API secret, ensure key/secret pair match",
    -2010: "Order rejected — check quantity, price, and balance",
    -2013: "Order not found — orderId may be wrong",
    -2014: "Bad API key format — regenerate your API key",
    -2015: "Invalid API-key, IP, or permissions — enable 'Futures Trading' permission at asterdex.com API settings",
    -2018: "Insufficient balance — deposit more or reduce order size",
    -2019: "Insufficient margin — reduce leverage or order size",
    -2020: "Unable to fill — market may have low liquidity",
    -2021: "Order would immediately trigger — adjust stop/activation price",
    -2022: "ReduceOnly rejected — no open position to reduce",
    -2027: "Max leverage exceeded — reduce leverage or position size",
    -2028: "Min leverage — increase margin balance",
}

# Cache for exchange info (avoid repeated calls)
_exchange_info_cache: dict = {}
_exchange_info_ts: float = 0.0
_CACHE_TTL = 300  # 5 minutes


# ═══════════════════════════════════════════════════════════════
# CORE UTILITIES
# ═══════════════════════════════════════════════════════════════

def _norm_symbol(symbol: str) -> str:
    """Normalize symbol: BTC → BTCUSDT, BTC/USDT → BTCUSDT."""
    s = symbol.replace("/", "").replace("-", "").upper()
    if not s.endswith("USDT") and not s.endswith("BUSD"):
        s = s + "USDT"
    return s


def _get_session() -> tuple[requests.Session, str, str]:
    """Get an authenticated session with API key and secret."""
    api_key = os.getenv("ASTER_API_KEY", "").strip()
    api_secret = os.getenv("ASTER_API_SECRET", "").strip()
    session = requests.Session()
    session.headers.update({"X-MBX-APIKEY": api_key})
    return session, api_key, api_secret


def _sign(params: dict, api_secret: str) -> str:
    """HMAC-SHA256 signature for authenticated endpoints.
    
    Per Aster docs: signature = HMAC-SHA256(secretKey, urlencode(all_params))
    Signature must be the LAST parameter appended.
    """
    return hmac.new(
        api_secret.encode("utf-8"),
        urlencode(params).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _format_error(resp: requests.Response, endpoint: str) -> dict:
    """Parse an Aster API error response into a clean, actionable dict."""
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    
    code = body.get("code", resp.status_code)
    msg = body.get("msg", resp.reason)
    hint = _ERROR_HINTS.get(code, "")
    
    result = {
        "error": True,
        "code": code,
        "message": msg,
        "endpoint": endpoint,
    }
    if hint:
        result["hint"] = hint
    return result


def _public_request(endpoint: str, params: dict | None = None) -> Any:
    """Unauthenticated GET (market data)."""
    try:
        resp = requests.get(
            f"{ASTER_FAPI_BASE}{endpoint}",
            params=params or {},
            timeout=15,
        )
        if resp.status_code != 200:
            return _format_error(resp, endpoint)
        return resp.json()
    except requests.exceptions.Timeout:
        return {"error": True, "code": -1007, "message": "Request timed out", "endpoint": endpoint}
    except requests.exceptions.ConnectionError:
        return {"error": True, "code": -1001, "message": "Connection failed — check internet", "endpoint": endpoint}
    except Exception as e:
        return {"error": True, "message": str(e), "endpoint": endpoint}


# Global lock for serializing Aster API calls (prevents race conditions in multi-agent)
_aster_api_lock = threading.Lock()

# Track API weight usage
_api_weight_used = 0
_api_weight_reset_ts = 0


def _signed_request(method: str, endpoint: str, params: dict | None = None) -> Any:
    """Authenticated request with HMAC-SHA256 signature + retry + weight tracking."""
    session, api_key, api_secret = _get_session()
    if not api_key or not api_secret:
        return {
            "error": True,
            "code": -2014,
            "message": "Aster API not configured",
            "hint": "Use 'add aster' command or set ASTER_API_KEY and ASTER_API_SECRET in .env",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
        reraise=True,
    )
    def _do_request():
        global _api_weight_used, _api_weight_reset_ts
        # Fresh signature on each attempt (timestamp must be current)
        p = dict(params or {})
        p["recvWindow"] = p.get("recvWindow", 5000)
        p["timestamp"] = int(time.time() * 1000)
        p["signature"] = _sign(p, api_secret)

        url = f"{ASTER_FAPI_BASE}{endpoint}"
        if method == "GET":
            resp = session.get(url, params=p, timeout=15)
        elif method == "POST":
            resp = session.post(url, params=p, timeout=15)
        elif method == "DELETE":
            resp = session.delete(url, params=p, timeout=15)
        else:
            return {"error": True, "message": f"Unsupported HTTP method: {method}"}

        # Track API weight from response headers
        weight = resp.headers.get("X-MBX-USED-WEIGHT-1m", "0")
        try:
            _api_weight_used = int(weight)
        except ValueError:
            pass

        if resp.status_code == 429:
            logger.warning(f"Aster rate limit hit! Weight: {_api_weight_used}")
            raise requests.exceptions.ConnectionError("Rate limited (429)")

        if resp.status_code != 200:
            return _format_error(resp, endpoint)
        return resp.json()

    with _aster_api_lock:
        try:
            return _do_request()
        except requests.exceptions.Timeout:
            return {"error": True, "code": -1007, "message": "Request timed out after 3 retries", "endpoint": endpoint}
        except requests.exceptions.ConnectionError:
            return {"error": True, "code": -1001, "message": "Connection failed after 3 retries", "endpoint": endpoint}
        except Exception as e:
            return {"error": True, "message": str(e), "endpoint": endpoint}


# ═══════════════════════════════════════════════════════════════
# EXCHANGE INFO & QUANTITY HELPERS
# ═══════════════════════════════════════════════════════════════

def _get_symbol_info(symbol: str) -> dict | None:
    """Get exchange info for a symbol (cached 5min). Returns filter data."""
    global _exchange_info_cache, _exchange_info_ts
    
    now = time.time()
    if now - _exchange_info_ts > _CACHE_TTL or not _exchange_info_cache:
        data = _public_request("/fapi/v1/exchangeInfo")
        if isinstance(data, dict) and not data.get("error"):
            _exchange_info_cache = {}
            for s in data.get("symbols", []):
                _exchange_info_cache[s["symbol"]] = s
            _exchange_info_ts = now
    
    return _exchange_info_cache.get(symbol)


def _get_leverage(symbol: str) -> int:
    """Get current leverage for a symbol from account position info."""
    try:
        positions = _signed_request("GET", "/fapi/v1/positionRisk", {"symbol": symbol})
        if isinstance(positions, list):
            for p in positions:
                if p.get("symbol") == symbol:
                    return int(p.get("leverage", 1))
    except Exception:
        pass
    return 1


def _calc_quantity(symbol: str, usd_amount: float) -> float | None:
    """Convert USD margin amount to contract quantity using current price, leverage, and exchange rules.

    usd_amount is treated as MARGIN — multiplied by leverage to get notional.
    Handles stepSize/minQty/minNotional from exchange info.
    Returns None if the amount is too small.
    """
    norm = _norm_symbol(symbol)

    # Get current price
    try:
        ticker = _public_request("/fapi/v1/ticker/price", {"symbol": norm})
        if isinstance(ticker, dict) and ticker.get("error"):
            return None
        price = float(ticker.get("price", 0))
        if price <= 0:
            return None
    except Exception:
        return None

    # Get leverage to convert margin → notional
    leverage = _get_leverage(norm)
    notional = usd_amount * leverage
    logger.info(f"_calc_quantity: ${usd_amount} margin × {leverage}x = ${notional} notional / ${price} = {notional / price:.6f} {norm}")

    # Raw quantity from notional
    raw_qty = notional / price
    
    # Get exchange rules
    info = _get_symbol_info(norm)
    if not info:
        # Fallback: round to 3 decimals (most common)
        return round(raw_qty, 3)
    
    # Apply LOT_SIZE filter
    step_size = 0.001
    min_qty = 0.001
    for f in info.get("filters", []):
        if f["filterType"] == "LOT_SIZE":
            step_size = float(f["stepSize"])
            min_qty = float(f["minQty"])
        elif f["filterType"] == "MIN_NOTIONAL":
            min_notional = float(f.get("notional", 5))
            if usd_amount < min_notional:
                return None  # Below minimum
    
    # Round down to stepSize
    precision = int(round(-math.log10(step_size))) if step_size > 0 else 3
    qty = math.floor(raw_qty / step_size) * step_size
    qty = round(qty, precision)
    
    if qty < min_qty:
        return None

    return qty


def _is_usd_amount(quantity: float, symbol: str) -> bool:
    """Determine if a quantity value is likely a USD amount rather than contract size.

    Uses current price to decide. If quantity * price would be absurdly large,
    it's almost certainly a USD amount, not a contract size.
    """
    norm = _norm_symbol(symbol)
    try:
        ticker = _public_request("/fapi/v1/ticker/price", {"symbol": norm})
        if isinstance(ticker, dict) and ticker.get("error"):
            return False
        price = float(ticker.get("price", 0))
        if price <= 0:
            return False
    except Exception:
        return False

    notional = quantity * price

    # If the notional value of treating quantity as contracts would be absurdly large,
    # it's almost certainly a USD amount. Also: if quantity >= 5 and the asset
    # price > $100, likely USD (nobody passes 110 BTC as contract size).
    if price > 100 and quantity >= 5:
        return True
    if notional > 50_000:
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════

def aster_diagnose() -> dict:
    """Run comprehensive diagnostics on Aster DEX connection.
    
    Tests: connectivity, time sync, API key validity, GET auth, POST auth (TRADE).
    Returns a clear status report with actionable hints.
    """
    results: dict[str, Any] = {
        "exchange": "Aster DEX",
        "api_url": ASTER_FAPI_BASE,
    }
    
    api_key = os.getenv("ASTER_API_KEY", "").strip()
    api_secret = os.getenv("ASTER_API_SECRET", "").strip()
    results["api_key_set"] = bool(api_key)
    results["api_secret_set"] = bool(api_secret)
    if api_key:
        results["api_key_preview"] = f"{api_key[:8]}...{api_key[-4:]}"
    
    # 1. Connectivity
    try:
        r = requests.get(f"{ASTER_FAPI_BASE}/fapi/v1/ping", timeout=10)
        results["connectivity"] = "✅ OK" if r.status_code == 200 else f"❌ HTTP {r.status_code}"
    except Exception as e:
        results["connectivity"] = f"❌ {e}"
        return results
    
    # 2. Time sync
    try:
        r = requests.get(f"{ASTER_FAPI_BASE}/fapi/v1/time", timeout=10)
        server_time = r.json().get("serverTime", 0)
        local_time = int(time.time() * 1000)
        drift = local_time - server_time
        results["time_drift_ms"] = drift
        results["time_sync"] = "✅ OK" if abs(drift) < 2000 else f"⚠️ {drift}ms drift (may cause -1021 errors)"
    except Exception:
        results["time_sync"] = "❌ Could not check"
    
    if not api_key or not api_secret:
        results["auth"] = "❌ API key/secret not configured"
        results["hint"] = "Set ASTER_API_KEY and ASTER_API_SECRET in .env"
        return results
    
    # 3. GET auth (USER_DATA — balance)
    balance_result = _signed_request("GET", "/fapi/v2/balance")
    if isinstance(balance_result, list):
        results["get_auth"] = "✅ Read access working"
        nonzero = [b for b in balance_result if float(b.get("balance", 0)) > 0 or float(b.get("availableBalance", 0)) > 0]
        results["assets_with_balance"] = len(nonzero)
    elif isinstance(balance_result, dict) and balance_result.get("error"):
        results["get_auth"] = f"❌ {balance_result.get('message', 'Failed')}"
        if balance_result.get("hint"):
            results["get_auth_hint"] = balance_result["hint"]
    
    # 4. POST auth (TRADE — leverage) — non-destructive test
    leverage_result = _signed_request("POST", "/fapi/v1/leverage", {
        "symbol": "BTCUSDT", "leverage": 20
    })
    if isinstance(leverage_result, dict):
        if leverage_result.get("error"):
            code = leverage_result.get("code")
            if code == -2015:
                results["post_auth"] = "❌ API key lacks TRADE permissions"
                results["post_auth_hint"] = "Enable 'Futures Trading' at asterdex.com → API Management"
            else:
                results["post_auth"] = f"❌ {leverage_result.get('message', 'Failed')}"
                if leverage_result.get("hint"):
                    results["post_auth_hint"] = leverage_result["hint"]
        elif "leverage" in leverage_result:
            results["post_auth"] = "✅ Trading access working"
            results["current_btc_leverage"] = leverage_result.get("leverage")
    
    # 5. Summary
    get_ok = "✅" in results.get("get_auth", "")
    post_ok = "✅" in results.get("post_auth", "")
    if get_ok and post_ok:
        results["overall"] = "✅ Fully operational — read + trade access confirmed"
    elif get_ok and not post_ok:
        results["overall"] = "⚠️ Read-only — API key lacks trading permissions"
    else:
        results["overall"] = "❌ Not working — check API credentials"
    
    return results


# ═══════════════════════════════════════════════════════════════
# PUBLIC MARKET DATA (no auth required)
# ═══════════════════════════════════════════════════════════════

def aster_ping() -> dict:
    """Check Aster API connectivity."""
    try:
        _public_request("/fapi/v1/ping")
        return {"status": "ok", "exchange": "Aster DEX", "url": ASTER_FAPI_BASE}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def aster_ticker(symbol: str) -> dict:
    """24h ticker stats: price, volume, high/low, price change."""
    s = _norm_symbol(symbol)
    data = _public_request("/fapi/v1/ticker/24hr", {"symbol": s})
    if isinstance(data, dict) and data.get("error"):
        return data
    return {
        "symbol": data.get("symbol"),
        "last_price": float(data.get("lastPrice", 0)),
        "price_change_pct": float(data.get("priceChangePercent", 0)),
        "high_24h": float(data.get("highPrice", 0)),
        "low_24h": float(data.get("lowPrice", 0)),
        "volume_24h": float(data.get("volume", 0)),
        "quote_volume_24h": float(data.get("quoteVolume", 0)),
        "weighted_avg_price": float(data.get("weightedAvgPrice", 0)),
    }


def aster_orderbook(symbol: str, limit: int = 10) -> dict:
    """Live orderbook with bids and asks."""
    s = _norm_symbol(symbol)
    data = _public_request("/fapi/v1/depth", {"symbol": s, "limit": limit})
    if isinstance(data, dict) and data.get("error"):
        return data
    bids = [{"price": float(b[0]), "qty": float(b[1])} for b in data.get("bids", [])[:limit]]
    asks = [{"price": float(a[0]), "qty": float(a[1])} for a in data.get("asks", [])[:limit]]
    best_bid = bids[0]["price"] if bids else 0
    best_ask = asks[0]["price"] if asks else 0
    spread = best_ask - best_bid if best_bid and best_ask else 0
    return {
        "symbol": s,
        "bids": bids,
        "asks": asks,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "mid_price": (best_bid + best_ask) / 2 if best_bid and best_ask else 0,
    }


def aster_klines(symbol: str, interval: str = "1h", limit: int = 24) -> list[dict]:
    """Candlestick/kline data."""
    s = _norm_symbol(symbol)
    data = _public_request("/fapi/v1/klines", {
        "symbol": s, "interval": interval, "limit": limit,
    })
    if isinstance(data, dict) and data.get("error"):
        return data
    return [
        {
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
        }
        for k in data
    ]


def aster_funding_rate(symbol: Optional[str] = None) -> Any:
    """Current funding rate and mark price."""
    params: dict[str, Any] = {}
    if symbol:
        params["symbol"] = _norm_symbol(symbol)
    data = _public_request("/fapi/v1/premiumIndex", params)
    if isinstance(data, dict) and data.get("error"):
        return data
    if isinstance(data, list):
        return [
            {
                "symbol": d.get("symbol"),
                "mark_price": float(d.get("markPrice", 0)),
                "funding_rate": float(d.get("lastFundingRate", 0)),
                "next_funding_time": d.get("nextFundingTime"),
            }
            for d in data[:20]
        ]
    return {
        "symbol": data.get("symbol"),
        "mark_price": float(data.get("markPrice", 0)),
        "funding_rate": float(data.get("lastFundingRate", 0)),
        "next_funding_time": data.get("nextFundingTime"),
    }


def aster_exchange_info(symbol: Optional[str] = None) -> dict:
    """Exchange info: trading pairs, contract specs, tick sizes."""
    params: dict[str, Any] = {}
    if symbol:
        params["symbol"] = _norm_symbol(symbol)
    data = _public_request("/fapi/v1/exchangeInfo", params)
    if isinstance(data, dict) and data.get("error"):
        return data
    symbols = data.get("symbols", [])
    return {
        "total_pairs": len(symbols),
        "pairs": [
            {
                "symbol": s.get("symbol"),
                "status": s.get("status"),
                "base_asset": s.get("baseAsset"),
                "quote_asset": s.get("quoteAsset"),
                "contract_type": s.get("contractType", "PERPETUAL"),
            }
            for s in symbols[:50]
        ],
    }


# ═══════════════════════════════════════════════════════════════
# ACCOUNT & POSITIONS (auth required)
# ═══════════════════════════════════════════════════════════════

def aster_config() -> dict:
    """Show Aster DEX configuration: API key status, connection."""
    api_key = os.getenv("ASTER_API_KEY", "").strip()
    api_secret = os.getenv("ASTER_API_SECRET", "").strip()
    configured = bool(api_key and api_secret)
    result: dict[str, Any] = {
        "exchange": "Aster DEX",
        "api_url": ASTER_FAPI_BASE,
        "configured": configured,
        "api_key": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else ("set" if api_key else "not set"),
    }
    if configured:
        try:
            _public_request("/fapi/v1/ping")
            result["connectivity"] = "ok"
        except Exception:
            result["connectivity"] = "failed"
    return result


def aster_balance() -> Any:
    """Account balance on Aster futures."""
    return _signed_request("GET", "/fapi/v2/balance")


def aster_positions(symbol: Optional[str] = None) -> Any:
    """Open positions with PnL, leverage, liquidation price."""
    params: dict[str, Any] = {}
    if symbol:
        params["symbol"] = _norm_symbol(symbol)
    data = _signed_request("GET", "/fapi/v2/positionRisk", params)
    if isinstance(data, dict) and data.get("error"):
        return data
    if isinstance(data, list):
        active = [
            {
                "symbol": p.get("symbol"),
                "side": "LONG" if float(p.get("positionAmt", 0)) > 0 else "SHORT",
                "size": abs(float(p.get("positionAmt", 0))),
                "entry_price": float(p.get("entryPrice", 0)),
                "mark_price": float(p.get("markPrice", 0)),
                "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                "leverage": int(p.get("leverage", 1)),
                "liquidation_price": float(p.get("liquidationPrice", 0)),
                "margin_type": p.get("marginType", "cross"),
            }
            for p in data
            if abs(float(p.get("positionAmt", 0))) > 0
        ]
        return active if active else {"message": "No open positions on Aster."}
    return data


def aster_account_info() -> Any:
    """Full account info: assets, positions, margins."""
    return _signed_request("GET", "/fapi/v2/account")


# ═══════════════════════════════════════════════════════════════
# TRADING (auth required)
# ═══════════════════════════════════════════════════════════════

def aster_place_order(
    symbol: str,
    side: str,
    order_type: str = "MARKET",
    quantity: float = 0,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
    usd_amount: Optional[float] = None,
) -> Any:
    """Place an order on Aster futures.

    Two ways to specify size:
    - usd_amount: Dollar amount to trade (e.g., 110 = $110 worth). Auto-converts to contracts.
    - quantity: Raw contract quantity (e.g., 0.001 BTC). Used as-is.

    If only quantity is given and it looks like a USD amount (e.g., 110 for BTC),
    it will be auto-converted using current price.
    """
    # ── Guardrail check (if sentinel guardrails are available) ──
    trade_usd = usd_amount if usd_amount is not None else quantity
    try:
        from core.sentinel import _active_guardrails
        if _active_guardrails:
            can_exec, reason = _active_guardrails.can_execute(trade_usd=trade_usd)
            if not can_exec:
                return {
                    "error": True,
                    "code": -9999,
                    "message": f"Guardrail blocked: {reason}",
                    "hint": "Trade rejected by sentinel guardrails",
                }
    except ImportError:
        pass  # Not running in sentinel mode — no guardrails

    s = _norm_symbol(symbol)

    # Determine actual contract quantity
    if usd_amount is not None and usd_amount > 0:
        # Explicit USD amount — always convert
        calc = _calc_quantity(s, usd_amount)
        if calc is None:
            return {
                "error": True,
                "message": f"Amount ${usd_amount} is below minimum notional for {s}",
                "hint": "Minimum order is typically $5 on most pairs",
            }
        actual_qty = calc
    elif quantity > 0 and _is_usd_amount(quantity, s):
        # quantity looks like USD (e.g., 110 for BTC at $69k = $7.6M notional)
        calc = _calc_quantity(s, quantity)
        if calc is None:
            return {
                "error": True,
                "message": f"Amount ${quantity} is below minimum notional for {s}",
                "hint": "Minimum order is typically $5 on most pairs",
            }
        actual_qty = calc
        logger.info(f"Auto-converted ${quantity} USD -> {actual_qty} {s} contracts")
    else:
        actual_qty = quantity

    if actual_qty <= 0:
        return {
            "error": True,
            "message": "Quantity must be positive",
            "hint": "Specify quantity (contract size) or usd_amount (dollar value)",
        }

    params: dict[str, Any] = {
        "symbol": s,
        "side": side.upper(),
        "type": order_type.upper(),
        "quantity": str(actual_qty),
    }
    if reduce_only:
        params["reduceOnly"] = "true"
    if order_type.upper() != "MARKET":
        params["timeInForce"] = time_in_force
    if price is not None:
        params["price"] = str(price)
    if stop_price is not None:
        params["stopPrice"] = str(stop_price)

    return _signed_request("POST", "/fapi/v1/order", params)


def aster_cancel_order(symbol: str, order_id: Optional[int] = None) -> Any:
    """Cancel an order on Aster."""
    params: dict[str, Any] = {"symbol": _norm_symbol(symbol)}
    if order_id is not None:
        params["orderId"] = order_id
    return _signed_request("DELETE", "/fapi/v1/order", params)


def aster_cancel_all_orders(symbol: str) -> Any:
    """Cancel all open orders for a symbol."""
    return _signed_request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": _norm_symbol(symbol)})


def aster_open_orders(symbol: Optional[str] = None) -> Any:
    """Get all open orders."""
    params: dict[str, Any] = {}
    if symbol:
        params["symbol"] = _norm_symbol(symbol)
    return _signed_request("GET", "/fapi/v1/openOrders", params)


def aster_order_history(symbol: str, limit: int = 20) -> Any:
    """Recent order history for a symbol."""
    return _signed_request("GET", "/fapi/v1/allOrders", {
        "symbol": _norm_symbol(symbol), "limit": limit,
    })


def aster_trade_history(symbol: str, limit: int = 20) -> Any:
    """Recent trade fills for a symbol."""
    return _signed_request("GET", "/fapi/v1/userTrades", {
        "symbol": _norm_symbol(symbol), "limit": limit,
    })


# ═══════════════════════════════════════════════════════════════
# LEVERAGE & MARGIN
# ═══════════════════════════════════════════════════════════════

def aster_set_leverage(symbol: str, leverage: int) -> Any:
    """Set leverage for a symbol (1-125x)."""
    leverage = max(1, min(125, leverage))
    return _signed_request("POST", "/fapi/v1/leverage", {
        "symbol": _norm_symbol(symbol), "leverage": leverage,
    })


def aster_set_margin_mode(symbol: str, margin_type: str = "CROSSED") -> Any:
    """Set margin mode: ISOLATED or CROSSED."""
    return _signed_request("POST", "/fapi/v1/marginType", {
        "symbol": _norm_symbol(symbol), "marginType": margin_type.upper(),
    })


# ═══════════════════════════════════════════════════════════════
# ORDER CONFIRMATION POLLING (Task 3)
# ═══════════════════════════════════════════════════════════════

def aster_place_order_confirmed(
    symbol: str,
    side: str,
    order_type: str = "MARKET",
    quantity: float = 0,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
    timeout_seconds: int = 30,
    poll_interval: float = 1.0,
) -> dict:
    """Place order and poll until confirmed filled, partially filled, or timeout.

    Returns dict with 'status' key: 'FILLED', 'PARTIALLY_FILLED', 'NEW', 'TIMEOUT', 'ERROR'
    """
    result = aster_place_order(
        symbol=symbol, side=side, order_type=order_type,
        quantity=quantity, price=price, stop_price=stop_price,
        time_in_force=time_in_force, reduce_only=reduce_only,
    )

    if isinstance(result, dict) and result.get("error"):
        return {**result, "status": "ERROR"}

    order_id = result.get("orderId")
    if not order_id:
        return {**result, "status": "UNKNOWN", "warning": "No orderId in response"}

    # For market orders, usually filled instantly — but verify
    if order_type.upper() == "MARKET":
        status = result.get("status", "")
        if status == "FILLED":
            return {**result, "status": "FILLED"}

    # Poll for order status
    s = _norm_symbol(symbol)
    elapsed = 0.0
    while elapsed < timeout_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval

        order_status = _signed_request("GET", "/fapi/v1/order", {
            "symbol": s,
            "orderId": order_id,
        })

        if isinstance(order_status, dict) and not order_status.get("error"):
            status = order_status.get("status", "")
            if status in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                return {**order_status, "status": status, "poll_time_s": elapsed}
            elif status == "PARTIALLY_FILLED":
                return {**order_status, "status": "PARTIALLY_FILLED", "poll_time_s": elapsed}

    return {
        **result,
        "status": "TIMEOUT",
        "warning": f"Order {order_id} not confirmed after {timeout_seconds}s",
        "poll_time_s": elapsed,
    }


# ═══════════════════════════════════════════════════════════════
# COUNTDOWN CANCEL — DEAD MAN'S SWITCH (Task 10)
# ═══════════════════════════════════════════════════════════════

def aster_countdown_cancel(symbol: str, countdown_ms: int = 30000) -> Any:
    """Set a countdown timer to auto-cancel all orders if not refreshed.

    Acts as a dead man's switch — call this periodically (e.g., every 20s for a 30s timer).
    Set countdown_ms=0 to disable.

    Args:
        symbol: Trading pair (e.g., 'BTC')
        countdown_ms: Milliseconds until auto-cancel. 0 to disable.
    """
    return _signed_request("POST", "/fapi/v1/countdownCancelAll", {
        "symbol": _norm_symbol(symbol),
        "countdownTime": countdown_ms,
    })


# ═══════════════════════════════════════════════════════════════
# TRAILING STOP (Task 11)
# ═══════════════════════════════════════════════════════════════

def aster_place_trailing_stop(
    symbol: str,
    side: str = "SELL",
    quantity: float = 0,
    callback_rate: float = 1.0,
    activation_price: Optional[float] = None,
    usd_amount: Optional[float] = None,
) -> Any:
    """Place a trailing stop market order on Aster futures.

    Args:
        symbol: Trading pair (e.g., 'BTC')
        side: SELL for long positions, BUY for short positions
        quantity: Contract size (or auto-detected USD amount)
        callback_rate: Trail distance as percentage (e.g., 1.0 = 1% trail)
        activation_price: Optional price at which trailing starts
        usd_amount: Explicit USD amount for auto-conversion
    """
    s = _norm_symbol(symbol)

    if usd_amount is not None and usd_amount > 0:
        calc = _calc_quantity(s, usd_amount)
        if calc is None:
            return {"error": True, "message": f"Amount ${usd_amount} below minimum for {s}"}
        actual_qty = calc
    elif quantity > 0 and _is_usd_amount(quantity, s):
        calc = _calc_quantity(s, quantity)
        if calc is None:
            return {"error": True, "message": f"Amount ${quantity} below minimum for {s}"}
        actual_qty = calc
    else:
        actual_qty = quantity

    params: dict[str, Any] = {
        "symbol": s,
        "side": side.upper(),
        "type": "TRAILING_STOP_MARKET",
        "quantity": str(actual_qty),
        "callbackRate": str(callback_rate),
        "reduceOnly": "true",
    }
    if activation_price is not None:
        params["activationPrice"] = str(activation_price)

    return _signed_request("POST", "/fapi/v1/order", params)

