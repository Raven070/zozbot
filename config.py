# --- FILE: config.py ---

import os
from dotenv import load_dotenv

load_dotenv() 

## -- Path Configuration --
# Get the absolute path of the directory where the project is located.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define paths relative to the base directory
DATA_DIR = os.path.join(BASE_DIR, 'data')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, 'knowledge_base')
VECTOR_STORE_DIR = os.path.join(BASE_DIR, 'vector_store')

# --- ADDED: Path to the bot's state file for the ON/OFF toggle ---
BOT_STATE_FILE = os.path.join(BASE_DIR, 'bot_state.json')

# Specific asset paths
PHOTO_DIR = os.path.join(ASSETS_DIR, 'photos')
VIDEO_DIR = os.path.join(ASSETS_DIR, 'videos')
AUDIO_DIR = os.path.join(ASSETS_DIR, 'audio')
PDF_DIR = os.path.join(ASSETS_DIR, 'pdf')
# Add this to your config.py file
QUESTIONS_DIR = os.path.join(ASSETS_DIR, 'questions')


DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))


## -- Bot & API Keys --
# Replace with your actual tokens
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GENAI_API_KEY = os.getenv('GENAI_API_KEY')
SCIENTIFIC_GENAI_API_KEY = os.getenv('SCIENTIFIC_GENAI_API_KEY')


## -- Admin Configuration --
ADMIN_IDS = [int(admin_id) for admin_id in os.getenv('ADMIN_IDS', '').split(',') if admin_id]


## -- Bot Persona & Static Text --
TEACHER_NAME = "دكتور ناصر"
SUPPORT_CONTACT = "https://www.facebook.com/DrNasserelbatal"
STANDARD_MESSAGE = (
    "انا مش قادر افهمك يا زوز فانت ممكن تبعتلنا على البيدج وفيه حد هيساعدك "
    "\nhttps://www.facebook.com/messages/t/906478826359384 \n"
    "لو عندك اي سوال تاني غير الي انا مش فاهمه دا اساله😂"
)
