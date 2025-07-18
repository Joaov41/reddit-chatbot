import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Reddit API Credentials
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'Reddit Hot Posts Extractor')

# Gemini API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Flask Configuration
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
SESSION_TYPE = os.getenv('SESSION_TYPE', 'filesystem')

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Validate required environment variables
required_vars = {
    'REDDIT_CLIENT_ID': REDDIT_CLIENT_ID,
    'REDDIT_CLIENT_SECRET': REDDIT_CLIENT_SECRET,
    'GEMINI_API_KEY': GEMINI_API_KEY
}

missing_vars = [var for var, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")