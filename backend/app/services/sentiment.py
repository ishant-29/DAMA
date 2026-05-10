"""
Social sentiment analysis service
"""
import praw
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import Dict, Optional
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Analyze social sentiment from Reddit"""
    
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.reddit = None
        self.sentiment_cache = {}
        self.cache_ttl = 3600  # 1 hour
        
    def _init_reddit(self):
        """Initialize Reddit API (requires credentials in config)"""
        try:
            # Reddit API requires credentials - skip if not configured
            if not settings.TELEGRAM_BOT_TOKEN:  # Placeholder check
                logger.warning("Reddit API not configured, using placeholder sentiment")
                return None
            
            # self.reddit = praw.Reddit(
            #     client_id="YOUR_CLIENT_ID",
            #     client_secret="YOUR_SECRET",
            #     user_agent="NSE Signal Engine"
            # )
        except Exception as e:
            logger.error(f"Failed to initialize Reddit API: {e}")
            return None
    
    def get_sentiment_score(self, symbol: str) -> float:
        """
        Get sentiment score for a stock symbol (-1 to 1)
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE.NS")
            
        Returns:
            Sentiment score between -1 (negative) and 1 (positive)
        """
        # Check cache
        cache_key = f"{symbol}_{int(time.time() / self.cache_ttl)}"
        if cache_key in self.sentiment_cache:
            return self.sentiment_cache[cache_key]
        
        # Extract base symbol (remove .NS)
        base_symbol = symbol.replace('.NS', '')
        
        # Get sentiment from Reddit
        sentiment = self._get_reddit_sentiment(base_symbol)
        
        # Cache result
        self.sentiment_cache[cache_key] = sentiment
        
        return sentiment
    
    def _get_reddit_sentiment(self, symbol: str) -> float:
        """Get sentiment from Reddit mentions"""
        try:
            if self.reddit is None:
                # Return neutral sentiment if Reddit not configured
                return 0.0
            
            # Search relevant subreddits
            subreddits = ['stocks', 'investing', 'IndiaInvestments']
            all_scores = []
            
            for sub in subreddits:
                try:
                    subreddit = self.reddit.subreddit(sub)
                    # Search for mentions
                    for submission in subreddit.search(symbol, time_filter='week', limit=10):
                        # Analyze title
                        title_sentiment = self.vader.polarity_scores(submission.title)
                        all_scores.append(title_sentiment['compound'])
                        
                        # Analyze top comments
                        try:
                            submission.comments.replace_more(limit=0)
                            for comment in submission.comments[:5]:
                                comment_sentiment = self.vader.polarity_scores(comment.body)
                                all_scores.append(comment_sentiment['compound'])
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"Error searching r/{sub}: {e}")
                    continue
            
            if all_scores:
                # Return average sentiment
                return sum(all_scores) / len(all_scores)
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Sentiment analysis error for {symbol}: {e}")
            return 0.0
    
    def apply_sentiment_to_confidence(
        self,
        base_confidence: float,
        symbol: str,
        signal_type: str
    ) -> float:
        """
        Adjust confidence score based on sentiment
        
        Args:
            base_confidence: Original confidence score
            symbol: Stock symbol
            signal_type: BUY or SELL
            
        Returns:
            Adjusted confidence score
        """
        sentiment = self.get_sentiment_score(symbol)
        
        # Adjust confidence based on sentiment alignment
        if signal_type == "BUY":
            # Positive sentiment boosts BUY confidence
            adjustment = sentiment * 0.05  # Max +/- 5%
        else:  # SELL
            # Negative sentiment boosts SELL confidence
            adjustment = -sentiment * 0.05
        
        # Apply adjustment
        adjusted = base_confidence + adjustment
        
        # Clamp to valid range
        return max(0.01, min(0.99, adjusted))

# Global instance
sentiment_analyzer = SentimentAnalyzer()
