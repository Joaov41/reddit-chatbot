from flask import Flask, request, jsonify, render_template, session
import praw
import google.generativeai as genai
from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    GEMINI_API_KEY,
)
import logging
from flask_session import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict

# ----------------------
# LRU CACHE IMPLEMENTATION
# ----------------------
class LRUCache:
    """
    A simple LRU cache using OrderedDict:
    - put(key, value): add/update an item in O(1)
    - get(key): retrieve an item in O(1)
    - evicts the oldest item when capacity is exceeded
    """
    def __init__(self, capacity=100):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None
        # Move this key to the end to mark it as most recently used
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        # If key exists, we delete it first so we can re-insert it at the end
        if key in self.cache:
            del self.cache[key]
        self.cache[key] = value
        # Evict the least recently used key if capacity is exceeded
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

# Instantiate a global LRU cache
lru_cache = LRUCache(capacity=20)  # Adjust capacity as needed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Initialize Reddit API client
try:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    logger.info("Reddit client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Reddit client: {e}")
    raise

# Initialize Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")
    logger.info("Gemini client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    raise

@app.route('/')
def home():
    """
    Render the chat interface.
    """
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or not isinstance(data, dict):
        logger.warning("Invalid JSON payload received.")
        return jsonify({'response': "Invalid input. Please provide a valid JSON payload."}), 400

    user_input = data.get('message')
    if not user_input or not isinstance(user_input, str):
        logger.warning("Invalid or missing 'message' field in the request.")
        return jsonify({'response': "Invalid input. 'message' field must be a non-empty string."}), 400

    try:
        if user_input.lower() == "new session":
            session.clear()
            return jsonify({'response': "New session started. What would you like to know about Reddit?"})

        # Handle summarization requests for specific posts
        if "summarize post" in user_input.lower():
            post_title = user_input.lower().replace("summarize post", "").strip()
            return summarize_post({"post_title": post_title})

        # Handle follow-up questions about the overview
        if 'overview_data' in session:
            context = "\n\n".join([
                f"Title: {post['title']}\n\nContent: {post['content']}\n\nComments: {' '.join(post['comments'])}"
                for post in session['overview_data']
            ])

            prompt = (
                "You are an assistant answering questions about multiple Reddit posts and their comments. "
                "Use the provided context to answer the user's question.\n\n"
                f"Context:\n{context}\n\nQuestion: {user_input}"
            )
            response = gemini_model.generate_content(prompt)
            return jsonify({'response': response.text.strip()})

        # Check if the query is about posts in a subreddit
        if ("r/" in user_input.lower() and
            any(word in user_input.lower() for word in ["posts", "latest", "new", "top", "hot"])):
            subreddit_name = extract_subreddit_name(user_input)
            num_posts = extract_number(user_input) or 10

            if "new" in user_input.lower():
                posts = get_new_posts(subreddit_name, num_posts)
                post_type = "newest"
            elif "hot" in user_input.lower():
                posts = get_hot_posts(subreddit_name, num_posts)
                post_type = "hottest"
            elif "top" in user_input.lower():
                posts = get_top_posts(subreddit_name, num_posts)
                post_type = "top"
            else:
                posts = get_hot_posts(subreddit_name, num_posts)
                post_type = "hottest"

            logger.info(f"User input: {user_input}")
            logger.info(f"Extracted subreddit: {subreddit_name}")
            logger.info(f"Number of posts: {num_posts}")
            logger.info(f"Post type: {post_type}")

            session['posts'] = posts
            session['subreddit'] = subreddit_name

            numbered_posts = [f"{i+1}. {post['title']} (Score: {post['score']})" for i, post in enumerate(posts)]
            response = f"Here are the {num_posts} {post_type} posts from r/{subreddit_name}:\n\n" + "\n".join(numbered_posts)
            return jsonify({'response': response})

        # Check if the query is about summarizing comments
        elif any(phrase in user_input.lower() for phrase in ["summarize", "summary"]):
            thread_url = extract_url(user_input)
            if not thread_url:
                post_number = extract_number(user_input)
                if post_number and 'posts' in session:
                    if 1 <= post_number <= len(session['posts']):
                        post = session['posts'][post_number - 1]
                        thread_url = post['url']
                    else:
                        return jsonify({'response': f"Invalid post number. Please choose a number between 1 and {len(session['posts'])}."})
                else:
                    return jsonify({'response': "I'm sorry, but I couldn't find a valid Reddit URL or post number in your request. Please provide a URL or refer to a post number from the previous list."})

            if thread_url:
                sort = extract_sort(user_input) or 'best'
                logger.info(f"Summarizing post and comments: URL={thread_url}, sort={sort}")
                summary = summarize_comments(thread_url, sort=sort)

                if 'summarized_posts' not in session:
                    session['summarized_posts'] = {}
                # Store the entire summary + raw content in the session
                session['summarized_posts'][thread_url] = summary
                session['current_post_url'] = thread_url

                response = (
                    f"Here's a summary of the post and its comments (comments sorted by {sort}):\n\n"
                    f"{summary['summary']}\n\n"
                    "Use the post's details for more follow-up questions!"
                )
                return jsonify({'response': response})
            else:
                return jsonify({'response': "I'm sorry, but I couldn't find a valid Reddit URL for this post."})

        # Handle follow-up questions about summarized posts
        elif 'summarized_posts' in session:
            post_number = extract_number(user_input)
            if post_number and 'posts' in session:
                if 1 <= post_number <= len(session['posts']):
                    post = session['posts'][post_number - 1]
                    thread_url = post['url']
                    if thread_url in session['summarized_posts']:
                        session['current_post_url'] = thread_url
                    else:
                        return jsonify({'response': f"Post {post_number} hasn't been summarized yet. Please ask to summarize it first."})
                else:
                    return jsonify({'response': f"Invalid post number. Please choose a number between 1 and {len(session['posts'])}."})

            current_post_url = session.get('current_post_url')
            if current_post_url and current_post_url in session['summarized_posts']:
                current_post = session['summarized_posts'][current_post_url]

                # Build context from both summary and raw data
                context = (
                    f"Title: {current_post['post_title']}\n\n"
                    f"Post Content:\n{current_post['post_content']}\n\n"
                    f"Comments:\n{' '.join(current_post['comments'])}\n\n"
                    f"Summary:\n{current_post['summary']}"
                )

                prompt = (
                    "You are an assistant helping answer questions about a Reddit post and its comments. "
                    "Use the provided context to answer the user's question.\n\n"
                    f"Context:\n{context}\n\nQuestion: {user_input}"
                )
                response = gemini_model.generate_content(prompt)
                return jsonify({'response': response.text.strip()})
            else:
                return jsonify({'response': "I'm sorry, but I don't have any summarized post to refer to. Please ask to summarize a post first."})

        else:
            # Use Gemini for general queries
            prompt = (
                "You are a helpful assistant that provides information about Reddit. "
                "You can explain how to use Reddit, discuss popular subreddits, or give general information about Reddit features and etiquette.\n\n"
                f"Question: {user_input}"
            )
            response = gemini_model.generate_content(prompt)
            return jsonify({'response': response.text.strip()})

    except Exception as e:
        logger.exception("An error occurred while processing the request.")
        return jsonify({'response': f"I'm sorry, but I encountered an error: {str(e)}"}), 500

@app.route('/subreddit_overview', methods=['POST'])
def subreddit_overview():
    data = request.get_json()
    subreddit_name = data.get('subreddit')
    num_posts = data.get('num_posts', 20)
    # READ "post_type" INSTEAD OF "sort_method"
    sort_method = data.get('post_type', 'new')  # default to 'new' if not provided

    try:
        # Decide which function to call based on sort_method
        if sort_method == 'hot':
            posts = get_hot_posts(subreddit_name, num_posts)
        elif sort_method == 'top':
            posts = get_top_posts(subreddit_name, num_posts)
        else:  # handle "new" or any invalid value by defaulting to "new"
            posts = get_new_posts(subreddit_name, num_posts)

        # Fetch details of each post (including comments)
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_post = {
                executor.submit(fetch_post_details, post['url']): post
                for post in posts
            }
            for future in as_completed(future_to_post):
                post = future_to_post[future]
                post_details = future.result()
                post.update(post_details)

        # At this point, each post has a "comments" list
        # that contains the text of all comments fetched for that post.
        session['overview_data'] = posts

        # Compute total number of comments across all posts
        total_comments = sum(len(post['comments']) for post in posts)

        # Display or log the total comments
        logger.info(
            f"Fetched {len(posts)} posts from r/{subreddit_name}, "
            f"with a total of {total_comments} comments extracted."
        )

        combined_content = "\n\n".join([
            f"Title: {post['title']}\n\nContent: {post['content']}\n\n"
            f"Comments: {' '.join(post['comments'])} (Total comments: {len(post['comments'])})"
            for post in posts
        ])

        prompt = (
            f"Provide an overview of the main topics and themes from these {num_posts} "
            f"{sort_method} posts in r/{subreddit_name}:\n\n{combined_content}"
        )

        overview_response = gemini_model.generate_content(prompt)
        overview = overview_response.text.strip()

        return jsonify({
            'response': (
                f"Overview of r/{subreddit_name} based on {num_posts} {sort_method} posts. "
                f"Total comments extracted: {total_comments}.\n\n{overview}\n\n"
                "You can now ask questions about these posts and their content."
            )
        })
    except Exception as e:
        logger.exception("Error in subreddit_overview")
        return jsonify({'response': f"An error occurred: {str(e)}"}), 500

def fetch_post_details(post_url):
    """
    Fetch post details, including main content and full comments list.
    Now uses the LRU cache to avoid redundant Reddit API calls for the same URL.
    """
    cached_result = lru_cache.get(post_url)
    if cached_result is not None:
        return cached_result

    submission = reddit.submission(url=post_url)
    submission.comments.replace_more(limit=None)
    all_comments = submission.comments.list()
    result = {
        'content': submission.selftext,
        'comments': [comment.body for comment in all_comments]
    }

    # Store in LRU cache
    lru_cache.put(post_url, result)
    return result

def extract_subreddit_name(text):
    import re
    match = re.search(r'r/(\w+)', text)
    return match.group(1) if match else None

def extract_number(text):
    import re
    numbers = re.findall(r'\b\d+\b', text)
    return int(numbers[0]) if numbers else None

def extract_url(text):
    import re
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
    return urls[0] if urls else None

def get_new_posts(subreddit_name, limit):
    subreddit = reddit.subreddit(subreddit_name)
    return [{"title": post.title, "score": post.score, "url": f"https://www.reddit.com{post.permalink}"}
            for post in subreddit.new(limit=limit)]

def get_hot_posts(subreddit_name, limit):
    subreddit = reddit.subreddit(subreddit_name)
    posts_data = []
    for post in subreddit.hot(limit=limit):
        if post.stickied:
            continue  # Skip sticky posts
        posts_data.append({
            "title": post.title,
            "score": post.score,
            "url": f"https://www.reddit.com{post.permalink}"
        })
    return posts_data

def get_top_posts(subreddit_name, limit):
    subreddit = reddit.subreddit(subreddit_name)
    posts_data = []
    for post in subreddit.top(time_filter='week', limit=limit):
        if post.stickied:
            continue  # Skip sticky posts
        posts_data.append({
            "title": post.title,
            "score": post.score,
            "url": f"https://www.reddit.com{post.permalink}"
        })
    return posts_data

def summarize_comments(thread_url, sort='best'):
    """
    Summarize the post content and its comments.
    Uses LRU cache keyed by (thread_url + sort) to avoid re-summarizing the same post + sort combination.
    Returns a dictionary with both the summary and the raw data for follow-up context.
    """
    cache_key = f"{thread_url}:{sort}"
    cached_result = lru_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    try:
        logger.info(f"Fetching submission: {thread_url}")
        submission = reddit.submission(url=thread_url)

        post_content = f"Title: {submission.title}\n\nContent: {submission.selftext}"
        logger.info("Summarizing post content")

        post_summary_prompt = f"Summarize the following Reddit post:\n\n{post_content}"
        post_summary_response = gemini_model.generate_content(post_summary_prompt)
        post_summary = post_summary_response.text.strip()

        logger.info(f"Setting comment sort to: {sort}")
        submission.comment_sort = sort

        logger.info("Replacing MoreComments objects")
        submission.comments.replace_more(limit=None)

        logger.info("Fetching all comments")
        all_comments = submission.comments.list()

        if not all_comments:
            logger.info("No comments found")
            summary_text = (
                f"Post Summary:\n{post_summary}\n\nThis post has no comments yet."
            )
            data_to_cache = {
                'summary': summary_text,
                'sort': sort,
                'post_title': submission.title,
                'post_content': submission.selftext,
                'comments': [],
                'comment_count': 0
            }
            lru_cache.put(cache_key, data_to_cache)
            return data_to_cache

        comment_count = len(all_comments)
        logger.info(f"Processing {comment_count} comments for summarization")
        combined_comments = ' '.join([comment.body for comment in all_comments])

        comment_summary_prompt = (
            f"Summarize the following {comment_count} Reddit comments (sorted by {sort}):\n\n{combined_comments}"
        )
        comment_summary_response = gemini_model.generate_content(comment_summary_prompt)
        comment_summary = comment_summary_response.text.strip()

        logger.info(f"Received summary for {comment_count} comments")
        summary_text = (
            f"Post Summary:\n{post_summary}\n\n"
            f"Comment Summary (Extracted {comment_count} total comments, including all nested and 'load more' comments):\n{comment_summary}\n\n"
            "Would you like to know anything else about this post or its comments?"
        )

        data_to_cache = {
            'summary': summary_text,
            'sort': sort,
            'post_title': submission.title,
            'post_content': submission.selftext,
            'comments': [comment.body for comment in all_comments],
            'comment_count': comment_count
        }

        # Cache the computed result
        lru_cache.put(cache_key, data_to_cache)
        return data_to_cache

    except Exception as e:
        logger.error(f"Error in summarize_comments: {str(e)}")
        raise

def extract_sort(text):
    sort_options = ['best', 'top', 'new', 'controversial', 'old', 'qa']
    words = text.lower().split()
    for s in sort_options:
        if s in words:
            return s
    return None

if __name__ == '__main__':
    app.run(debug=True, port=5000)
