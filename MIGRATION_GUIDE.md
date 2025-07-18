# Migration Guide: Upgrading to the Improved Reddit Chatbot

This guide will help you migrate from the original `app.py` to the improved version with better security, performance, and code organization.

## Key Improvements

1. **Enhanced Security**
   - API credentials now stored in environment variables
   - Input validation and sanitization
   - Rate limiting to prevent abuse
   - Better session management

2. **Better Code Organization**
   - Separated into modules (services, utils, models)
   - Clear separation of concerns
   - Reusable components

3. **Improved Performance**
   - Thread-safe LRU cache with TTL support
   - Concurrent API calls for bulk operations
   - Optimized response handling

4. **Enhanced Error Handling**
   - Specific exception types
   - Better error messages
   - Proper HTTP status codes

## Migration Steps

### 1. Install New Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in your project root:

```bash
cp .env.example .env
```

Edit `.env` and add your API credentials:

```env
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=Reddit Hot Posts Extractor
GEMINI_API_KEY=your_gemini_api_key
FLASK_SECRET_KEY=your_secret_key_here
```

### 3. Set Up Redis (for Rate Limiting)

The improved version uses Redis for rate limiting. Install Redis:

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Windows:**
Use WSL or Docker:
```bash
docker run -d -p 6379:6379 redis:alpine
```

### 4. Update Your Code

Replace `app.py` with `app_improved.py`:

```bash
mv app.py app_old.py
mv app_improved.py app.py
```

### 5. Update Import Statements

If you have any custom code that imports from the old `app.py`, update the imports:

**Old:**
```python
from app import extract_subreddit_name, LRUCache
```

**New:**
```python
from utils import extract_subreddit_name
from models import LRUCache
```

### 6. API Changes

The improved version maintains backward compatibility for most endpoints, but with enhanced features:

#### `/chat` endpoint:
- Now includes rate limiting (30 requests per minute)
- Better error responses with proper HTTP status codes
- Input sanitization for security

#### `/subreddit_overview` endpoint:
- Now includes rate limiting (5 requests per minute)
- Better concurrent fetching of post details
- Enhanced error handling

### 7. Session Data Structure

The session data structure remains mostly the same, but with additional metadata:

**Old:**
```python
session['posts'] = [{'title': '...', 'score': 100, 'url': '...'}]
```

**New:**
```python
session['posts'] = [{
    'title': '...',
    'score': 100,
    'url': '...',
    'author': 'username',
    'created_utc': 1234567890,
    'num_comments': 50,
    'id': 'post_id'
}]
```

### 8. Running the Application

The application runs the same way:

```bash
python app.py
```

For production, use Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Troubleshooting

### Redis Connection Error
If you get a Redis connection error, ensure Redis is running:
```bash
redis-cli ping
```

You can also run without rate limiting by setting a dummy Redis URL:
```env
REDIS_URL=memory://
```

### Missing Environment Variables
The app will raise a `ValueError` if required environment variables are missing. Check your `.env` file.

### Import Errors
Ensure all new directories (`models/`, `services/`, `utils/`) are in your Python path.

## Rollback Plan

If you need to rollback:

1. Restore the original `app.py`:
   ```bash
   mv app.py app_improved.py
   mv app_old.py app.py
   ```

2. Update `config.py` to remove environment variable loading

3. Reinstall original dependencies

## Additional Features

The improved version includes:

1. **Health Check Endpoint**: `GET /health`
2. **Better Caching**: Thread-safe with TTL support
3. **Type Hints**: Better IDE support and code clarity
4. **Modular Design**: Easier to extend and maintain

## Support

If you encounter issues during migration:

1. Check the logs for detailed error messages
2. Ensure all environment variables are set correctly
3. Verify Redis is running (if using rate limiting)
4. Check that all new dependencies are installed

## Next Steps

After successful migration:

1. Test all functionality thoroughly
2. Monitor performance improvements
3. Customize rate limits as needed
4. Consider adding additional features using the modular structure