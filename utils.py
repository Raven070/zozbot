# utils.py
import os
import json
import logging
import hashlib
from config import DATA_DIR, KNOWLEDGE_BASE_DIR, BASE_DIR,QUESTIONS_DIR

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Data Loading and Saving Functions ---

def load_lols():
    """Loads the 'gareeda' answers JSON file."""
    gareeda_path = os.path.join(DATA_DIR, 'lol.json')
    with open(gareeda_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def load_answers():
    """Load all answer JSON files"""
    # Load gareeda answers (existing)
    gareeda_path = os.path.join(QUESTIONS_DIR, 'gareda.json')
    with open(gareeda_path, 'r', encoding='utf-8') as file:
        gareeda_answers = json.load(file)
    
    # Load Moaaser answers
    moaaser_path = os.path.join(QUESTIONS_DIR, 'Moaaser.json')
    with open(moaaser_path, 'r', encoding='utf-8') as file:
        moaaser_answers = json.load(file)
    
    # Load Tafwoq answers
    tafwoq_path = os.path.join(QUESTIONS_DIR, 'Tafwoq.json')
    with open(tafwoq_path, 'r', encoding='utf-8') as file:
        tafwoq_answers = json.load(file)
    
    logger.info("Loaded all question answer files")
    return gareeda_answers, moaaser_answers, tafwoq_answers


def load_local_knowledge():
    """Dynamically loads all .md and .json files from the knowledge_base directory."""
    knowledge = ""
    documents_path = os.path.join(KNOWLEDGE_BASE_DIR, 'documents')
    faqs_path = os.path.join(KNOWLEDGE_BASE_DIR, 'faqs')

    # Load Markdown documents
    try:
        if os.path.isdir(documents_path):
            for filename in os.listdir(documents_path):
                if filename.endswith(".md"):
                    file_path = os.path.join(documents_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        knowledge += f.read() + "\n\n"
    except Exception as e:
        logger.error(f"Error loading documents from {documents_path}: {e}")

    # Load JSON FAQs
    try:
        if os.path.isdir(faqs_path):
            for filename in os.listdir(faqs_path):
                if filename.endswith(".json"):
                    file_path = os.path.join(faqs_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        faqs = json.load(f)
                        for item in faqs:
                            if 'question' in item and 'answer' in item:
                                knowledge += f"Q: {item['question']}\nA: {item['answer']}\n\n"
    except Exception as e:
        logger.error(f"Error loading FAQs from {faqs_path}: {e}")

    if not knowledge:
        logger.warning("Local knowledge base is empty.")
    return knowledge

