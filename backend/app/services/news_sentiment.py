"""
News Sentiment NLP Engine using FinBERT.
Suppresses BUY signals when recent news is strongly negative.
Falls back to keyword analysis if FinBERT is unavailable.
"""

import feedparser
from datetime import datetime, timedelta
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class NewsSentimentAnalyzer:

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

    SENTIMENT_MODIFIERS = {
        "STRONGLY_POSITIVE": +0.05,
        "MILDLY_POSITIVE": +0.02,
        "NEUTRAL": 0.0,
        "MILDLY_NEGATIVE": -0.05,
        "STRONGLY_NEGATIVE": -0.15,
    }

    NEWS_FEEDS = [
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "https://feeds.feedburner.com/ndtvprofit-latest",
    ]

    NEGATIVE_KEYWORDS = [
        'fraud', 'scam', 'raid', 'sebi', 'penalty', 'fine', 'lawsuit',
        'investigation', 'bankruptcy', 'default', 'loss', 'decline', 'downgrade',
        'promoter selling', 'insider trading', 'collapse',
    ]
    POSITIVE_KEYWORDS = [
        'profit', 'growth', 'upgrade', 'buy', 'target', 'record', 'order',
        'contract', 'expansion', 'dividend', 'acquisition', 'partnership',
    ]

    def __init__(self):
        self._pipeline = None
        self._finbert_failed = False

    def _get_pipeline(self):
        if self._finbert_failed:
            return None
        if self._pipeline is None:
            try:
                from transformers import pipeline as hf_pipeline
                logger.info("Loading FinBERT model...")
                self._pipeline = hf_pipeline(
                    "text-classification",
                    model="ProsusAI/finbert",
                    tokenizer="ProsusAI/finbert",
                    max_length=512,
                    truncation=True,
                )
                logger.info("FinBERT loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load FinBERT: {e}")
                self._pipeline = None
                self._finbert_failed = True
        return self._pipeline

    def fetch_news(self, symbol: str, company_name: str = None, hours: int = 168) -> list:
        search_terms = [symbol.upper()]
        if company_name:
            search_terms.append(company_name.split()[0])

        # Use timezone-aware UTC datetime for cutoff
        try:
            from datetime import timezone
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        except ImportError:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
        articles = []

        # 1. Fetch targeted news from yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            yf_news = ticker.news
            if yf_news:
                for item in yf_news:
                    content = item.get('content', {})
                    if not content:
                        continue
                        
                    pub_str = content.get('pubDate', '')
                    pub_date = None
                    if pub_str:
                        try:
                            from dateutil import parser
                            # Parse and make timezone-aware
                            pub_date = parser.parse(pub_str)
                            from datetime import timezone
                            if pub_date.tzinfo is None:
                                pub_date = pub_date.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    
                    if not pub_date:
                        try:
                            from datetime import timezone
                            pub_date = datetime.now(timezone.utc)
                        except Exception:
                            pub_date = datetime.utcnow()
                            
                    if pub_date >= cutoff:
                        articles.append({
                            'title': content.get('title', ''),
                            'summary': content.get('summary', '')[:500],
                            'url': content.get('clickThroughUrl', {}).get('url', ''),
                            'published': pub_date.isoformat(),
                            'source': content.get('provider', {}).get('displayName', 'Yahoo Finance')
                        })
        except Exception as e:
            logger.debug(f"yfinance news error for {symbol}: {e}")

        # 2. Add from generic RSS feeds
        for feed_url in self.NEWS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:30]:
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    text = f"{title} {summary}"

                    if any(term.lower() in text.lower() for term in search_terms):
                        try:
                            from datetime import timezone
                            pub_date = datetime.now(timezone.utc)
                        except Exception:
                            pub_date = datetime.utcnow()
                            
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            try:
                                import time
                                dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                                from datetime import timezone
                                pub_date = dt.replace(tzinfo=timezone.utc)
                            except Exception:
                                pass

                        if pub_date >= cutoff:
                            articles.append({
                                'title': title,
                                'summary': summary[:500],
                                'url': entry.get('link', ''),
                                'published': pub_date.isoformat(),
                                'source': feed.feed.get('title', feed_url),
                            })
            except Exception as e:
                logger.debug(f"Feed error {feed_url}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for a in articles:
            key = a['title'][:50].lower()
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique[:10]

    def analyze_sentiment(self, articles: list) -> dict:
        if not articles:
            return {
                'sentiment': 'NEUTRAL', 'confidence_modifier': 0.0,
                'article_count': 0, 'positive_count': 0, 'negative_count': 0, 'details': [],
            }

        pipeline_fn = self._get_pipeline()
        if not pipeline_fn:
            return self._fallback_sentiment(articles)

        results = []
        for article in articles:
            try:
                text = article['title'][:512]
                prediction = pipeline_fn(text)[0]
                results.append({
                    'title': article['title'],
                    'source': article['source'],
                    'published': article['published'],
                    'sentiment': prediction['label'].lower(),
                    'score': round(prediction['score'], 3),
                })
            except Exception:
                pass

        if not results:
            return self._fallback_sentiment(articles)

        positive = [r for r in results if r['sentiment'] == self.POSITIVE]
        negative = [r for r in results if r['sentiment'] == self.NEGATIVE]
        neutral = [r for r in results if r['sentiment'] == self.NEUTRAL]

        pos_score = sum(r['score'] for r in positive)
        neg_score = sum(r['score'] for r in negative)
        net_score = pos_score - neg_score

        if net_score > 1.5 and len(positive) >= 2:
            label = "STRONGLY_POSITIVE"
        elif net_score > 0.3:
            label = "MILDLY_POSITIVE"
        elif net_score < -1.5 and len(negative) >= 2:
            label = "STRONGLY_NEGATIVE"
        elif net_score < -0.3:
            label = "MILDLY_NEGATIVE"
        else:
            label = "NEUTRAL"

        return {
            'sentiment': label,
            'confidence_modifier': self.SENTIMENT_MODIFIERS[label],
            'article_count': len(results),
            'positive_count': len(positive),
            'negative_count': len(negative),
            'neutral_count': len(neutral),
            'net_score': round(net_score, 3),
            'details': results,
            'summary': self._generate_summary(label, len(positive), len(negative), len(results)),
        }

    def _generate_summary(self, sentiment: str, pos: int, neg: int, total: int) -> str:
        summaries = {
            "STRONGLY_POSITIVE": f"✅ {pos}/{total} articles positive — Strong news tailwind",
            "MILDLY_POSITIVE": f"🟢 {pos}/{total} articles positive — Mild news support",
            "NEUTRAL": f"⚪ Mixed news — {pos} positive, {neg} negative of {total}",
            "MILDLY_NEGATIVE": f"🟡 {neg}/{total} articles negative — Caution advised",
            "STRONGLY_NEGATIVE": f"🔴 {neg}/{total} articles negative — BUY signal suppressed",
        }
        return summaries.get(sentiment, "No recent news found")

    def _fallback_sentiment(self, articles: list) -> dict:
        neg_count = sum(
            1 for a in articles
            if any(kw in (a['title'] + a.get('summary', '')).lower() for kw in self.NEGATIVE_KEYWORDS)
        )
        pos_count = sum(
            1 for a in articles
            if any(kw in (a['title'] + a.get('summary', '')).lower() for kw in self.POSITIVE_KEYWORDS)
        )

        if neg_count > pos_count and neg_count >= 2:
            return {
                'sentiment': 'MILDLY_NEGATIVE', 'confidence_modifier': -0.05,
                'article_count': len(articles), 'positive_count': pos_count,
                'negative_count': neg_count, 'model': 'keyword_fallback',
            }
        return {
            'sentiment': 'NEUTRAL', 'confidence_modifier': 0.0,
            'article_count': len(articles), 'positive_count': pos_count,
            'negative_count': neg_count, 'model': 'keyword_fallback',
        }

    def get_signal_sentiment(self, symbol: str, company_name: str = None) -> dict:
        articles = self.fetch_news(symbol, company_name, hours=24)
        analysis = self.analyze_sentiment(articles)
        analysis['symbol'] = symbol
        return analysis
