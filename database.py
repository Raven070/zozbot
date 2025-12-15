# database.py
import os
import psycopg2
from psycopg2.extras import DictCursor, Json
from werkzeug.security import generate_password_hash, check_password_hash
from config import DATA_DIR, DB_NAME, DB_USER, DB_PASS, DB_HOST, DB_PORT
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    return conn


# ==========================================
# DATABASE SETUP
# ==========================================

def setup_database():
    """
    Initializes the database schema in PostgreSQL and ensures the default admin exists.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            logger.info("Ensuring database tables exist in PostgreSQL...")
            
            # --- Users Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(255) PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_active TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    admin_last_viewed_at TIMESTAMPTZ  
                )
            ''')

            cursor.execute('''
                ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_last_viewed_at TIMESTAMPTZ
            ''')
            
            # Create index for faster queries on last_active
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_last_active 
                ON users(last_active DESC)
            ''')
            
            # --- Interactions Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    user_id VARCHAR(255) NOT NULL,
                    intent VARCHAR(255),
                    response_type VARCHAR(255),
                    confidence REAL,
                    response_time REAL,
                    user_input TEXT,
                    bot_response TEXT,
                    is_corrected BOOLEAN DEFAULT FALSE,
                    corrected_text TEXT,
                    user_feedback INTEGER DEFAULT 0,
                    chat_type VARCHAR(50) DEFAULT 'administrative',
                    image_path VARCHAR(255),
                    cached_question_id INTEGER
                )
            ''')
            
            # Add index for chat_type for performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interactions_chat_type
                ON interactions(chat_type)
            ''')
            
            # Add index for cached_question_id
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_interactions_cached_question
                ON interactions(cached_question_id)
            ''')

            # --- Admins Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # --- Site Issues Table (UPDATED) ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS site_issues (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255), 
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    issue_type VARCHAR(255) NOT NULL,
                    student_code VARCHAR(255) NOT NULL,
                    session_number VARCHAR(255),
                    status VARCHAR(50) NOT NULL DEFAULT 'open'
                )
            ''')

            # Safely add the user_id column if it doesn't exist in the old table
            cursor.execute('''
                ALTER TABLE site_issues ADD COLUMN IF NOT EXISTS user_id VARCHAR(255)
            ''')

            # This will now succeed because the column is guaranteed to exist
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_site_issues_user_id
                ON site_issues(user_id)
            ''')
            
            # --- Cached Scientific Questions Table (NEW) ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cached_scientific_questions (
                    id SERIAL PRIMARY KEY,
                    question_text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    embedding JSONB,
                    image_hash VARCHAR(64),
                    times_used INTEGER DEFAULT 1,
                    last_used TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    is_corrected BOOLEAN DEFAULT FALSE,
                    corrected_at TIMESTAMPTZ,
                    correction_source VARCHAR(50),
                    metadata JSONB
                )
            ''')
            
            # Create indexes for cached questions
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cached_questions_normalized 
                ON cached_scientific_questions(normalized_text)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cached_questions_hash 
                ON cached_scientific_questions(image_hash)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cached_questions_last_used 
                ON cached_scientific_questions(last_used DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cached_questions_corrected 
                ON cached_scientific_questions(is_corrected)
            ''')

            # --- Create Default Admin ---
            initial_email = 'zoznasseradmin@hoss.com'
            cursor.execute("SELECT email FROM admins WHERE email = %s", (initial_email,))
            admin_exists = cursor.fetchone()
            
            if not admin_exists:
                logger.info(f"Default admin '{initial_email}' not found. Creating it now...")
                initial_password = '12345'
                hashed_password = generate_password_hash(initial_password)
                cursor.execute(
                    "INSERT INTO admins (email, password_hash) VALUES (%s, %s)",
                    (initial_email, hashed_password)
                )
                logger.info("Default admin created successfully.")
            else:
                logger.info(f"Default admin '{initial_email}' already exists.")
            
        conn.commit()
        logger.info("PostgreSQL database setup complete.")
    except Exception as e:
        logger.error(f"Error during database setup: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()


# ==========================================
# USER MANAGEMENT FUNCTIONS
# ==========================================


def update_admin_last_view(user_id: str):
    """Updates the admin_last_viewed_at timestamp for a user to NOW()."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users 
                SET admin_last_viewed_at = CURRENT_TIMESTAMP 
                WHERE user_id = %s
                """,
                (user_id,)
            )
            conn.commit()
    finally:
        conn.close()


def register_user(user_id: str, username: str = None, first_name: str = None):
    """Registers or updates a user in the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_active)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_active = CURRENT_TIMESTAMP
                """,
                (user_id, username, first_name)
            )
            conn.commit()
    finally:
        conn.close()


def get_all_active_user_ids(active_days: int = 90):
    """Gets all user IDs who were active within the specified days."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id FROM users 
                WHERE last_active >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                ORDER BY user_id
                """,
                (active_days,)
            )
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_user_ids_batch(offset: int, limit: int = 100):
    """Gets a batch of user IDs for efficient broadcasting."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id FROM users 
                WHERE last_active >= CURRENT_TIMESTAMP - INTERVAL '90 days'
                ORDER BY user_id
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_total_active_users(active_days: int = 90):
    """Returns count of active users."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM users 
                WHERE last_active >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                """,
                (active_days,)
            )
            return cursor.fetchone()[0]
    finally:
        conn.close()


# ==========================================
# ADMIN MANAGEMENT FUNCTIONS
# ==========================================

def add_admin(email, password):
    """Adds a new admin to the database with a hashed password."""
    if not email or not password:
        return False, "Email and password cannot be empty."
    
    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO admins (email, password_hash) VALUES (%s, %s)",
                (email, hashed_password)
            )
            conn.commit()
            return True, f"Admin '{email}' added successfully."
    except psycopg2.IntegrityError:
        conn.rollback()
        return False, f"Admin with email '{email}' already exists."
    finally:
        conn.close()


def delete_admin(email):
    """Deletes an admin from the database by their email."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM admins WHERE email = %s", (email,))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_admin_by_email(email):
    """Retrieves an admin's data by their email."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_admin_by_id(admin_id):
    """Retrieves an admin's data by their ID."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM admins WHERE id = %s", (admin_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def verify_admin_password(email, password):
    """Verifies an admin's password against the stored hash."""
    admin = get_admin_by_email(email)
    if admin and check_password_hash(admin['password_hash'], password):
        return True
    return False


def get_all_admins():
    """Retrieves a list of all administrators."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT id, email, created_at FROM admins ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


# ==========================================
# SITE ISSUE MANAGEMENT FUNCTIONS
# ==========================================

# --- This function is correct ---
def create_site_issue(user_id: str, issue_type: str, student_code: str, session_number: str = None):
    """Logs a new site issue to the database, including the user_id."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO site_issues (user_id, issue_type, student_code, session_number)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, issue_type, student_code, session_number)
            )
            conn.commit()
    finally:
        conn.close()


def get_open_site_issues():
    """Retrieves all site issues with an 'open' status."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # SELECT * will now automatically include the new user_id column
            cursor.execute("SELECT * FROM site_issues WHERE status = 'open' ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def resolve_site_issue(issue_id: int):
    """Marks a site issue as 'resolved' instead of deleting it."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE site_issues SET status = 'resolved' WHERE id = %s AND status = 'open'",
                (issue_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()


# ==========================================
# INTERACTION LOGGING FUNCTIONS
# ==========================================

def log_interaction(
    user_id, 
    user_input, 
    bot_response, 
    intent, 
    response_type, 
    confidence, 
    response_time,
    image_path: str = None
):
    """Logs the interaction and returns the new interaction's ID from PostgreSQL."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO interactions (
                    user_id, user_input, bot_response, intent, 
                    response_type, confidence, response_time, image_path
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    user_id, user_input, bot_response, intent, 
                    response_type, confidence, response_time, image_path
                )
            )
            interaction_id = cursor.fetchone()[0]
            conn.commit()
            return interaction_id
    finally:
        conn.close()

def log_scientific_interaction(
    user_id: str, 
    user_input: str, 
    bot_response: str, 
    image_path: str = None, 
    response_time: float = 0.0,
    cached_question_id: int = None
) -> int:

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO interactions 
                (user_id, user_input, bot_response, chat_type, image_path, 
                 intent, response_type, confidence, response_time, timestamp, cached_question_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                RETURNING id
            """, (
                user_id, 
                user_input, 
                bot_response, 
                'scientific',
                image_path,
                'scientific_response',
                'scientific',
                1.0,
                response_time,
                cached_question_id
            ))
            
            interaction_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Logged scientific interaction {interaction_id} for user {user_id}")
            return interaction_id
            
    except Exception as e:
        logger.error(f"Error logging scientific interaction: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


def update_interaction_feedback(interaction_id: int, feedback: int):
    """Updates the feedback for a given interaction."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE interactions SET user_feedback = %s WHERE id = %s", (feedback, interaction_id))
            conn.commit()
    finally:
        conn.close()


def update_interaction_correction(interaction_id: int, corrected_text: str):
    """Updates an interaction with corrected text and resets its feedback status."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE interactions 
                SET is_corrected = TRUE, 
                    corrected_text = %s, 
                    user_feedback = 0 
                WHERE id = %s
                """,
                (corrected_text, interaction_id)
            )
            conn.commit()
    finally:
        conn.close()


def link_correction_to_cache(interaction_id: int, cached_question_id: int):
    """Link a corrected interaction to its cached question."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE interactions 
                SET cached_question_id = %s 
                WHERE id = %s
            ''', (cached_question_id, interaction_id))
            
            conn.commit()
    except Exception as e:
        logger.error(f"Error linking correction to cache: {e}")
        conn.rollback()
    finally:
        conn.close()


# ==========================================
# CONVERSATION RETRIEVAL FUNCTIONS
# ==========================================


def get_user_chat_history(user_id: str):
    """Retrieves the full chat history for a specific user."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM interactions WHERE user_id = %s AND chat_type = 'administrative' ORDER BY timestamp ASC", (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_conversation_users():
    """Gets all unique users, their message count, last message time, and a count of their new messages."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = """
                SELECT
                    i.user_id,
                    COUNT(i.id) as message_count,
                    MAX(i.timestamp) as last_message_ts,
                    SUM(CASE WHEN i.user_feedback = -1 THEN 1 ELSE 0 END) as negative_feedback_count,
                    COUNT(i.id) FILTER (WHERE i.timestamp > u.admin_last_viewed_at) as new_message_count
                FROM
                    interactions i
                LEFT JOIN users u ON i.user_id = u.user_id
                WHERE i.chat_type = 'administrative'
                GROUP BY
                    i.user_id
                ORDER BY
                    last_message_ts DESC
            """
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()



def get_user_scientific_chat_history(user_id: str):
    """Get the scientific chat history for a specific user."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT id, user_input, bot_response, timestamp, user_feedback, 
                       is_corrected, corrected_text, image_path, cached_question_id
                FROM interactions
                WHERE user_id = %s AND chat_type = 'scientific'
                ORDER BY timestamp ASC
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting scientific chat history: {e}")
        return []
    finally:
        if conn:
            conn.close()

            

def get_scientific_conversation_users():
    """Get all users who have had scientific conversations, ordered by last message."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    i.user_id,
                    COUNT(i.id) as message_count,
                    MAX(i.timestamp) as last_message_ts,
                    SUM(CASE WHEN i.user_feedback = -1 AND (is_corrected = FALSE OR is_corrected IS NULL) THEN 1 ELSE 0 END) as negative_feedback_count,
                    COUNT(i.id) FILTER (WHERE i.timestamp > u.admin_last_viewed_at) as new_message_count
                FROM interactions i
                LEFT JOIN users u ON i.user_id = u.user_id
                WHERE i.chat_type = 'scientific'
                GROUP BY i.user_id
                ORDER BY last_message_ts DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting scientific conversation users: {e}")
        return []
    finally:
        if conn:
            conn.close()





# ==========================================
# FEEDBACK MANAGEMENT FUNCTIONS
# ==========================================

def get_negative_feedback_interactions():
    """Retrieves all interactions with negative feedback."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT id, user_id, user_input, bot_response, timestamp FROM interactions WHERE user_feedback = -1 ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ==========================================
# ANALYTICS FUNCTIONS
# ==========================================

def get_analytics_summary():
    """Retrieves a summary of analytics data."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM interactions")
            total_queries = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as successful FROM interactions WHERE confidence > 0.6")
            successful_queries = cursor.fetchone()['successful']
            
            success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
            
            cursor.execute("SELECT AVG(response_time) as avg_time FROM interactions")
            avg_response_time = cursor.fetchone()['avg_time'] or 0
            
            cursor.execute("SELECT COUNT(*) as fallback_count FROM interactions WHERE response_type LIKE '%%fallback%%'")
            fallback_count = cursor.fetchone()['fallback_count']
            
            cursor.execute("SELECT intent, COUNT(*) as count FROM interactions WHERE intent IS NOT NULL GROUP BY intent ORDER BY count DESC LIMIT 5")
            top_intents = [dict(row) for row in cursor.fetchall()]

            return {
                'total_queries': total_queries,
                'success_rate': success_rate,
                'avg_response_time': avg_response_time * 1000,
                'fallback_count': fallback_count,
                'top_intents': top_intents
            }
    finally:
        conn.close()


# ==========================================
# CACHED QUESTIONS FUNCTIONS (NEW)
# ==========================================

def cache_scientific_question(
    question_text: str,
    normalized_text: str,
    answer_text: str,
    embedding: list,
    image_hash: str = None,
    metadata: dict = None
) -> int:
    """Cache a new scientific question-answer pair."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO cached_scientific_questions 
                (question_text, normalized_text, answer_text, embedding, image_hash, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                question_text,
                normalized_text,
                answer_text,
                Json(embedding),
                image_hash,
                Json(metadata) if metadata else None
            ))
            
            cached_id = cursor.fetchone()[0]
            conn.commit()
            return cached_id
    except Exception as e:
        logger.error(f"Error caching question: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_cached_question_by_image_hash(image_hash: str) -> dict:
    """Get cached question by image hash."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT * FROM cached_scientific_questions 
                WHERE image_hash = %s 
                ORDER BY last_used DESC 
                LIMIT 1
            ''', (image_hash,))
            
            row = cursor.fetchone()
            if row:
                # Update usage statistics
                cursor.execute('''
                    UPDATE cached_scientific_questions 
                    SET times_used = times_used + 1, last_used = CURRENT_TIMESTAMP 
                    WHERE id = %s
                ''', (row['id'],))
                conn.commit()
                return dict(row)
            return None
    finally:
        conn.close()


def get_cached_question_by_text(normalized_text: str) -> dict:
    """Get cached question by normalized text."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT * FROM cached_scientific_questions 
                WHERE normalized_text = %s 
                ORDER BY last_used DESC 
                LIMIT 1
            ''', (normalized_text,))
            
            row = cursor.fetchone()
            if row:
                # Update usage statistics
                cursor.execute('''
                    UPDATE cached_scientific_questions 
                    SET times_used = times_used + 1, last_used = CURRENT_TIMESTAMP 
                    WHERE id = %s
                ''', (row['id'],))
                conn.commit()
                return dict(row)
            return None
    finally:
        conn.close()


def get_recent_cached_questions(limit: int = 100) -> list:
    """Get recent cached questions for similarity comparison."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT id, question_text, normalized_text, answer_text, 
                       embedding, times_used, is_corrected
                FROM cached_scientific_questions 
                ORDER BY last_used DESC 
                LIMIT %s
            ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def update_cached_question_answer(
    cached_question_id: int,
    new_answer: str,
    correction_source: str = 'manual'
) -> bool:
    """Update a cached question's answer."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE cached_scientific_questions 
                SET answer_text = %s, 
                    is_corrected = TRUE, 
                    corrected_at = CURRENT_TIMESTAMP,
                    correction_source = %s
                WHERE id = %s
            ''', (new_answer, correction_source, cached_question_id))
            
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_cache_statistics() -> dict:
    """Get statistics about the question cache."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Total cached questions
            cursor.execute('SELECT COUNT(*) as total FROM cached_scientific_questions')
            total = cursor.fetchone()['total']
            
            # Total cache hits
            cursor.execute('SELECT SUM(times_used) as hits FROM cached_scientific_questions')
            hits_result = cursor.fetchone()
            total_hits = hits_result['hits'] if hits_result['hits'] else 0
            
            # Corrected questions
            cursor.execute('SELECT COUNT(*) as corrected FROM cached_scientific_questions WHERE is_corrected = TRUE')
            corrected = cursor.fetchone()['corrected']
            
            # Most used questions
            cursor.execute('''
                SELECT question_text, times_used 
                FROM cached_scientific_questions 
                ORDER BY times_used DESC 
                LIMIT 5
            ''')
            top_questions = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_cached': total,
                'total_hits': total_hits,
                'corrected_count': corrected,
                'top_questions': top_questions,
                'hit_rate': (total_hits / total) if total > 0 else 0
            }
    finally:
        conn.close()

def delete_interaction_by_id(interaction_id: int) -> bool:
    """Deletes a single interaction by its ID."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM interactions WHERE id = %s",
                (interaction_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting interaction {interaction_id}: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
# CORRECTIONS HUB FUNCTIONS (NEW)
# ==========================================

def get_all_corrected_interactions(
    search_query: str = None,
    chapter: str = None,
    lesson: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 100,
    offset: int = 0
) -> list:
    """
    Get all corrected scientific interactions with advanced filtering.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            query = '''
                SELECT 
                    id, user_id, user_input, bot_response, corrected_text,
                    timestamp, image_path, is_corrected, cached_question_id
                FROM interactions 
                WHERE chat_type = 'scientific' 
                AND is_corrected = TRUE
            '''
            
            params = []
            
            if search_query:
                query += ' AND (user_input ILIKE %s OR corrected_text ILIKE %s)'
                search_pattern = f'%{search_query}%'
                params.extend([search_pattern, search_pattern])
            
            if date_from:
                query += ' AND timestamp >= %s'
                params.append(date_from)
            
            if date_to:
                query += ' AND timestamp <= %s'
                params.append(date_to)
            
            query += ' ORDER BY timestamp DESC LIMIT %s OFFSET %s'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def get_corrected_count(search_query: str = None) -> int:
    """Get total count of corrected interactions for pagination."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = '''
                SELECT COUNT(*) 
                FROM interactions 
                WHERE chat_type = 'scientific' 
                AND is_corrected = TRUE
            '''
            
            params = []
            
            if search_query:
                query += ' AND (user_input ILIKE %s OR corrected_text ILIKE %s)'
                search_pattern = f'%{search_query}%'
                params.extend([search_pattern, search_pattern])
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    finally:
        conn.close()


def get_similar_uncorrected_questions(question_text: str, limit: int = 10) -> list:
    """
    Find similar uncorrected questions for bulk correction.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Extract key terms from question
            words = question_text.lower().split()
            key_words = [w for w in words if len(w) > 3][:5]
            
            if not key_words:
                return []
            
            # Build ILIKE query for each word
            conditions = ' AND '.join(['user_input ILIKE %s'] * len(key_words))
            patterns = [f'%{word}%' for word in key_words]
            
            query = f'''
                SELECT id, user_id, user_input, bot_response, timestamp, image_path
                FROM interactions 
                WHERE chat_type = 'scientific' 
                AND (is_corrected = FALSE OR is_corrected IS NULL)
                AND user_feedback != 1
                AND {conditions}
                ORDER BY timestamp DESC
                LIMIT %s
            '''
            
            params = patterns + [limit]
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def bulk_apply_correction(interaction_ids: list, corrected_text: str) -> int:
    """Apply the same correction to multiple interactions."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE interactions 
                SET corrected_text = %s, 
                    is_corrected = TRUE,
                    user_feedback = 0
                WHERE id = ANY(%s)
            ''', (corrected_text, interaction_ids))
            
            conn.commit()
            return cursor.rowcount
    finally:
        conn.close()


def get_correction_statistics() -> dict:
    """Get statistics about corrections."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Total scientific interactions
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM interactions 
                WHERE chat_type = 'scientific'
            ''')
            total = cursor.fetchone()['total']
            
            # Corrected interactions
            cursor.execute('''
                SELECT COUNT(*) as corrected 
                FROM interactions 
                WHERE chat_type = 'scientific' AND is_corrected = TRUE
            ''')
            corrected = cursor.fetchone()['corrected']
            
            # Pending corrections (negative feedback, not corrected)
            cursor.execute('''
                SELECT COUNT(*) as pending 
                FROM interactions 
                WHERE chat_type = 'scientific' 
                AND user_feedback = -1 
                AND (is_corrected = FALSE OR is_corrected IS NULL)
            ''')
            pending = cursor.fetchone()['pending']
            
            # Corrections by date (last 7 days)
            cursor.execute('''
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM interactions 
                WHERE chat_type = 'scientific' 
                AND is_corrected = TRUE
                AND timestamp >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            ''')
            recent_corrections = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_scientific': total,
                'corrected_count': corrected,
                'pending_count': pending,
                'correction_rate': (corrected / total * 100) if total > 0 else 0,
                'recent_corrections': recent_corrections
            }
    finally:
        conn.close()
        


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_interaction_by_id(interaction_id: int) -> dict:
    """Get a specific interaction by ID."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT * FROM interactions WHERE id = %s
            ''', (interaction_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_cached_question_by_id(cached_id: int) -> dict:
    """Get a specific cached question by ID."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT * FROM cached_scientific_questions WHERE id = %s
            ''', (cached_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def delete_old_cache_entries(days: int = 90, min_usage: int = 3) -> int:
    """Delete old cache entries that haven't been used much."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                DELETE FROM cached_scientific_questions 
                WHERE last_used < CURRENT_TIMESTAMP - INTERVAL '%s days'
                AND times_used < %s
                RETURNING id
            ''', (days, min_usage))
            
            deleted_ids = cursor.fetchall()
            conn.commit()
            return len(deleted_ids)
    finally:
        conn.close()


def get_all_cached_questions(limit: int = 1000, offset: int = 0) -> list:
    """Get all cached questions with pagination."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT 
                    id, question_text, answer_text, times_used, 
                    is_corrected, created_at, last_used, correction_source
                FROM cached_scientific_questions 
                ORDER BY last_used DESC
                LIMIT %s OFFSET %s
            ''', (limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def search_cached_questions(search_query: str, limit: int = 50) -> list:
    """Search cached questions by text."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            search_pattern = f'%{search_query}%'
            cursor.execute('''
                SELECT 
                    id, question_text, answer_text, times_used, 
                    is_corrected, created_at, last_used
                FROM cached_scientific_questions 
                WHERE question_text ILIKE %s OR answer_text ILIKE %s
                ORDER BY times_used DESC
                LIMIT %s
            ''', (search_pattern, search_pattern, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def get_interactions_by_cached_id(cached_id: int) -> list:
    """Get all interactions linked to a specific cached question."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT 
                    id, user_id, user_input, bot_response, 
                    corrected_text, is_corrected, timestamp
                FROM interactions 
                WHERE cached_question_id = %s
                ORDER BY timestamp DESC
            ''', (cached_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def get_unapproved_interactions(limit: int = 50) -> list:
    """Get scientific interactions that haven't been approved or corrected yet."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('''
                SELECT 
                    id, user_id, user_input, bot_response, 
                    timestamp, image_path, user_feedback
                FROM interactions 
                WHERE chat_type = 'scientific'
                AND (is_corrected = FALSE OR is_corrected IS NULL)
                AND cached_question_id IS NULL
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_interaction_as_approved(interaction_id: int) -> bool:
    """Mark an interaction as approved (answer is correct)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE interactions 
                SET user_feedback = 1,
                    corrected_text = bot_response,
                    is_corrected = TRUE
                WHERE id = %s
            ''', (interaction_id,))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_statistics_summary() -> dict:
    """Get comprehensive statistics summary."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            stats = {}
            
            # Total users
            cursor.execute('SELECT COUNT(*) as total FROM users')
            stats['total_users'] = cursor.fetchone()['total']
            
            # Active users (last 30 days)
            cursor.execute('''
                SELECT COUNT(*) as active 
                FROM users 
                WHERE last_active >= CURRENT_TIMESTAMP - INTERVAL '30 days'
            ''')
            stats['active_users_30d'] = cursor.fetchone()['active']
            
            # Total interactions
            cursor.execute('SELECT COUNT(*) as total FROM interactions')
            stats['total_interactions'] = cursor.fetchone()['total']
            
            # Scientific interactions
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM interactions 
                WHERE chat_type = 'scientific'
            ''')
            stats['scientific_interactions'] = cursor.fetchone()['total']
            
            # Administrative interactions
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM interactions 
                WHERE chat_type = 'administrative'
            ''')
            stats['administrative_interactions'] = cursor.fetchone()['total']
            
            # Cached questions
            cursor.execute('SELECT COUNT(*) as total FROM cached_scientific_questions')
            stats['cached_questions'] = cursor.fetchone()['total']
            
            # Approved cached questions
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM cached_scientific_questions 
                WHERE is_corrected = TRUE
            ''')
            stats['approved_cached'] = cursor.fetchone()['total']
            
            # Total cache hits
            cursor.execute('''
                SELECT SUM(times_used) as total 
                FROM cached_scientific_questions
            ''')
            result = cursor.fetchone()
            stats['total_cache_hits'] = result['total'] if result['total'] else 0
            
            # Corrected interactions
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM interactions 
                WHERE chat_type = 'scientific' AND is_corrected = TRUE
            ''')
            stats['corrected_interactions'] = cursor.fetchone()['total']
            
            # Pending corrections
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM interactions 
                WHERE chat_type = 'scientific' 
                AND user_feedback = -1 
                AND (is_corrected = FALSE OR is_corrected IS NULL)
            ''')
            stats['pending_corrections'] = cursor.fetchone()['total']
            
            # Open site issues
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM site_issues 
                WHERE status = 'open'
            ''')
            stats['open_issues'] = cursor.fetchone()['total']
            
            # Calculate cache efficiency
            if stats['cached_questions'] > 0:
                stats['cache_efficiency'] = (
                    stats['total_cache_hits'] / stats['cached_questions']
                )
            else:
                stats['cache_efficiency'] = 0
            
            return stats
    finally:
        conn.close()


# ==========================================
# DATABASE MAINTENANCE
# ==========================================

def vacuum_database():
    """Run VACUUM on the database to reclaim space and optimize."""
    conn = get_db_connection()
    try:
        # VACUUM cannot run inside a transaction block
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cursor:
            cursor.execute('VACUUM ANALYZE')
            logger.info("Database VACUUM completed successfully")
    except Exception as e:
        logger.error(f"Error running VACUUM: {e}")
    finally:
        conn.close()


def get_database_size() -> dict:
    """Get database size information."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Get database size
            cursor.execute('''
                SELECT pg_size_pretty(pg_database_size(current_database())) as size
            ''')
            db_size = cursor.fetchone()['size']
            
            # Get table sizes
            cursor.execute('''
                SELECT 
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            ''')
            table_sizes = [dict(row) for row in cursor.fetchall()]
            
            return {
                'database_size': db_size,
                'table_sizes': table_sizes
            }
    finally:
        conn.close()


# ==========================================
# INITIALIZATION
# ==========================================

if __name__ == '__main__':
    """Run database setup when executed directly."""
    print("Setting up database...")
    setup_database()
    print("Database setup complete!")
    
    # Print statistics
    stats = get_statistics_summary()
    print("\nDatabase Statistics:")
    print(f"  Total Users: {stats['total_users']}")
    print(f"  Active Users (30d): {stats['active_users_30d']}")
    print(f"  Total Interactions: {stats['total_interactions']}")
    print(f"  Scientific Interactions: {stats['scientific_interactions']}")
    print(f"  Cached Questions: {stats['cached_questions']}")
    print(f"  Approved Cache: {stats['approved_cached']}")
    print(f"  Total Cache Hits: {stats['total_cache_hits']}")
    print(f"  Cache Efficiency: {stats['cache_efficiency']:.2f}x")