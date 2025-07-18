# Reddit Flask Chatbot

> **Version Notice:** This repository contains both v1.0 (in `main` branch) and v2.0 (in `reddit-chatbot-improvements` branch). See installation instructions below for accessing v2.0.

A Flask application that interacts with Reddit and Gemini Flash to summarize posts and comments. Users can fetch the latest, hot, or top posts from a subreddit and getsummaries.


## Features

- **Fetch Reddit Posts:** Retrieve new, hot, or top posts from any subreddit.

![CleanShot 2025-01-24 at 19 59 35@2x](https://github.com/user-attachments/assets/a37559a5-94bb-4731-bc66-679c7ff7aa8b)

- **Summarize Posts and Comments:** Get AI-generated summaries of posts and their comments.

  ![CleanShot 2025-01-24 at 20 00 36@2x](https://github.com/user-attachments/assets/8061a360-1bc9-4e11-bfc6-8ac4ab8e10c3)

- **Chat Interface:** Interact with the bot to ask questions about Reddit posts.

- Overview function that does a general summary of the entirety of what is being discussed on an entire subreddit

![CleanShot 2025-01-24 at 20 03 51@2x](https://github.com/user-attachments/assets/21e78089-c0a1-4172-99ef-ba1070a21954)

![CleanShot 2025-01-24 at 20 04 48@2x](https://github.com/user-attachments/assets/e84d67e6-0639-4147-9993-8897b3005939)


Fixed a bug, where posts with with more than 200 comments would only extract up to 200 posts. Now the app extracts anad analyzes all comments, including all nested levels and the more comments api. It can handle ALL comments provided by the different Reddit api's.
Switched from OpenAI to Gemini 2.0 Flash - very fast, with a very big context, essential for an app like this that handles huge amounts of text.

## Technologies Used

- **Flask:** Web framework for Python.
- **PRAW:** Python Reddit API Wrapper.
- **Gemini API:** For generating summaries using GPT models.
- **Flask-Session:** Manage user sessions.
- ** Implements LRU cache to avoid unnecessary repeated API calls.

## Setup and Installation

### 1. Clone the Repository

For the latest stable version (v1.0):
```bash
git clone https://github.com/Joaov41/reddit-chatbot.git
cd reddit-chatbot
```

For the improved v2.0 (currently in pull request):
```bash
git clone https://github.com/Joaov41/reddit-chatbot.git
cd reddit-chatbot
git checkout reddit-chatbot-improvements
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Edit `.env` and add your API credentials:
- Reddit Client ID and Secret (get from https://www.reddit.com/prefs/apps)
- Gemini API Key (get from https://makersuite.google.com/app/apikey)

### 4. Run the Application

For the original version:
```bash
python app.py
```

For the improved v2.0 (recommended):
```bash
python app_improved.py
```

## Recent Improvements (v2.0)

> **Note:** v2.0 is currently available in the `reddit-chatbot-improvements` branch (see clone instructions above). Once the pull request is merged, it will be available in the main branch.

The codebase has been significantly improved with:

### Security Enhancements
- API credentials now stored in environment variables (not hardcoded)
- Input validation and sanitization for all user inputs
- Rate limiting to prevent API abuse
- Secure session management

### Performance Optimizations
- Thread-safe LRU cache with TTL (time-to-live) support
- Concurrent API calls for fetching multiple posts
- Optimized memory usage

### Code Quality
- Modular architecture with separate services, models, and utilities
- Type hints for better IDE support
- Comprehensive error handling with specific exceptions
- Clean separation of concerns

### New Features
- Health check endpoint (`/health`)
- Better error messages with proper HTTP status codes
- Enhanced caching strategy
- Configurable rate limits

**Note:** The v2.0 improvements are implemented in `app_improved.py`. The original `app.py` remains unchanged for backward compatibility.

For users upgrading from v1.0, please see the [Migration Guide](MIGRATION_GUIDE.md).
