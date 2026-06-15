"""
Yahoo Finance scraper — wrapper functions for server.py ToolRegistry.

Extracted from chat.py inline dispatch code. Uses yfinance library.
"""

from typing import Optional


def get_stock_price(ticker: str = "SPY") -> dict:
    """Get current stock price, volume, day range for a ticker symbol."""
    import yfinance as yf
    t = yf.Ticker(ticker.upper())
    info = t.info
    return {
        "ticker": ticker.upper(),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "previous_close": info.get("previousClose"),
        "day_high": info.get("dayHigh"),
        "day_low": info.get("dayLow"),
        "volume": info.get("volume"),
        "market_cap": info.get("marketCap"),
        "name": info.get("shortName"),
        "source": "yfinance",
    }


def get_stock_info(ticker: str = "SPY") -> dict:
    """Get detailed stock info — sector, P/E, market cap, margins, analysts."""
    import yfinance as yf
    t = yf.Ticker(ticker.upper())
    info = t.info
    return {
        "ticker": ticker.upper(),
        "name": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "eps_trailing": info.get("trailingEps"),
        "dividend_yield": info.get("dividendYield"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "beta": info.get("beta"),
        "profit_margin": info.get("profitMargins"),
        "recommendation_key": info.get("recommendationKey"),
        "source": "yfinance",
    }


def get_stock_news(ticker: str = "SPY") -> dict:
    """Get latest news articles for a stock ticker."""
    import yfinance as yf
    t = yf.Ticker(ticker.upper())
    news = t.news or []
    items = []
    for n in news[:5]:
        c = n.get("content", n)
        provider = c.get("provider", {}) if isinstance(c, dict) else {}
        canonical = c.get("canonicalUrl", {}) if isinstance(c, dict) else {}
        items.append({
            "title": c.get("title") if isinstance(c, dict) else n.get("title"),
            "summary": (c.get("summary", "") if isinstance(c, dict) else "")[:200],
            "publisher": provider.get("displayName") if isinstance(provider, dict) else n.get("publisher"),
            "link": canonical.get("url") if isinstance(canonical, dict) else n.get("link"),
            "published": c.get("pubDate") if isinstance(c, dict) else n.get("providerPublishTime"),
        })
    return {"ticker": ticker.upper(), "news": items, "source": "yfinance"}


def get_stock_history(ticker: str = "SPY", period: str = "1mo") -> dict:
    """Get historical stock price data with computed returns, volatility, Sharpe."""
    import yfinance as yf
    t = yf.Ticker(ticker.upper())
    hist = t.history(period=period)
    if hist.empty:
        return {"error": f"No history for {ticker}"}
    closes = hist["Close"].tolist()
    returns = [(closes[i] - closes[i-1])/closes[i-1] for i in range(1, len(closes))]
    avg_return = sum(returns)/len(returns) if returns else 0
    volatility = (sum((r - avg_return)**2 for r in returns) / len(returns))**0.5 if returns else 0
    sharpe = (avg_return / volatility * (252**0.5)) if volatility > 0 else 0
    return {
        "ticker": ticker.upper(),
        "period": period,
        "current_price": float(closes[-1]),
        "period_return_pct": round((closes[-1]/closes[0] - 1) * 100, 2),
        "daily_avg_return_pct": round(avg_return * 100, 4),
        "daily_volatility_pct": round(volatility * 100, 4),
        "annualized_sharpe": round(sharpe, 2),
        "high": round(max(closes), 2),
        "low": round(min(closes), 2),
        "data_points": len(closes),
        "source": "yfinance",
    }


def get_analyst_recs(ticker: str = "SPY") -> dict:
    """Get analyst recommendations for a stock."""
    import yfinance as yf
    t = yf.Ticker(ticker.upper())
    recs = t.recommendations
    if recs is not None and len(recs) > 0:
        recent = recs.tail(5).to_dict(orient="records")
        return {"ticker": ticker.upper(), "recommendations": recent, "source": "yfinance"}
    return {"ticker": ticker.upper(), "recommendations": [], "source": "yfinance"}


def run_stock_analysis(ticker: str = "SPY") -> dict:
    """Run comprehensive stock analysis — fundamentals, technicals, risk, analyst targets."""
    import yfinance as yf
    t = yf.Ticker(ticker.upper())
    info = t.info
    hist = t.history(period="1y")
    closes_1y = hist["Close"].tolist() if not hist.empty else []

    if len(closes_1y) > 1:
        returns = [(closes_1y[i] - closes_1y[i-1])/closes_1y[i-1] for i in range(1, len(closes_1y))]
        avg_ret = sum(returns)/len(returns)
        vol = (sum((r - avg_ret)**2 for r in returns)/len(returns))**0.5
        sharpe = (avg_ret / vol * (252**0.5)) if vol > 0 else 0
    else:
        avg_ret, vol, sharpe = 0, 0, 0

    ma50 = sum(closes_1y[-50:])/50 if len(closes_1y) >= 50 else None
    ma200 = sum(closes_1y[-200:])/200 if len(closes_1y) >= 200 else None
    price = info.get("currentPrice") or info.get("regularMarketPrice") or (closes_1y[-1] if closes_1y else None)

    recs = t.recommendations
    rec_summary = {}
    if recs is not None and len(recs) > 0:
        latest = recs.tail(1).to_dict(orient="records")
        if latest:
            rec_summary = latest[0]

    result = {
        "ticker": ticker.upper(),
        "name": info.get("shortName"),
        "sector": info.get("sector"),
        "current_price": price,
        "market_cap": info.get("marketCap"),
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margin": info.get("profitMargins"),
        "roe": info.get("returnOnEquity"),
        "ma_50": round(ma50, 2) if ma50 else None,
        "ma_200": round(ma200, 2) if ma200 else None,
        "beta": info.get("beta"),
        "1y_return_pct": round((closes_1y[-1]/closes_1y[0] - 1) * 100, 2) if len(closes_1y) > 1 else None,
        "daily_volatility_pct": round(vol * 100, 4) if vol else None,
        "annualized_sharpe": round(sharpe, 2) if sharpe else None,
        "target_mean": info.get("targetMeanPrice"),
        "recommendation_key": info.get("recommendationKey"),
        "analyst_recommendations": rec_summary,
        "dividend_yield": info.get("dividendYield"),
        "source": "yfinance",
    }
    return {k: v for k, v in result.items() if v is not None}
