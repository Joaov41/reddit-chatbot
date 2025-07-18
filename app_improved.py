import logging
from flask import Flask, request, jsonify, render_template, session
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import BadRequest

from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    GEMINI_API_KEY,
    FLASK_SECRET_KEY,
    SESSION_TYPE,
    REDIS_URL
)
from services import RedditService, GeminiService
from utils import (
    extract_subreddit_name,
    extract_number,
    extract_url,
    extract_sort,
    extract_post_type,
    validate_subreddit_name,
    validate_reddit_url,
    sanitize_input,
    validate_post_number,
    validate_sort_option
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
app.config['SESSION_TYPE'] = SESSION_TYPE
Session(app)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri=REDIS_URL
)

# Initialize services
try:
    reddit_service = RedditService(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )
    gemini_service = GeminiService(api_key=GEMINI_API_KEY)
    logger.info("All services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise


@app.errorhandler(400)
def bad_request(e):
    """Handle bad request errors."""
    return jsonify({'error': 'Bad request', 'message': str(e)}), 400


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors."""
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': f"Rate limit exceeded: {e.description}"
    }), 429


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {e}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred. Please try again later.'
    }), 500


@app.route('/')
def home():
    """Render the chat interface."""
    return render_template('chat.html')


@app.route('/chat', methods=['POST'])
@limiter.limit("30 per minute")
def chat():
    """Handle chat requests."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            raise BadRequest("Invalid JSON payload")
        
        user_input = data.get('message')
        if not user_input or not isinstance(user_input, str):
            raise BadRequest("'message' field must be a non-empty string")
        
        # Sanitize input
        user_input = sanitize_input(user_input, max_length=1000)
        
        # Handle new session request
        if user_input.lower() == "new session":
            session.clear()
            return jsonify({
                'response': "New session started. What would you like to know about Reddit?"
            })
        
        # Handle post summarization request
        if "summarize post" in user_input.lower():
            return handle_post_summarization(user_input)
        
        # Handle follow-up questions about overview
        if 'overview_data' in session:
            return handle_overview_question(user_input)
        
        # Handle subreddit posts request
        if is_subreddit_posts_request(user_input):
            return handle_subreddit_posts(user_input)
        
        # Handle comment summarization
        if is_summarization_request(user_input):
            return handle_comment_summarization(user_input)
        
        # Handle follow-up questions about summarized posts
        if 'summarized_posts' in session:
            return handle_post_question(user_input)
        
        # Handle general queries
        return handle_general_query(user_input)
        
    except BadRequest as e:
        raise
    except Exception as e:
        logger.exception("Error processing chat request")
        return jsonify({
            'response': f"I'm sorry, but I encountered an error: {str(e)}"
        }), 500


def is_subreddit_posts_request(text: str) -> bool:
    """Check if the request is for subreddit posts."""
    text_lower = text.lower()
    return ("r/" in text_lower and 
            any(word in text_lower for word in ["posts", "latest", "new", "top", "hot"]))


def is_summarization_request(text: str) -> bool:
    """Check if the request is for summarization."""
    return any(phrase in text.lower() for phrase in ["summarize", "summary"])


def handle_post_summarization(user_input: str) -> tuple:
    """Handle post summarization requests."""
    post_title = user_input.lower().replace("summarize post", "").strip()
    
    if not post_title:
        return jsonify({
            'response': "Please provide a post title to summarize."
        }), 400
    
    # This would need to be implemented - search for post by title
    return jsonify({
        'response': "Post search by title is not yet implemented. Please provide a post URL or number."
    })


def handle_overview_question(user_input: str) -> tuple:
    """Handle questions about subreddit overview."""
    overview_data = session.get('overview_data', [])
    
    # Build context from overview data
    context_parts = []
    for post in overview_data[:10]:  # Limit context size
        context_parts.append(
            f"Title: {post.get('title', '')}\n"
            f"Content: {post.get('content', '')[:500]}\n"
            f"Top comments: {' '.join([c.get('body', '')[:100] for c in post.get('comments', [])[:3]])}"
        )
    
    context = "\n\n".join(context_parts)
    response = gemini_service.answer_question(user_input, context)
    
    return jsonify({'response': response})


def handle_subreddit_posts(user_input: str) -> tuple:
    """Handle requests for subreddit posts."""
    subreddit_name = extract_subreddit_name(user_input)
    if not subreddit_name:
        return jsonify({
            'response': "I couldn't find a subreddit name in your request. Please use format: r/subredditname"
        }), 400
    
    if not validate_subreddit_name(subreddit_name):
        return jsonify({
            'response': f"Invalid subreddit name: {subreddit_name}. Subreddit names must be 3-21 characters, alphanumeric and underscores only."
        }), 400
    
    num_posts = extract_number(user_input) or 10
    num_posts = min(max(num_posts, 1), 50)  # Limit between 1 and 50
    
    post_type = extract_post_type(user_input)
    
    try:
        posts = reddit_service.get_posts(subreddit_name, post_type, num_posts)
        
        if not posts:
            return jsonify({
                'response': f"No posts found in r/{subreddit_name}. The subreddit might be private or doesn't exist."
            })
        
        # Store in session
        session['posts'] = posts
        session['subreddit'] = subreddit_name
        
        # Format response
        numbered_posts = [
            f"{i+1}. {post['title']} (Score: {post['score']}, Comments: {post['num_comments']})"
            for i, post in enumerate(posts)
        ]
        
        response = (
            f"Here are the {len(posts)} {post_type} posts from r/{subreddit_name}:\n\n" +
            "\n".join(numbered_posts) +
            "\n\nYou can ask me to summarize any of these posts by number."
        )
        
        return jsonify({'response': response})
        
    except Exception as e:
        logger.error(f"Error fetching posts: {e}")
        return jsonify({
            'response': f"Error fetching posts from r/{subreddit_name}: {str(e)}"
        }), 500


def handle_comment_summarization(user_input: str) -> tuple:
    """Handle comment summarization requests."""
    # Extract URL or post number
    thread_url = extract_url(user_input)
    
    if not thread_url:
        post_number = extract_number(user_input)
        if post_number and 'posts' in session:
            posts = session.get('posts', [])
            if not validate_post_number(post_number, len(posts)):
                return jsonify({
                    'response': f"Invalid post number. Please choose between 1 and {len(posts)}."
                }), 400
            
            post = posts[post_number - 1]
            thread_url = post['url']
        else:
            return jsonify({
                'response': "Please provide a Reddit URL or refer to a post number from the list."
            }), 400
    
    if not validate_reddit_url(thread_url):
        return jsonify({
            'response': "Invalid Reddit URL. Please provide a valid reddit.com URL."
        }), 400
    
    sort = validate_sort_option(extract_sort(user_input) or 'best')
    
    try:
        # Get submission details
        submission_data = reddit_service.get_submission_details(thread_url, sort)
        
        # Generate summaries
        post_summary = gemini_service.summarize_post(
            submission_data['title'],
            submission_data['content']
        )
        
        comments_summary = gemini_service.summarize_comments(
            submission_data['comments']
        )
        
        # Store in session
        if 'summarized_posts' not in session:
            session['summarized_posts'] = {}
        
        session['summarized_posts'][thread_url] = {
            'summary': f"Post Summary:\\n{post_summary}\\n\\nComments Summary:\\n{comments_summary}",
            'data': submission_data,
            'sort': sort
        }
        session['current_post_url'] = thread_url
        
        response = (
            f"Post: {submission_data['title']}\\n\\n"
            f"Author: {submission_data['author']} | Score: {submission_data['score']}\\n\\n"
            f"Post Summary:\\n{post_summary}\\n\\n"
            f"Comments Summary (Total: {submission_data['comment_count']}, sorted by {sort}):\\n"
            f"{comments_summary}\\n\\n"
            "Feel free to ask questions about this post!"
        )
        
        return jsonify({'response': response})
        
    except Exception as e:
        logger.error(f"Error summarizing post: {e}")
        return jsonify({
            'response': f"Error summarizing post: {str(e)}"
        }), 500


def handle_post_question(user_input: str) -> tuple:
    """Handle questions about summarized posts."""
    current_url = session.get('current_post_url')
    if not current_url or current_url not in session.get('summarized_posts', {}):
        return jsonify({
            'response': "No post currently selected. Please summarize a post first."
        })
    
    post_data = session['summarized_posts'][current_url]['data']
    
    # Build context
    context = (
        f"Title: {post_data['title']}\\n"
        f"Content: {post_data['content']}\\n\\n"
        f"Comments:\\n" +
        "\\n".join([
            f"- {c['author']} (score: {c['score']}): {c['body']}"
            for c in post_data['comments'][:20]  # Limit to first 20 comments
        ])
    )
    
    response = gemini_service.answer_question(user_input, context)
    return jsonify({'response': response})


def handle_general_query(user_input: str) -> tuple:
    """Handle general Reddit-related queries."""
    prompt = (
        "You are a helpful assistant that provides information about Reddit. "
        "You can explain how to use Reddit, discuss popular subreddits, "
        "or give general information about Reddit features and etiquette.\\n\\n"
        f"Question: {user_input}"
    )
    
    response = gemini_service.generate_response(prompt)
    return jsonify({'response': response})


@app.route('/subreddit_overview', methods=['POST'])
@limiter.limit("5 per minute")
def subreddit_overview():
    """Generate an overview of a subreddit based on multiple posts."""
    try:
        data = request.get_json()
        if not data:
            raise BadRequest("Invalid JSON payload")
        
        subreddit_name = data.get('subreddit')
        if not subreddit_name or not validate_subreddit_name(subreddit_name):
            raise BadRequest("Invalid subreddit name")
        
        num_posts = min(max(data.get('num_posts', 20), 5), 50)
        post_type = data.get('post_type', 'new')
        
        if post_type not in ['new', 'hot', 'top']:
            post_type = 'new'
        
        # Fetch posts
        posts = reddit_service.get_posts(subreddit_name, post_type, num_posts)
        
        if not posts:
            return jsonify({
                'response': f"No posts found in r/{subreddit_name}"
            })
        
        # Fetch detailed information for each post
        urls = [post['url'] for post in posts]
        detailed_posts = reddit_service.fetch_multiple_submissions(urls)
        
        # Update posts with detailed information
        for post, details in zip(posts, detailed_posts):
            post.update(details)
        
        # Store in session
        session['overview_data'] = posts
        
        # Generate overview
        overview = gemini_service.generate_overview(posts, subreddit_name, post_type)
        
        # Calculate statistics
        total_comments = sum(post.get('comment_count', 0) for post in posts)
        avg_score = sum(post.get('score', 0) for post in posts) / len(posts) if posts else 0
        
        response = (
            f"Overview of r/{subreddit_name} based on {len(posts)} {post_type} posts:\\n\\n"
            f"Statistics:\\n"
            f"- Total comments analyzed: {total_comments}\\n"
            f"- Average post score: {avg_score:.1f}\\n\\n"
            f"{overview}\\n\\n"
            "You can now ask questions about these posts and their content."
        )
        
        return jsonify({'response': response})
        
    except BadRequest as e:
        raise
    except Exception as e:
        logger.error(f"Error generating overview: {e}")
        return jsonify({
            'response': f"Error generating overview: {str(e)}"
        }), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    app.run(debug=False, port=5000)