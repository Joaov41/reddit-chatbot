# Reddit Flask Chatbot

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

```bash
git clone https://github.com/Joaov41/reddit-chatbot.git
cd reddit-chatbot
pip install -r requirements.txt
Fill the config.py file with your Reddit and Gemini API key credentials
Run python.py



