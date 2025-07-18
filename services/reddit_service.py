import logging
from typing import List, Dict, Optional, Any
import praw
from praw.models import Submission
from concurrent.futures import ThreadPoolExecutor, as_completed

from models import LRUCache
from utils import validate_subreddit_name, validate_reddit_url


logger = logging.getLogger(__name__)


class RedditService:
    """Service for interacting with Reddit API."""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """
        Initialize Reddit service.
        
        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string
        """
        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            # Test the connection
            self.reddit.user.me()
            logger.info("Reddit client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            raise
        
        # Initialize cache with 1 hour TTL
        self.cache = LRUCache(capacity=100, ttl=3600)
    
    def get_posts(self, subreddit_name: str, post_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get posts from a subreddit.
        
        Args:
            subreddit_name: Name of the subreddit
            post_type: Type of posts ('new', 'hot', 'top')
            limit: Number of posts to fetch
            
        Returns:
            List of post dictionaries
            
        Raises:
            ValueError: If subreddit name is invalid
            Exception: If Reddit API call fails
        """
        if not validate_subreddit_name(subreddit_name):
            raise ValueError(f"Invalid subreddit name: {subreddit_name}")
        
        cache_key = f"posts:{subreddit_name}:{post_type}:{limit}"
        cached_posts = self.cache.get(cache_key)
        if cached_posts:
            logger.info(f"Returning cached posts for {cache_key}")
            return cached_posts
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            if post_type == 'new':
                posts_generator = subreddit.new(limit=limit)
            elif post_type == 'hot':
                posts_generator = subreddit.hot(limit=limit)
            elif post_type == 'top':
                posts_generator = subreddit.top(time_filter='week', limit=limit)
            else:
                posts_generator = subreddit.hot(limit=limit)
            
            posts = []
            for post in posts_generator:
                # Skip stickied posts for hot and top
                if post.stickied and post_type in ['hot', 'top']:
                    continue
                
                posts.append({
                    'title': post.title,
                    'score': post.score,
                    'url': f"https://www.reddit.com{post.permalink}",
                    'author': str(post.author) if post.author else '[deleted]',
                    'created_utc': post.created_utc,
                    'num_comments': post.num_comments,
                    'id': post.id
                })
                
                if len(posts) >= limit:
                    break
            
            self.cache.put(cache_key, posts)
            return posts
            
        except Exception as e:
            logger.error(f"Error fetching posts from r/{subreddit_name}: {e}")
            raise
    
    def get_submission_details(self, url: str, sort: str = 'best') -> Dict[str, Any]:
        """
        Get detailed information about a Reddit submission including comments.
        
        Args:
            url: Reddit post URL
            sort: Comment sort order
            
        Returns:
            Dictionary with post details and comments
            
        Raises:
            ValueError: If URL is invalid
            Exception: If Reddit API call fails
        """
        if not validate_reddit_url(url):
            raise ValueError(f"Invalid Reddit URL: {url}")
        
        cache_key = f"submission:{url}:{sort}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached submission for {url}")
            return cached_data
        
        try:
            submission = self.reddit.submission(url=url)
            submission.comment_sort = sort
            
            # Expand all comments
            submission.comments.replace_more(limit=None)
            all_comments = submission.comments.list()
            
            result = {
                'title': submission.title,
                'content': submission.selftext,
                'author': str(submission.author) if submission.author else '[deleted]',
                'score': submission.score,
                'url': url,
                'created_utc': submission.created_utc,
                'num_comments': submission.num_comments,
                'comments': [
                    {
                        'body': comment.body,
                        'author': str(comment.author) if comment.author else '[deleted]',
                        'score': comment.score,
                        'created_utc': comment.created_utc
                    }
                    for comment in all_comments
                ],
                'comment_count': len(all_comments)
            }
            
            self.cache.put(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error fetching submission {url}: {e}")
            raise
    
    def fetch_multiple_submissions(self, urls: List[str], max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch multiple submissions concurrently.
        
        Args:
            urls: List of Reddit post URLs
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of submission details
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.get_submission_details, url): url
                for url in urls
            }
            
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    logger.error(f"Error fetching {url}: {e}")
                    results.append({
                        'url': url,
                        'error': str(e),
                        'comments': [],
                        'content': ''
                    })
        
        return results