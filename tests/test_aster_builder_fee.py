"""Unit tests — every Aster order carries the Sentinel broker fee.

Pure unit tests: the signed API call is mocked, so nothing hits the network and
no real trade is placed. Guards the revenue-capture path so a refactor can't
silently drop the broker fee. Mirrors tests/test_builder_fee.py (Hyperliquid).
"""

from unittest.mock import patch

from sentinel.scrapers import aster


def test_aster_broker_config_defaults():
    """Revenue config: address defaults to the dedicated Aster wallet, rate is 1 BPS."""
    assert aster.ASTER_BROKER_ADDRESS == aster._ASTER_BROKER_WALLET
    assert aster.ASTER_BROKER_ADDRESS.startswith("0x")
    assert aster.ASTER_BROKER_FEE_RATE == 10  # tenths of a BPS = 0.01%


@patch.object(aster, "_signed_request")
def test_aster_place_order_attaches_broker(mock_req):
    mock_req.return_value = {"orderId": 123, "status": "NEW"}
    aster.aster_place_order("BTC", "BUY", quantity=0.001)
    # _signed_request(method, endpoint, params) — params is the 3rd positional arg.
    call_params = mock_req.call_args[0][2]
    assert "broker" in call_params
    assert call_params["broker"] == aster.ASTER_BROKER_ADDRESS


@patch.object(aster, "_signed_request")
def test_aster_trailing_stop_attaches_broker(mock_req):
    mock_req.return_value = {"orderId": 456, "status": "NEW"}
    aster.aster_place_trailing_stop("ETH", side="SELL", quantity=1.0)
    call_params = mock_req.call_args[0][2]
    assert "broker" in call_params
    assert call_params["broker"] == aster.ASTER_BROKER_ADDRESS
