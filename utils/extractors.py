import re
from typing import Optional


def extract_subreddit_name(text: str) -> Optional[str]:
    """
    Extract subreddit name from text (e.g., "r/python" -> "python").
    
    Args:
        text: Input text containing subreddit reference
        
    Returns:
        Extracted subreddit name or None
    """
    match = re.search(r'r/(\w+)', text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_number(text: str) -> Optional[int]:
    """
    Extract the first number from text.
    
    Args:
        text: Input text containing number
        
    Returns:
        Extracted number or None
    """
    numbers = re.findall(r'\b\d+\b', text)
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            return None
    return None


def extract_url(text: str) -> Optional[str]:
    """
    Extract the first URL from text.
    
    Args:
        text: Input text containing URL
        
    Returns:
        Extracted URL or None
    """
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else None


def extract_sort(text: str) -> Optional[str]:
    """
    Extract sort option from text.
    
    Args:
        text: Input text containing sort option
        
    Returns:
        Extracted sort option or None
    """
    sort_options = ['best', 'top', 'new', 'controversial', 'old', 'qa']
    words = text.lower().split()
    
    for sort_option in sort_options:
        if sort_option in words:
            return sort_option
    
    return None


def extract_post_type(text: str) -> str:
    """
    Extract post type from text (new, hot, top).
    
    Args:
        text: Input text containing post type
        
    Returns:
        Post type ('new', 'hot', or 'top')
    """
    text_lower = text.lower()
    
    if 'new' in text_lower or 'latest' in text_lower:
        return 'new'
    elif 'hot' in text_lower:
        return 'hot'
    elif 'top' in text_lower:
        return 'top'
    else:
        return 'hot'  # Default to hot posts