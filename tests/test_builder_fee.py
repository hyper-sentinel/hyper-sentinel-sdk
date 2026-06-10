"""Unit tests — every Hyperliquid order carries the Sentinel builder fee.

Pure unit tests: the Exchange + approval call are mocked, so nothing hits the
network and no real trade is placed. Guards the revenue-capture path so a
refactor can't silently drop the builder fee.
"""

from unittest.mock import MagicMock, patch

from sentinel.scrapers import hyperliquid as hl

# A minimal "ok" response shaped like the Hyperliquid SDK returns.
_OK = {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 1}}]}}}


def _mock_exchange():
    ex = MagicMock()
    ex.market_open.return_value = _OK
    ex.order.return_value = _OK
    return ex


def test_builder_fee_config_defaults():
    """Revenue config: address defaults to the Sentinel wallet, rate is 1 BPS."""
    assert hl.BUILDER_FEE_ADDRESS == hl._SENTINEL_LABS_WALLET
    assert hl.BUILDER_FEE_ADDRESS.startswith("0x")
    assert hl.BUILDER_FEE_RATE == 10  # tenths of a BPS = 0.01%


@patch.object(hl, "_ensure_builder_fee_approved", lambda: None)
def test_market_order_attaches_builder():
    ex = _mock_exchange()
    with patch.object(hl, "_get_exchange", return_value=(ex, MagicMock(), "0xwallet")):
        hl.place_hl_order("BTC", "buy", 0.1, order_type="market")
    builder = ex.market_open.call_args.kwargs["builder"]
    assert builder == {"b": hl.BUILDER_FEE_ADDRESS, "f": hl.BUILDER_FEE_RATE}


@patch.object(hl, "_ensure_builder_fee_approved", lambda: None)
def test_limit_order_attaches_builder():
    ex = _mock_exchange()
    with patch.object(hl, "_get_exchange", return_value=(ex, MagicMock(), "0xwallet")):
        hl.place_hl_order("ETH", "sell", 1.0, price=4000.0, order_type="limit")
    builder = ex.order.call_args.kwargs["builder"]
    assert builder == {"b": hl.BUILDER_FEE_ADDRESS, "f": hl.BUILDER_FEE_RATE}
