import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold


logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google's Gemini AI."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize Gemini service.
        
        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.0-flash-exp)
        """
        try:
            genai.configure(api_key=api_key)
            
            # Configure safety settings to be less restrictive
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }
            
            self.model = genai.GenerativeModel(
                model_name,
                safety_settings=safety_settings
            )
            logger.info(f"Gemini client initialized with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    def generate_response(self, prompt: str, max_length: int = 1000) -> str:
        """
        Generate a response from Gemini.
        
        Args:
            prompt: The prompt to send to Gemini
            max_length: Maximum response length
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If API call fails
        """
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Limit response length if needed
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    def summarize_post(self, title: str, content: str) -> str:
        """
        Summarize a Reddit post.
        
        Args:
            title: Post title
            content: Post content
            
        Returns:
            Summary of the post
        """
        prompt = f"""Summarize the following Reddit post concisely:

Title: {title}

Content: {content}

Provide a clear, informative summary in 2-3 sentences."""
        
        return self.generate_response(prompt)
    
    def summarize_comments(self, comments: List[Dict[str, Any]], max_comments: Optional[int] = None) -> str:
        """
        Summarize a list of Reddit comments.
        
        Args:
            comments: List of comment dictionaries
            max_comments: Maximum number of comments to include
            
        Returns:
            Summary of the comments
        """
        if not comments:
            return "This post has no comments yet."
        
        # Limit number of comments if specified
        comments_to_summarize = comments[:max_comments] if max_comments else comments
        
        # Prepare comment text
        comment_texts = []
        for i, comment in enumerate(comments_to_summarize, 1):
            author = comment.get('author', '[deleted]')
            body = comment.get('body', '')
            score = comment.get('score', 0)
            comment_texts.append(f"Comment {i} (by {author}, score: {score}): {body}")
        
        combined_comments = "\n\n".join(comment_texts)
        
        prompt = f"""Summarize the following {len(comments_to_summarize)} Reddit comments. 
Identify the main themes, sentiments, and any notable insights or discussions:

{combined_comments}

Provide a comprehensive summary that captures the essence of the discussion."""
        
        return self.generate_response(prompt, max_length=500)
    
    def generate_overview(self, posts: List[Dict[str, Any]], subreddit: str, post_type: str) -> str:
        """
        Generate an overview of multiple posts from a subreddit.
        
        Args:
            posts: List of post dictionaries with details
            subreddit: Name of the subreddit
            post_type: Type of posts (new, hot, top)
            
        Returns:
            Overview summary
        """
        # Prepare content for analysis
        post_summaries = []
        total_comments = 0
        
        for post in posts:
            title = post.get('title', '')
            content = post.get('content', '')
            comments = post.get('comments', [])
            total_comments += len(comments)
            
            # Include some comment samples
            comment_sample = ' '.join([c.get('body', '')[:100] for c in comments[:5]])
            
            post_summaries.append(f"Title: {title}\nContent: {content}\nComment samples: {comment_sample}")
        
        combined_content = "\n\n---\n\n".join(post_summaries)
        
        prompt = f"""Analyze these {len(posts)} {post_type} posts from r/{subreddit} and provide an overview:

{combined_content}

Please provide:
1. Main topics and themes being discussed
2. Overall sentiment and tone of the subreddit
3. Any trending issues or concerns
4. Notable patterns or insights

Keep the overview concise but informative."""
        
        return self.generate_response(prompt, max_length=800)
    
    def answer_question(self, question: str, context: str) -> str:
        """
        Answer a question based on provided context.
        
        Args:
            question: User's question
            context: Context to use for answering
            
        Returns:
            Answer to the question
        """
        prompt = f"""You are an assistant helping answer questions about Reddit posts and comments.
Use the provided context to answer the user's question accurately and helpfully.

Context:
{context}

Question: {question}

Provide a clear, direct answer based on the context. If the answer cannot be found in the context, say so."""
        
        return self.generate_response(prompt, max_length=500)