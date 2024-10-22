# app.py

from flask import Flask, request, jsonify, render_template, session
import praw
from openai import OpenAI
from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    OPENAI_API_KEY,
)
import logging
from flask_session import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)
logger.info("OpenAI client initialized successfully.")

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
            ai_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an assistant answering questions about multiple Reddit posts and their comments. Use the provided context to answer the user's question."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {user_input}"}
                ],
                max_tokens=300,
                temperature=0.7,
            )
            return jsonify({'response': ai_response.choices[0].message.content.strip()})

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
            
            # Store posts in session
            session['posts'] = posts
            session['subreddit'] = subreddit_name
            
            numbered_posts = [f"{i+1}. {post['title']} (Score: {post['score']})" for i, post in enumerate(posts)]
            response = f"Here are the {num_posts} {post_type} posts from r/{subreddit_name}:\n\n" + "\n".join(numbered_posts)
        
        # Check if the query is about summarizing comments
        elif any(phrase in user_input.lower() for phrase in ["summarize", "summary"]):
            thread_url = extract_url(user_input)
            if not thread_url:
                # Try to find the post by number
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
                
                # Store summarized post data in session
                if 'summarized_posts' not in session:
                    session['summarized_posts'] = {}
                session['summarized_posts'][thread_url] = {
                    'summary': summary,
                    'sort': sort
                }
                session['current_post_url'] = thread_url
                
                response = f"Here's a summary of the post and its comments (comments sorted by {sort}):\n\n{summary}"
            else:
                response = "I'm sorry, but I couldn't find a valid Reddit URL for this post."
        
        # Handle follow-up questions about summarized posts
        elif 'summarized_posts' in session:
            # Check if the question is about a specific post number
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
                context = current_post['summary']
                ai_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an assistant helping answer questions about a Reddit post and its comments. Use the provided context to answer the user's question."},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {user_input}"}
                    ],
                    max_tokens=500,
                    temperature=0.7,
                )
                return jsonify({'response': ai_response.choices[0].message.content.strip()})
            else:
                return jsonify({'response': "I'm sorry, but I don't have any summarized post to refer to. Please ask to summarize a post first."})
        
        else:
            # Use GPT-4o-mini for general queries or to interpret complex requests
            ai_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that provides information about Reddit. You can explain how to use Reddit, discuss popular subreddits, or give general information about Reddit features and etiquette."},
                    {"role": "user", "content": user_input}
                ],
                max_tokens=500,
                temperature=0.7,
            )
            response = ai_response.choices[0].message.content.strip()

        logger.info("Successfully processed the request and generated a response.")
        return jsonify({'response': response})
    except Exception as e:
        logger.exception("An error occurred while processing the request.")
        return jsonify({'response': f"I'm sorry, but I encountered an error: {str(e)}"}), 500

@app.route('/subreddit_overview', methods=['POST'])
def subreddit_overview():
    data = request.get_json()
    subreddit_name = data.get('subreddit')
    num_posts = data.get('num_posts', 20)

    try:
        posts = get_new_posts(subreddit_name, num_posts)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_post = {executor.submit(fetch_post_details, post['url']): post for post in posts}
            for future in as_completed(future_to_post):
                post = future_to_post[future]
                post_details = future.result()
                post.update(post_details)

        session['overview_data'] = posts  # This now contains all comments for each post
        
        combined_content = "\n\n".join([
            f"Title: {post['title']}\n\nContent: {post['content']}\n\nComments: {' '.join(post['comments'])} (Total comments: {len(post['comments'])})"
            for post in posts
        ])
        
        overview = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Provide an overview of the main topics and themes from these {num_posts} posts from r/{subreddit_name}:"},
                {"role": "user", "content": combined_content}
            ],
            max_tokens=500,
            temperature=0.7,
        ).choices[0].message.content.strip()

        return jsonify({'response': f"Overview of r/{subreddit_name} based on {num_posts} posts:\n\n{overview}\n\nYou can now ask questions about these posts and their content."})
    except Exception as e:
        logger.exception("An error occurred while processing the subreddit overview request.")
        return jsonify({'response': f"I'm sorry, but I encountered an error: {str(e)}"}), 500

def fetch_post_details(post_url):
    submission = reddit.submission(url=post_url)
    submission.comments.replace_more(limit=None)  # This will replace all MoreComments objects
    all_comments = submission.comments.list()  # This gets all comments, including nested ones
    return {
        'content': submission.selftext,
        'comments': [comment.body for comment in all_comments]
    }

def extract_subreddit_name(text):
    import re
    match = re.search(r'r/(\w+)', text)
    return match.group(1) if match else None

def extract_number(text):
    import re
    numbers = re.findall(r'\b\d+\b', text)
    return int(numbers[0]) if numbers else None

def extract_url(text):
    # Simple extraction of the first URL in the text
    import re
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
    return urls[0] if urls else None

def get_new_posts(subreddit_name, limit):
    subreddit = reddit.subreddit(subreddit_name)
    return [{"title": post.title, "score": post.score, "url": f"https://www.reddit.com{post.permalink}"} for post in subreddit.new(limit=limit)]

def get_hot_posts(subreddit_name, limit):
    subreddit = reddit.subreddit(subreddit_name)
    return [{"title": post.title, "score": post.score, "url": f"https://www.reddit.com{post.permalink}"} for post in subreddit.hot(limit=limit)]

def get_top_posts(subreddit_name, limit):
    subreddit = reddit.subreddit(subreddit_name)
    return [{"title": post.title, "score": post.score, "url": f"https://www.reddit.com{post.permalink}"} for post in subreddit.top(limit=limit)]

def summarize_comments(thread_url, sort='best'):
    try:
        logger.info(f"Fetching submission: {thread_url}")
        submission = reddit.submission(url=thread_url)
        
        # Summarize the post content
        post_content = f"Title: {submission.title}\n\nContent: {submission.selftext}"
        logger.info("Summarizing post content")
        post_summary = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize the following Reddit post:"},
                {"role": "user", "content": post_content}
            ],
            max_tokens=150,
            temperature=0.7,
        ).choices[0].message.content.strip()
        
        logger.info(f"Setting comment sort to: {sort}")
        submission.comment_sort = sort
        
        logger.info("Replacing MoreComments objects")
        submission.comments.replace_more(limit=None)
        
        logger.info(f"Fetching all comments")
        all_comments = submission.comments.list()
        
        if not all_comments:
            logger.info("No comments found")
            return f"Post Summary:\n{post_summary}\n\nThis post has no comments yet."
        
        comment_count = len(all_comments)
        logger.info(f"Processing {comment_count} comments for summarization")
        combined_comments = ' '.join([comment.body for comment in all_comments])

        logger.info("Sending request to OpenAI for comment summarization")
        comment_summary = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Summarize the following {comment_count} Reddit comments (sorted by {sort}):"},
                {"role": "user", "content": combined_comments}
            ],
            max_tokens=300,
            temperature=0.7,
        ).choices[0].message.content.strip()
        
        logger.info(f"Received summary from OpenAI for {comment_count} comments")
        return f"Post Summary:\n{post_summary}\n\nComment Summary ({comment_count} comments):\n{comment_summary}\n\nWould you like to know anything else about this post or its comments?"
    except Exception as e:
        logger.error(f"Error in summarize_comments: {str(e)}")
        raise

def extract_sort(text):
    sort_options = ['best', 'top', 'new', 'controversial', 'old', 'qa']
    words = text.lower().split()
    for i, word in enumerate(words):
        if word == 'sorted' and i+1 < len(words) and words[i+1] == 'by':
            if i+2 < len(words) and words[i+2] in sort_options:
                return words[i+2]
        if word in sort_options:
            return word
    return None

def extract_depth(text):
    # Look for phrases like "depth 5" or "5 levels deep"
    import re
    depth_match = re.search(r'depth\s+(\d+)|(\d+)\s+levels?\s+deep', text, re.IGNORECASE)
    if depth_match:
        return int(depth_match.group(1) or depth_match.group(2))
    return None

@app.route('/summarize_post', methods=['POST'])
def summarize_post():
    data = request.get_json()
    post_title = data.get('post_title')
    
    if not post_title:
        return jsonify({'response': "Please provide a post title to summarize."})
    
    overview_data = session.get('overview_data', [])
    matching_posts = [post for post in overview_data if post['title'].lower() == post_title.lower()]
    
    if not matching_posts:
        return jsonify({'response': f"No post found with the title '{post_title}'. Please check the title and try again."})
    
    post = matching_posts[0]
    post_content = f"Title: {post['title']}\n\nContent: {post['content']}"
    comments = post['comments']
    
    post_summary = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize the following Reddit post:"},
            {"role": "user", "content": post_content}
        ],
        max_tokens=150,
        temperature=0.7,
    ).choices[0].message.content.strip()
    
    comment_summary = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Summarize the following {len(comments)} Reddit comments:"},
            {"role": "user", "content": ' '.join(comments)}
        ],
        max_tokens=300,
        temperature=0.7,
    ).choices[0].message.content.strip()
    
    summary = f"Post Summary:\n{post_summary}\n\nComment Summary ({len(comments)} comments):\n{comment_summary}"
    return jsonify({'response': summary})

if __name__ == '__main__':
    app.run(debug=True)  # Set to False in production
