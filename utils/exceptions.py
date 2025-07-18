class RedditBotException(Exception):
    """Base exception for Reddit bot."""
    pass


class RedditAPIException(RedditBotException):
    """Exception for Reddit API errors."""
    pass


class GeminiAPIException(RedditBotException):
    """Exception for Gemini API errors."""
    pass


class ValidationException(RedditBotException):
    """Exception for validation errors."""
    pass


class RateLimitException(RedditBotException):
    """Exception for rate limit errors."""
    pass


class CacheException(RedditBotException):
    """Exception for cache-related errors."""
    pass