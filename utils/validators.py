import re
from typing import Optional
from urllib.parse import urlparse


def validate_subreddit_name(name: str) -> bool:
    """
    Validate subreddit name according to Reddit's rules.
    
    Args:
        name: Subreddit name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False
    
    # Subreddit names must be 3-21 characters, alphanumeric and underscores only
    pattern = r'^[a-zA-Z0-9_]{3,21}$'
    return bool(re.match(pattern, name))


def validate_reddit_url(url: str) -> bool:
    """
    Validate if a URL is a valid Reddit URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid Reddit URL, False otherwise
    """
    try:
        parsed = urlparse(url)
        valid_domains = ['reddit.com', 'www.reddit.com', 'old.reddit.com']
        return parsed.hostname in valid_domains and parsed.scheme in ['http', 'https']
    except Exception:
        return False


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input by removing potentially harmful content.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    # Remove any HTML/script tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Limit length
    text = text[:max_length]
    
    # Remove multiple whitespaces
    text = ' '.join(text.split())
    
    return text.strip()


def validate_post_number(number: int, max_posts: int) -> bool:
    """
    Validate if a post number is within valid range.
    
    Args:
        number: Post number to validate
        max_posts: Maximum number of posts
        
    Returns:
        True if valid, False otherwise
    """
    return 1 <= number <= max_posts


def validate_sort_option(sort: str) -> str:
    """
    Validate and normalize sort option.
    
    Args:
        sort: Sort option to validate
        
    Returns:
        Normalized sort option or 'best' as default
    """
    valid_sorts = ['best', 'top', 'new', 'controversial', 'old', 'qa']
    sort_lower = sort.lower() if sort else 'best'
    return sort_lower if sort_lower in valid_sorts else 'best'