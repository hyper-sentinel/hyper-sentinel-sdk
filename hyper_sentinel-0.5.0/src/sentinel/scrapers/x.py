"""
X (Twitter) API v2 Scraper
Search tweets, get trends, and run basic sentiment analysis.

Requires: X_BEARER_TOKEN in .env (get at developer.twitter.com)
"""

import requests
from typing import Optional


class XScraper:
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.twitter.com/2/"

    def _make_request(self, endpoint: str, params: Optional[dict] = None, method: str = 'GET') -> dict:
        url = self.base_url + endpoint
        import time
        last_err = None
        for attempt in range(2):
            try:
                if method == 'GET':
                    response = requests.get(url, headers=self.headers, params=params, timeout=10)
                elif method == 'POST':
                    response = requests.post(url, headers=self.headers, json=params, timeout=10)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_err = e
                if attempt == 0:
                    time.sleep(2)  # Brief retry on transient DNS/network errors
                    continue
                raise Exception(f"Network error after retry ({endpoint}): {str(e)}")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Error making request to {endpoint}: {str(e)}")
        raise Exception(f"Request failed ({endpoint}): {str(last_err)}")

    def search_tweets(self, query: str, max_results: int = 100, start_time: Optional[str] = None, end_time: Optional[str] = None) -> list[dict]:
        """
        Search for tweets using v2 API.

        Args:
            query: Search query
            max_results: Maximum number of results (10-100, Twitter minimum is 10)
            start_time: YYYY-MM-DDTHH:mm:ssZ (ISO 8601)
            end_time: YYYY-MM-DDTHH:mm:ssZ (ISO 8601)

        Returns:
            List of tweet dicts with author info attached.
        """
        # Twitter API requires max_results between 10-100
        max_results = max(10, min(100, max_results))

        endpoint = "tweets/search/recent"
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,author_id,text,public_metrics,source",
            "user.fields": "name,username,verified",
            "expansions": "author_id"
        }
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        try:
            data = self._make_request(endpoint, params)
        except Exception as e:
            # Return empty list with error context instead of crashing
            return [{"error": str(e), "query": query}]

        tweets = data.get('data', [])
        users = {user['id']: user for user in data.get('includes', {}).get('users', [])}

        for tweet in tweets:
            author_id = tweet['author_id']
            if author_id in users:
                tweet['author'] = users[author_id]

        return tweets

    def get_trending_topics(self, location_id: int = 1) -> list[dict]:
        """
        Get trending topics for a location.

        Args:
            location_id: WOEID (1 = Worldwide)

        Returns:
            List of trending topics.
        """
        endpoint = "trends/place.json"
        params = {"id": location_id}
        return self._make_request(endpoint, params, method='GET')[0].get('trends', [])

    def get_tweet_sentiment(self, tweets: list[dict]) -> list[dict]:
        """
        Basic keyword-based sentiment analysis on tweets.

        Returns list of dicts with tweet_id, sentiment (positive/negative/neutral), and score.
        """
        positive_words = ['good', 'bullish', 'buy', 'up', 'moon', 'pump', 'ath', 'breakout', 'gains', 'long']
        negative_words = ['bad', 'bearish', 'sell', 'down', 'dump', 'crash', 'short', 'rekt', 'rug', 'scam']

        sentiments = []
        for tweet in tweets:
            text = tweet['text'].lower()
            positive = sum(1 for word in positive_words if word in text)
            negative = sum(1 for word in negative_words if word in text)
            sentiment = 'positive' if positive > negative else 'negative' if negative > positive else 'neutral'
            sentiments.append({
                'tweet_id': tweet['id'],
                'sentiment': sentiment,
                'score': positive - negative
            })
        return sentiments
