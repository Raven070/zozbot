#!/usr/bin/env python3
# admin_dashboard.py - Complete Admin Dashboard for AI-Agent Management
# FULLY UPDATED WITH CACHE CORRECTION FIXES
# INCLUDES SITE_ISSUES MESSAGING FEATURES

import os
import json
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from collections import defaultdict
from redis_client import redis_conn, BOT_STATE_KEY
import uuid
import database
import utils
import broadcaster
from config import (
    DATA_DIR, KNOWLEDGE_BASE_DIR, VECTOR_STORE_DIR,
    BOT_STATE_FILE, ASSETS_DIR, BASE_DIR
)
import knowledge_processor
from enhanced_question_deduplication import deduplicator

# --- ADJUSTED APP INITIALIZATION ---
# Define the path to your static folder by finding the 'assets' or 'static' directory
assets_dir_path = os.path.join(BASE_DIR, 'assets')
static_dir_path = os.path.join(BASE_DIR, 'static')
static_folder_to_use = assets_dir_path if os.path.exists(assets_dir_path) else static_dir_path

# Initialize Flask app and explicitly tell it where the static folder is
app = Flask(
    __name__, 
    template_folder='templates', 
    static_folder=static_folder_to_use, 
    static_url_path=f'/{os.path.basename(static_folder_to_use)}'
)
app.secret_key = 'your-super-secret-key-change-this-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# --- Login Manager Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"


class Admin(UserMixin):
    """Admin user class for Flask-Login."""
    def __init__(self, id, email):
        self.id = id
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    """Load user from the database by user ID."""
    admin_data = database.get_admin_by_id(int(user_id))
    if admin_data:
        return Admin(id=admin_data['id'], email=admin_data['email'])
    return None


# --- App Initialization ---
# Ensure all required directories exist on startup.
os.makedirs(os.path.join(KNOWLEDGE_BASE_DIR, 'documents'), exist_ok=True)
os.makedirs(os.path.join(KNOWLEDGE_BASE_DIR, 'faqs'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'scientific_kb', 'faqs'), exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Set up the database within the application context.
with app.app_context():
    database.setup_database()


# --- HELPER FUNCTIONS ---

def get_knowledge_files(view='administrative'):
    """Get all knowledge base files (markdown and JSON) with their details for a specific view."""
    files = {'documents': [], 'faqs': []}
    
    if view == 'scientific':
        scientific_base = os.path.join(BASE_DIR, 'scientific_kb')
        docs_base = scientific_base
        faqs_base = os.path.join(scientific_base, 'faqs')
    else:  # administrative
        docs_base = os.path.join(KNOWLEDGE_BASE_DIR, 'documents')
        faqs_base = os.path.join(KNOWLEDGE_BASE_DIR, 'faqs')

    # Get markdown documents
    if os.path.exists(docs_base):
        for item in os.listdir(docs_base):
            item_path = os.path.join(docs_base, item)
            if view == 'scientific' and os.path.isdir(item_path) and item != 'faqs':
                for doc_filename in os.listdir(item_path):
                    if doc_filename.endswith('.md'):
                        filepath = os.path.join(item_path, doc_filename)
                        display_name = os.path.join(item, doc_filename).replace('\\', '/')
                        files['documents'].append({
                            'name': display_name, 
                            'path': filepath, 
                            'size': os.path.getsize(filepath),
                            'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                        })
            elif view == 'administrative' and os.path.isfile(item_path) and item.endswith('.md'):
                files['documents'].append({
                    'name': item, 
                    'path': item_path, 
                    'size': os.path.getsize(item_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                })

    # Get FAQ JSON files
    if os.path.exists(faqs_base):
        for item in os.listdir(faqs_base):
            item_path = os.path.join(faqs_base, item)
            if os.path.isdir(item_path):
                for sub_item in os.listdir(item_path):
                    if sub_item.endswith('.json'):
                        filepath = os.path.join(item_path, sub_item)
                        filename = os.path.join(item, sub_item).replace('\\', '/')
                        files['faqs'].append({
                            'name': filename, 
                            'path': filepath, 
                            'size': os.path.getsize(filepath),
                            'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                        })
            elif os.path.isfile(item_path) and item.endswith('.json'):
                files['faqs'].append({
                    'name': item, 
                    'path': item_path, 
                    'size': os.path.getsize(item_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                })
    
    return files


def get_base_path(view, file_type):
    """Helper to determine the correct base directory based on view and file type."""
    if view == 'scientific':
        base = os.path.join(BASE_DIR, 'scientific_kb')
        if file_type == 'document':
            return base
        elif file_type == 'faq':
            return os.path.join(base, 'faqs')
    else:  # administrative
        base = KNOWLEDGE_BASE_DIR
        if file_type == 'document':
            return os.path.join(base, 'documents')
        elif file_type == 'faq':
            return os.path.join(base, 'faqs')
    
    raise ValueError("Invalid file type or view specified")


# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles admin login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if database.verify_admin_password(email, password):
            admin_data = database.get_admin_by_email(email)
            admin = Admin(id=admin_data['id'], email=admin_data['email'])
            login_user(admin)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Handles admin logout."""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ==========================================
# MAIN PAGE ROUTES
# ==========================================

@app.route('/')
@login_required
def dashboard():
    """Main dashboard view."""
    state = redis_conn.get(BOT_STATE_KEY)
    bot_enabled = True if state is None else state == 'true'

    analytics = database.get_analytics_summary()
    knowledge_files = get_knowledge_files()
    
    total_users = database.get_total_active_users()
    users_30_days = database.get_total_active_users(30)
    users_7_days = database.get_total_active_users(7)
    
    return render_template(
        'dashboard.html', 
        bot_enabled=bot_enabled, 
        analytics=analytics, 
        knowledge_files=knowledge_files,
        total_users=total_users,
        users_30_days=users_30_days,
        users_7_days=users_7_days
    )


@app.route('/admin-management', methods=['GET', 'POST'])
@login_required
def admin_management():
    """Page for adding and deleting admin accounts."""
    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form.get('email')
        
        if action == 'add':
            password = request.form.get('password')
            if not email or not password:
                flash('Email and password are required to add an admin.', 'danger')
            else:
                success, message = database.add_admin(email, password)
                flash(message, 'success' if success else 'danger')
        
        elif action == 'delete':
            if not email:
                flash('Email is required to delete an admin.', 'danger')
            elif email == current_user.email:
                flash('You cannot delete your own account.', 'danger')
            else:
                if database.delete_admin(email):
                    flash(f'Admin {email} has been deleted.', 'success')
                else:
                    flash(f'Admin {email} not found.', 'danger')
        return redirect(url_for('admin_management'))

    admins = database.get_all_admins()
    return render_template('admin_management.html', admins=admins)


@app.route('/site-issues')
@login_required
def site_issues():
    """Site Issues management page with categorized view, now reading from the database."""
    all_issues = database.get_open_site_issues()
    selected_category = request.args.get('view', None)

    categorized_issues = defaultdict(list)
    for issue in all_issues:
        categorized_issues[issue['issue_type']].append(issue)

    if selected_category and selected_category in categorized_issues:
        issues_to_display = categorized_issues[selected_category]
        return render_template(
            'site_issues.html',
            issues=issues_to_display,
            selected_category=selected_category
        )
    else:
        category_counts = {
            'reopen_session': len(categorized_issues.get('reopen_session', [])),
            'extend_deadline': len(categorized_issues.get('extend_deadline', [])),
            'remove_block': len(categorized_issues.get('remove_block', []))
        }
        total_count = len(all_issues)
        return render_template(
            'site_issues.html',
            category_counts=category_counts,
            total_count=total_count,
            selected_category=None
        )


@app.route('/broadcast')
@login_required
def broadcast_page():
    """Broadcast center page with active user count."""
    total_users = database.get_total_active_users()
    return render_template('broadcast.html', total_users=total_users)


@app.route('/content-management')
@login_required
def content_management():
    """Content Management System page with Administrative/Scientific views."""
    view = request.args.get('view', 'administrative')
    files = get_knowledge_files(view)
    return render_template('content_management.html', files=files, view=view)


@app.route('/feedback')
@login_required
def feedback():
    """Feedback management page with partitioned access."""
    selected_part = request.args.get('part', default=None, type=int)
    
    all_feedback_items = database.get_negative_feedback_interactions()
    total_count = len(all_feedback_items)
    
    part_counts = [0] * 10
    for item in all_feedback_items:
        part_index = item['id'] % 10
        part_counts[part_index] += 1
        
    items_to_display = []
    if selected_part is not None and 1 <= selected_part <= 10:
        part_index = selected_part - 1
        items_to_display = [
            item for item in all_feedback_items if item['id'] % 10 == part_index
        ]

    return render_template(
        'feedback.html', 
        feedback_items=items_to_display,
        part_counts=part_counts,
        total_count=total_count,
        selected_part=selected_part
    )


@app.route('/analytics')
@login_required
def analytics():
    """Analytics dashboard."""
    analytics_data = database.get_analytics_summary()
    return render_template('analytics.html', analytics=analytics_data)


@app.route('/conversations')
@login_required
def conversations():
    """Conversations management page - now with chat type selection."""
    chat_type = request.args.get('chat_type', default='administrative', type=str)
    selected_part = request.args.get('part', default=None, type=int)
    
    if chat_type not in ['administrative', 'scientific']:
        chat_type = 'administrative'
    
    if chat_type == 'administrative':
        all_users = database.get_conversation_users()
    else:
        all_users = database.get_scientific_conversation_users()
    
    total_count = len(all_users)
    
    # FIX: Helper function to robustly get the partition index for numeric or string user_ids
    def get_partition_index(user_id):
        user_id_str = str(user_id)
        try:
            # Try to use the user ID as an integer for partitioning (for backward compatibility)
            user_int = int(user_id_str)
        except ValueError:
            # If the ID is a string (e.g., 'test_user'), use a stable hash
            # This ensures consistent partitioning even for non-numeric IDs.
            # uuid is imported at the module level.
            user_int = uuid.uuid5(uuid.NAMESPACE_DNS, user_id_str).int
            
        return user_int % 10

    part_counts = [0] * 10
    for user in all_users:
        # Use the robust helper function instead of direct int() conversion
        part_index = get_partition_index(user['user_id'])
        part_counts[part_index] += 1
        
    users_to_display = []
    if selected_part is not None and 1 <= selected_part <= 10:
        part_index = selected_part - 1
        users_to_display = [
            # Use the robust helper function for filtering as well
            user for user in all_users if get_partition_index(user['user_id']) == part_index
        ]
        
    return render_template(
        'conversations.html', 
        users=users_to_display,
        part_counts=part_counts,
        total_count=total_count,
        selected_part=selected_part,
        chat_type=chat_type
    )


# ==========================================
# CORRECTIONS HUB ROUTES (NEW)
# ==========================================

@app.route('/corrections-hub')
@login_required
def corrections_hub():
    """Main corrections hub page for scientific questions."""
    return render_template('corrections_hub.html')


# ==========================================
# API ROUTES - USER STATS
# ==========================================

@app.route('/api/users/stats')
@login_required
def get_user_stats():
    """API endpoint to get user statistics."""
    try:
        stats = {
            'total_active_90_days': database.get_total_active_users(90),
            'total_active_30_days': database.get_total_active_users(30),
            'total_active_7_days': database.get_total_active_users(7),
            'total_active_24_hours': database.get_total_active_users(1)
        }
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# API ROUTES - SITE ISSUES
# ==========================================

@app.route('/api/issues/resolve', methods=['POST'])
@login_required
def resolve_issue():
    """
    API endpoint to resolve an issue.
    NEW: Also sends a confirmation message to the student.
    """
    try:
        data = request.get_json()
        issue_id = data.get('id')

        if not issue_id:
            return jsonify({'success': False, 'error': 'Issue ID not provided.'})

        # --- NEW: Fetch issue details BEFORE resolving ---
        conn = database.get_db_connection()
        issue_info = None
        try:
            with conn.cursor(cursor_factory=database.DictCursor) as cursor:
                cursor.execute(
                    "SELECT user_id, issue_type FROM site_issues WHERE id = %s AND status = 'open'",
                    (issue_id,)
                )
                issue_info = cursor.fetchone()
        except Exception as e:
            conn.close()
            utils.logger.error(f"Error fetching issue details: {e}")
            return jsonify({'success': False, 'error': 'Database error while fetching issue.'})
        conn.close()

        if not issue_info:
            return jsonify({'success': False, 'error': 'Issue not found or already resolved.'})
        
        user_id = issue_info.get('user_id') # Use .get() for safety, will be None for old issues
        issue_type = issue_info['issue_type']
        # --- End new block ---

        # Resolve the issue in the database
        success = database.resolve_site_issue(int(issue_id))
        
        if success:
            # --- *** THIS IS THE FIX *** ---
            # Only attempt to send a message if we have a user_id
            if user_id:
                message_text = "Your request has been processed."
                if issue_type == 'reopen_session':
                    message_text = "Your request to reopen the session has been approved. The session is now open."
                elif issue_type == 'extend_deadline':
                    message_text = "Your request to extend the deadline has been approved. The deadline has been extended."
                elif issue_type == 'remove_block':
                    message_text = "Your request to remove a block from your account has been approved. The block is now removed."
                
                try:
                    broadcaster.send_direct_message(user_id, message_text)
                    utils.logger.info(f"Sent resolution confirmation to {user_id} for issue {issue_id}")
                except Exception as e:
                    utils.logger.error(f"Failed to send message for resolved issue {issue_id} to {user_id}: {e}")
                
                return jsonify({'success': True, 'message': f'Issue resolved and student notified.'})
            
            else:
                # No user_id was found (likely an old entry), so just confirm resolution.
                utils.logger.warning(f"Issue {issue_id} resolved, but no user_id found. Cannot send notification.")
                return jsonify({'success': True, 'message': 'Issue marked as resolved (no student ID to notify).'})
            # --- *** END OF FIX *** ---
            
        else:
            return jsonify({'success': False, 'error': 'Issue not found or already resolved.'})

    except Exception as e:
        utils.logger.error(f"Error in resolve_issue: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/issues/send-message', methods=['POST'])
@login_required
def send_issue_message():
    """
    API endpoint to send a custom message to a student from the site issues page.
    NEW: Also resolves the issue.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        issue_id = data.get('issue_id') 
        message = data.get('message')

        if not issue_id or not message:
            return jsonify({'success': False, 'error': 'Issue ID and message are required.'})

        # --- NEW: Resolve the issue first ---
        success = database.resolve_site_issue(int(issue_id))
        if not success:
            utils.logger.warning(f"Failed to resolve issue {issue_id} while sending message (already resolved?).")
            # We can still try to send the message
        
        if user_id and user_id != 'None' and user_id != 'N/A':
            try:
                broadcaster.send_direct_message(user_id, message)
                utils.logger.info(f"Admin sent custom message to {user_id} and resolved issue {issue_id}.")
                return jsonify({'success': True, 'message': 'Message sent and issue resolved!'})
            except Exception as e:
                utils.logger.error(f"Error sending message in send_issue_message (issue {issue_id}): {e}", exc_info=True)
                # Return success=True because the issue was still resolved
                return jsonify({'success': True, 'message': f'Issue resolved, but failed to send message: {str(e)}'})
        else:
            utils.logger.info(f"Issue {issue_id} resolved with a custom message (but no user_id to send to).")
            return jsonify({'success': True, 'message': 'Issue resolved (no student ID to send message to).'})

    except Exception as e:
        utils.logger.error(f"Error in send_issue_message: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})
    
# ==========================================
# API ROUTES - BOT CONTROL
# ==========================================

@app.route('/api/bot/toggle', methods=['POST'])
@login_required
def toggle_bot():
    """API endpoint to toggle bot ON/OFF state using Redis."""
    try:
        state = redis_conn.get(BOT_STATE_KEY)
        if state is None:
            current_state_bool = True
        else:
            current_state_bool = state == 'true'

        new_state_bool = not current_state_bool
        redis_conn.set(BOT_STATE_KEY, 'true' if new_state_bool else 'false')

        return jsonify({'success': True, 'bot_enabled': new_state_bool})
    except Exception as e:
        utils.logger.error(f"Redis error in toggle_bot: {e}")
        return jsonify({'success': False, 'error': 'Failed to save state to Redis'})


# ==========================================
# API ROUTES - CONVERSATIONS
# ==========================================

@app.route('/api/conversation/<user_id>')
@login_required
def get_conversation(user_id):
    """API endpoint to get chat history for a user - supports both types."""
    chat_type = request.args.get('chat_type', 'administrative')
    
    database.update_admin_last_view(user_id)
    
    if chat_type == 'scientific':
        history = database.get_user_scientific_chat_history(user_id)
    else:
        history = database.get_user_chat_history(user_id)
    
    return jsonify({'success': True, 'conversation': history, 'chat_type': chat_type})

# ==========================================
# API ROUTES - CORRECTIONS (FIXED WITH CACHE UPDATES)
# ==========================================
@app.route('/api/conversation/correct', methods=['POST'])
@login_required
def correct_response():
    """
    Apply correction and CACHE the corrected answer with proper image hash.
    
    FIXED: Proper order and immediate is_corrected marking.
    """
    try:
        data = request.get_json()
        interaction_id = data.get('interaction_id')
        corrected_text = data.get('corrected_text')
        
        if not all([interaction_id, corrected_text]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        utils.logger.info(f" Correcting interaction {interaction_id}")
        
        # Get interaction details FIRST
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            cursor.execute('''
                SELECT user_input, cached_question_id, image_path
                FROM interactions 
                WHERE id = %s
            ''', (interaction_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return jsonify({'success': False, 'error': 'Interaction not found'})
            
            user_input = row['user_input']
            cached_id = row['cached_question_id']
            image_path = row['image_path']
        
        conn.close()
        
        # Compute image hash
        image_hash = None
        if image_path:
            try:
                import hashlib
                possible_paths = [
                    os.path.join(BASE_DIR, 'assets', image_path),
                    os.path.join(ASSETS_DIR, image_path),
                    image_path
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            image_hash = hashlib.sha256(f.read()).hexdigest()
                        utils.logger.info(f" Computed image hash: {image_hash[:16]}...")
                        break
            except Exception as e:
                utils.logger.error(f"Error computing hash: {e}")
        
        # Update or create cache
        if cached_id:
            # Update existing cache
            utils.logger.info(f"Updating existing cache ID {cached_id}")
            success = database.update_cached_question_answer(
                cached_question_id=cached_id,
                new_answer=corrected_text,
                correction_source='manual_correction'
            )
            
            if success:
                utils.logger.info(f" Cache {cached_id} updated")
        else:
            # Create NEW cache entry
            utils.logger.info("Creating NEW cache entry")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Cache with corrected answer
                success = loop.run_until_complete(
                    deduplicator.cache_question(
                        question_text=user_input,
                        answer_text=corrected_text,
                        image_hash=image_hash,
                        metadata={'corrected': True, 'source': 'admin_correction'}
                    )
                )
                
                if success:
                    utils.logger.info(" Cache created successfully")
                    
                    # NOW find the cache ID and mark it as corrected
                    conn = database.get_db_connection()
                    with conn.cursor() as cursor:
                        # Find the cache entry we just created
                        if image_hash:
                            cursor.execute('''
                                SELECT id FROM cached_scientific_questions
                                WHERE image_hash = %s
                                ORDER BY created_at DESC
                                LIMIT 1
                            ''', (image_hash,))
                        else:
                            cursor.execute('''
                                SELECT id FROM cached_scientific_questions
                                WHERE question_text = %s
                                ORDER BY created_at DESC
                                LIMIT 1
                            ''', (user_input,))
                        
                        result = cursor.fetchone()
                        if result:
                            new_cached_id = result[0]
                            
                            # CRITICAL FIX: Mark as corrected immediately!
                            cursor.execute('''
                                UPDATE cached_scientific_questions
                                SET is_corrected = TRUE,
                                    corrected_at = CURRENT_TIMESTAMP,
                                    correction_source = 'manual_correction'
                                WHERE id = %s
                            ''', (new_cached_id,))
                            
                            conn.commit()
                            
                            # Link to interaction
                            cursor.execute('''
                                UPDATE interactions
                                SET cached_question_id = %s
                                WHERE id = %s
                            ''', (new_cached_id, interaction_id))
                            
                            conn.commit()
                            
                            utils.logger.info(f" Cache {new_cached_id} marked as corrected and linked")
                            cached_id = new_cached_id
                        else:
                            utils.logger.warning("âš ï¸ Could not find created cache entry")
                    
                    conn.close()
                    
            finally:
                loop.close()
        
        # Update interaction with correction
        database.update_interaction_correction(interaction_id, corrected_text)
        utils.logger.info(f" Interaction {interaction_id} updated with correction")
        
        return jsonify({
            'success': True, 
            'message': 'Response corrected and cached successfully',
            'cached_id': cached_id
        })
        
    except Exception as e:
        utils.logger.error(f"Error in correct_response: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/conversation/approve', methods=['POST'])
@login_required
def approve_response():
    """
    Approve answer as correct and cache it.
    
    FIXED: Immediate is_corrected marking.
    """
    try:
        data = request.get_json()
        interaction_id = data.get('interaction_id')
        
        if not interaction_id:
            return jsonify({'success': False, 'error': 'Missing interaction_id'})
        
        utils.logger.info(f"ðŸ‘ Approving interaction {interaction_id}")
        
        # Get interaction details
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            cursor.execute('''
                SELECT user_input, bot_response, cached_question_id, image_path
                FROM interactions 
                WHERE id = %s
            ''', (interaction_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return jsonify({'success': False, 'error': 'Interaction not found'})
            
            user_input = row['user_input']
            bot_response = row['bot_response']
            cached_id = row['cached_question_id']
            image_path = row['image_path']
        
        conn.close()
        
        # Compute image hash
        image_hash = None
        if image_path:
            try:
                import hashlib
                possible_paths = [
                    os.path.join(BASE_DIR, 'assets', image_path),
                    os.path.join(ASSETS_DIR, image_path),
                    image_path
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            image_hash = hashlib.sha256(f.read()).hexdigest()
                        utils.logger.info(f" Computed image hash: {image_hash[:16]}...")
                        break
            except Exception as e:
                utils.logger.error(f"Error computing hash: {e}")
        
        if not cached_id:
            # Create cache entry
            utils.logger.info("Creating cache for approved answer")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                success = loop.run_until_complete(
                    deduplicator.cache_question(
                        question_text=user_input,
                        answer_text=bot_response,
                        image_hash=image_hash,
                        metadata={'approved': True, 'source': 'admin_approval'}
                    )
                )
                
                if success:
                    # Find and mark as corrected
                    conn = database.get_db_connection()
                    with conn.cursor() as cursor:
                        if image_hash:
                            cursor.execute('''
                                SELECT id FROM cached_scientific_questions
                                WHERE image_hash = %s
                                ORDER BY created_at DESC
                                LIMIT 1
                            ''', (image_hash,))
                        else:
                            cursor.execute('''
                                SELECT id FROM cached_scientific_questions
                                WHERE question_text = %s
                                ORDER BY created_at DESC
                                LIMIT 1
                            ''', (user_input,))
                        
                        result = cursor.fetchone()
                        if result:
                            new_cached_id = result[0]
                            
                            # Mark as corrected (approved = corrected)
                            cursor.execute('''
                                UPDATE cached_scientific_questions
                                SET is_corrected = TRUE,
                                    corrected_at = CURRENT_TIMESTAMP,
                                    correction_source = 'admin_approval'
                                WHERE id = %s
                            ''', (new_cached_id,))
                            
                            conn.commit()
                            
                            # Link to interaction
                            cursor.execute('''
                                UPDATE interactions
                                SET cached_question_id = %s,
                                    is_corrected = TRUE,
                                    corrected_text = %s,
                                    user_feedback = 1
                                WHERE id = %s
                            ''', (new_cached_id, bot_response, interaction_id))
                            
                            conn.commit()
                            
                            utils.logger.info(f" Cache {new_cached_id} created and approved")
                            cached_id = new_cached_id
                    
                    conn.close()
            finally:
                loop.close()
        else:
            # Just mark existing as approved
            database.update_cached_question_answer(
                cached_question_id=cached_id,
                new_answer=bot_response,
                correction_source='admin_approval'
            )
            
            conn = database.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE interactions
                    SET is_corrected = TRUE,
                        corrected_text = %s,
                        user_feedback = 1
                    WHERE id = %s
                ''', (bot_response, interaction_id))
                conn.commit()
            conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Answer approved and cached successfully',
            'cached_id': cached_id
        })
        
    except Exception as e:
        utils.logger.error(f"Error in approve_response: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/conversation/correct_both', methods=['POST'])
@login_required
def correct_response_and_add_to_faq():
    """
    Correct answer, cache it with image hash, AND add to FAQ file.
    """
    try:
        data = request.get_json()
        interaction_id = data.get('interaction_id')
        corrected_text = data.get('corrected_text')
        original_question = data.get('original_question')
        faq_filename = data.get('faq_filename')
        chat_type = data.get('chat_type', 'administrative')

        if not all([interaction_id, corrected_text, original_question, faq_filename]):
            return jsonify({'success': False, 'error': 'Missing required fields'})

        # Update interaction
        database.update_interaction_correction(interaction_id, corrected_text)
        utils.logger.info(f"âœ“ Updated interaction {interaction_id}")
        
        # Cache the correction (same logic as correct_response)
        try:
            conn = database.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT user_input, cached_question_id, image_path
                    FROM interactions 
                    WHERE id = %s
                ''', (interaction_id,))
                
                row = cursor.fetchone()
                if row:
                    user_input = row[0]
                    cached_id = row[1]
                    image_path = row[2]
                    
                    # Compute image hash
                    image_hash = None
                    if image_path:
                        try:
                            import hashlib
                            possible_paths = [
                                os.path.join(BASE_DIR, 'assets', image_path),
                                os.path.join(BASE_DIR, image_path),
                                os.path.join(ASSETS_DIR, image_path),
                                image_path
                            ]
                            
                            for path in possible_paths:
                                if os.path.exists(path):
                                    with open(path, 'rb') as f:
                                        image_hash = hashlib.sha256(f.read()).hexdigest()
                                    break
                        except:
                            pass
                    
                    if cached_id:
                        # Update existing cache
                        database.update_cached_question_answer(
                            cached_question_id=cached_id,
                            new_answer=corrected_text,
                            correction_source='manual_with_faq'
                        )
                        utils.logger.info(f"âœ“ Updated cache ID {cached_id}")
                    else:
                        # Create new cache
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        try:
                            cache_success = loop.run_until_complete(
                                deduplicator.cache_question(
                                    question_text=user_input,
                                    answer_text=corrected_text,
                                    image_hash=image_hash,
                                    metadata={'corrected': True, 'added_to_faq': True}
                                )
                            )
                            
                            if cache_success:
                                similar = loop.run_until_complete(
                                    deduplicator.find_similar_question(
                                        question_text=user_input,
                                        image_hash=image_hash
                                    )
                                )
                                
                                if similar:
                                    new_cached_id = similar['id']
                                    database.update_cached_question_answer(
                                        cached_question_id=new_cached_id,
                                        new_answer=corrected_text,
                                        correction_source='manual_with_faq'
                                    )
                                    database.link_correction_to_cache(interaction_id, new_cached_id)
                                    utils.logger.info(f"âœ“ Created cache ID {new_cached_id}")
                        finally:
                            loop.close()
            
            conn.close()
        except Exception as e:
            utils.logger.error(f"Error caching: {e}")
        
        # Add to FAQ file
        if chat_type == 'scientific':
            faqs_path = os.path.join(BASE_DIR, 'scientific_kb', 'faqs')
        else:
            faqs_path = os.path.join(KNOWLEDGE_BASE_DIR, 'faqs')

        safe_filename = faq_filename.replace('..', '')
        filepath = os.path.join(faqs_path, safe_filename)
        
        if not os.path.abspath(filepath).startswith(os.path.abspath(faqs_path)):
            return jsonify({'success': False, 'error': 'Invalid file path'})
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        faq_data = []
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    faq_data = json.load(f)
                    if not isinstance(faq_data, list):
                        faq_data = []
            except json.JSONDecodeError:
                faq_data = []

        faq_data.append({'question': original_question, 'answer': corrected_text})
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(faq_data, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True, 
            'message': f'Correction cached and added to {faq_filename}'
        })

    except Exception as e:
        utils.logger.error(f"Error in correct_both: {e}")
        return jsonify({'success': False, 'error': str(e)})




# ==========================================
# API ROUTES - FAQ MANAGEMENT
# ==========================================

@app.route('/api/faqs/list')
@login_required
def list_faq_files():
    """API to list all available FAQ JSON files - supports both types."""
    try:
        chat_type = request.args.get('chat_type', 'administrative')
        
        if chat_type == 'scientific':
            faqs_base = os.path.join(BASE_DIR, 'scientific_kb', 'faqs')
            files = []
            
            if os.path.exists(faqs_base):
                for item in os.listdir(faqs_base):
                    item_path = os.path.join(faqs_base, item)
                    
                    if os.path.isdir(item_path):
                        for filename in os.listdir(item_path):
                            if filename.endswith('.json'):
                                relative_path = os.path.join(item, filename)
                                files.append(relative_path.replace('\\', '/'))
                                
                    elif os.path.isfile(item_path) and item.endswith('.json'):
                        files.append(item)
        else:
            faqs_path = os.path.join(KNOWLEDGE_BASE_DIR, 'faqs')
            if not os.path.exists(faqs_path):
                os.makedirs(faqs_path)
            files = [f for f in os.listdir(faqs_path) if f.endswith('.json')]
        
        return jsonify({'success': True, 'files': sorted(files), 'chat_type': chat_type})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/faq/add', methods=['POST'])
@login_required
def add_to_faq():
    """API to add a new question-answer pair to a FAQ file."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        question = data.get('question')
        answer = data.get('answer')
        chat_type = data.get('chat_type', 'administrative')

        if not all([filename, question, answer]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        if not filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'Invalid filename, must end with .json'})

        if chat_type == 'scientific':
            faqs_path = os.path.join(BASE_DIR, 'scientific_kb', 'faqs')
        else:
            faqs_path = os.path.join(KNOWLEDGE_BASE_DIR, 'faqs')
        
        # Security: Clean the filename to prevent directory traversal attacks
        safe_filename = filename.replace('..', '')
        filepath = os.path.join(faqs_path, safe_filename)
        
        # Security check: ensure the resolved path is within the intended faqs_path directory
        if not os.path.abspath(filepath).startswith(os.path.abspath(faqs_path)):
            return jsonify({'success': False, 'error': 'Invalid file path detected.'})
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        faq_data = []
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    faq_data = json.load(f)
                    if not isinstance(faq_data, list):
                        faq_data = []
            except json.JSONDecodeError:
                faq_data = []

        faq_data.append({'question': question, 'answer': answer})
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(faq_data, f, ensure_ascii=False, indent=2)

        return jsonify({'success': True, 'message': f'Successfully added to {filename}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# API ROUTES - CONTENT MANAGEMENT
# ==========================================

@app.route('/api/file/create', methods=['POST'])
@login_required
def create_file():
    """API to create a new knowledge file in the correct context."""
    try:
        data = request.get_json()
        view = data.get('view', 'administrative')
        file_type = data.get('type')
        filename = secure_filename(data.get('filename').replace('\\', '/'))
        content = data.get('content', '')
        
        base_path = get_base_path(view, file_type)
        filepath = os.path.join(base_path, filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if file_type == 'document' and not filename.endswith('.md'):
            filename += '.md'
        elif file_type == 'faq' and not filename.endswith('.json'):
            filename += '.json'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': 'File created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/file/read')
@login_required
def read_file():
    """API to read the content of a knowledge file from the correct context."""
    try:
        view = request.args.get('view', 'administrative')
        file_type = request.args.get('type')
        filename = request.args.get('filename')
        
        base_path = get_base_path(view, file_type)
        filepath = os.path.join(base_path, filename)
            
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'})
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/file/update', methods=['POST'])
@login_required
def update_file():
    """API to update an existing knowledge file in the correct context."""
    try:
        data = request.get_json()
        view = data.get('view', 'administrative')
        file_type = data.get('type')
        filename = data.get('filename')
        content = data.get('content')
        
        base_path = get_base_path(view, file_type)
        filepath = os.path.join(base_path, filename)
            
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'})
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': 'File updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/file/delete', methods=['DELETE'])
@login_required
def delete_file():
    """API to delete a knowledge file from the correct context."""
    try:
        view = request.args.get('view', 'administrative')
        file_type = request.args.get('type')
        filename = request.args.get('filename')
        
        base_path = get_base_path(view, file_type)
        filepath = os.path.join(base_path, filename)
            
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'})
            
        os.remove(filepath)
        return jsonify({'success': True, 'message': 'File deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/refresh-vector-store', methods=['POST'])
@login_required
def refresh_vector_store():
    """API endpoint to refresh BOTH vector stores."""
    try:
        knowledge_processor.create_vector_store()
        knowledge_processor.create_scientific_vector_store()
        return jsonify({'success': True, 'message': 'All vector stores refreshed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# API ROUTES - FEEDBACK MANAGEMENT
# ==========================================

@app.route('/api/feedback/dismiss', methods=['POST'])
@login_required
def dismiss_feedback():
    """API endpoint to dismiss a feedback item."""
    try:
        interaction_id = request.get_json().get('interaction_id')
        if not interaction_id:
            return jsonify({'success': False, 'error': 'Interaction ID not provided'})
        database.update_interaction_feedback(interaction_id, 0)
        return jsonify({'success': True, 'message': 'Feedback dismissed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# API ROUTES - CORRECTIONS HUB (NEW)
# ==========================================

@app.route('/api/corrections/statistics')
@login_required
def get_correction_statistics():
    """API endpoint to get correction statistics for the corrections hub."""
    try:
        stats = database.get_correction_statistics()
        
        # Also get cache statistics if available
        try:
            cache_stats = deduplicator.get_statistics()
            stats['cache'] = cache_stats
        except Exception as e:
            utils.logger.warning(f"Could not get cache statistics: {e}")
            stats['cache'] = {}
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        utils.logger.error(f"Error getting correction statistics: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/corrections/pending-statistics')
@login_required
def get_pending_statistics():
    """API endpoint to get pending questions statistics."""
    try:
        # Get count of disliked scientific questions that are not yet corrected
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM interactions
                WHERE chat_type = 'scientific'
                  AND user_feedback = -1
                  AND (is_corrected = FALSE OR is_corrected IS NULL)
            ''')
            
            result = cursor.fetchone()
            pending_count = result['count'] if result else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'pending_count': pending_count
        })
    except Exception as e:
        utils.logger.error(f"Error getting pending statistics: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/corrections/pending-list')
@login_required
def list_pending_questions():
    """API endpoint to list all pending (disliked, uncorrected) scientific questions."""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        search_query = request.args.get('search', None)
        
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            # Base query
            where_clauses = [
                "chat_type = 'scientific'",
                "user_feedback = -1",
                "(is_corrected = FALSE OR is_corrected IS NULL)"
            ]
            params = []
            
            # Add search filter
            if search_query:
                where_clauses.append("(user_input ILIKE %s OR bot_response ILIKE %s)")
                params.extend([f'%{search_query}%', f'%{search_query}%'])
            
            where_clause = ' AND '.join(where_clauses)
            
            # Get pending questions
            query = f'''
                SELECT 
                    id,
                    user_id,
                    user_input,
                    bot_response,
                    image_path,
                    timestamp,
                    cached_question_id
                FROM interactions
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            '''
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            pending_questions = [dict(row) for row in cursor.fetchall()]
            
            # Get total count
            count_query = f'''
                SELECT COUNT(*) as count
                FROM interactions
                WHERE {where_clause}
            '''
            cursor.execute(count_query, params[:-2] if search_query else [])
            total_count = cursor.fetchone()['count']
        
        conn.close()
        
        total_pages = (total_count + limit - 1) // limit
        
        return jsonify({
            'success': True,
            'pending_questions': pending_questions,
            'total': total_count,
            'page': page,
            'pages': total_pages
        })
    except Exception as e:
        utils.logger.error(f"Error listing pending questions: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/corrections/pending-detail/<int:interaction_id>')
@login_required
def get_pending_detail(interaction_id):
    """API endpoint to get full details of a specific pending question."""
    try:
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            cursor.execute('''
                SELECT * FROM interactions 
                WHERE id = %s AND chat_type = 'scientific'
            ''', (interaction_id,))
            
            row = cursor.fetchone()
            if row:
                return jsonify({
                    'success': True,
                    'pending_question': dict(row)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Question not found'
                })
        
        conn.close()
    except Exception as e:
        utils.logger.error(f"Error getting pending detail: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})
    
    
@app.route('/api/corrections/list')
@login_required
def list_corrections():
    """API endpoint to list all corrected interactions with filters."""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        search_query = request.args.get('search', None)
        chapter = request.args.get('chapter', None)
        lesson = request.args.get('lesson', None)
        date_from = request.args.get('date_from', None)
        date_to = request.args.get('date_to', None)
        
        corrections = database.get_all_corrected_interactions(
            search_query=search_query,
            chapter=chapter,
            lesson=lesson,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset
        )
        
        total_count = database.get_corrected_count(search_query=search_query)
        total_pages = (total_count + limit - 1) // limit
        
        return jsonify({
            'success': True,
            'corrections': corrections,
            'total': total_count,
            'page': page,
            'pages': total_pages
        })
    except Exception as e:
        utils.logger.error(f"Error listing corrections: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/corrections/detail/<int:correction_id>')
@login_required
def get_correction_detail(correction_id):
    """API endpoint to get full details of a specific correction."""
    try:
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            cursor.execute('''
                SELECT * FROM interactions 
                WHERE id = %s AND chat_type = 'scientific'
            ''', (correction_id,))
            
            row = cursor.fetchone()
            if row:
                return jsonify({
                    'success': True,
                    'correction': dict(row)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Correction not found'
                })
    except Exception as e:
        utils.logger.error(f"Error getting correction detail: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()


@app.route('/api/corrections/find-similar', methods=['POST'])
@login_required
def find_similar_questions():
    """API endpoint to find similar uncorrected questions for bulk correction."""
    try:
        data = request.get_json()
        question_text = data.get('question_text')
        
        if not question_text:
            return jsonify({'success': False, 'error': 'Question text is required'})
        
        similar_questions = database.get_similar_uncorrected_questions(
            question_text=question_text,
            limit=20
        )
        
        return jsonify({
            'success': True,
            'similar': similar_questions
        })
    except Exception as e:
        utils.logger.error(f"Error finding similar questions: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/corrections/bulk-apply', methods=['POST'])
@login_required
def bulk_apply_correction():
    """
    Apply correction to multiple interactions and cache all with proper image hashes.
    """
    try:
        data = request.get_json()
        interaction_ids = data.get('interaction_ids', [])
        corrected_text = data.get('corrected_text')
        
        if not interaction_ids or not corrected_text:
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Apply bulk correction
        count = database.bulk_apply_correction(interaction_ids, corrected_text)
        utils.logger.info(f"âœ“ Corrected {count} interactions")
        
        # Cache all corrections
        try:
            conn = database.get_db_connection()
            with conn.cursor() as cursor:
                # Get all cached question IDs
                cursor.execute('''
                    SELECT DISTINCT cached_question_id, user_input, image_path
                    FROM interactions 
                    WHERE id = ANY(%s)
                ''', (interaction_ids,))
                
                rows = cursor.fetchall()
                
                cached_count = 0
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    for row in rows:
                        cached_id = row[0]
                        user_input = row[1]
                        image_path = row[2]
                        
                        if cached_id:
                            # Update existing cache
                            success = database.update_cached_question_answer(
                                cached_question_id=cached_id,
                                new_answer=corrected_text,
                                correction_source='bulk_correction'
                            )
                            if success:
                                cached_count += 1
                        else:
                            # Create new cache with image hash
                            image_hash = None
                            if image_path:
                                try:
                                    import hashlib
                                    possible_paths = [
                                        os.path.join(BASE_DIR, 'assets', image_path),
                                        os.path.join(BASE_DIR, image_path),
                                        os.path.join(ASSETS_DIR, image_path),
                                        image_path
                                    ]
                                    
                                    for path in possible_paths:
                                        if os.path.exists(path):
                                            with open(path, 'rb') as f:
                                                image_hash = hashlib.sha256(f.read()).hexdigest()
                                            break
                                except:
                                    pass
                            
                            cache_success = loop.run_until_complete(
                                deduplicator.cache_question(
                                    question_text=user_input,
                                    answer_text=corrected_text,
                                    image_hash=image_hash,
                                    metadata={'bulk_corrected': True}
                                )
                            )
                            
                            if cache_success:
                                cached_count += 1
                finally:
                    loop.close()
                
                utils.logger.info(f"âœ“ Cached {cached_count} corrections")
            
            conn.close()
        except Exception as e:
            utils.logger.warning(f"Error caching bulk corrections: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Corrected {count} questions and cached for future use',
            'count': count
        })
        
    except Exception as e:
        utils.logger.error(f"Error in bulk_apply: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/corrections/export-all', methods=['POST'])
@login_required
def export_all_corrections():
    """API endpoint to export all corrections as a JSON file."""
    try:
        corrections = database.get_all_corrected_interactions(limit=10000)
        
        # Format for export
        export_data = []
        for correction in corrections:
            export_data.append({
                'question': correction['user_input'],
                'original_answer': correction['bot_response'],
                'corrected_answer': correction['corrected_text'],
                'student_id': correction['user_id'],
                'timestamp': correction['timestamp'].isoformat() if correction['timestamp'] else None
            })
        
        return jsonify({
            'success': True,
            'data': export_data,
            'count': len(export_data)
        })
    except Exception as e:
        utils.logger.error(f"Error exporting corrections: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# API ROUTES - CACHE MANAGEMENT (NEW)
# ==========================================

@app.route('/api/cache/statistics')
@login_required
def get_cache_statistics():
    """API endpoint to get question cache statistics."""
    try:
        stats = deduplicator.get_statistics()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        utils.logger.error(f"Error getting cache statistics: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})



@app.route('/api/cache/delete/<int:cached_id>', methods=['DELETE'])
@login_required
def delete_cached_question(cached_id):
    """
    Delete a cached question and unlink all interactions from it.
    
    FIXED: Also marks interactions as uncorrected when cache is deleted.
    """
    try:
        utils.logger.info(f"ðŸ—‘ï¸ Attempting to delete cached question ID {cached_id}")
        
        conn = database.get_db_connection()
        
        try:
            with conn.cursor() as cursor:
                # First, get all interaction IDs that will be affected
                cursor.execute('''
                    SELECT id FROM interactions 
                    WHERE cached_question_id = %s
                ''', (cached_id,))
                
                affected_ids = [row[0] for row in cursor.fetchall()]
                
                # Unlink interactions AND mark them as uncorrected
                cursor.execute('''
                    UPDATE interactions 
                    SET cached_question_id = NULL,
                        is_corrected = FALSE,
                        corrected_text = NULL
                    WHERE cached_question_id = %s
                ''', (cached_id,))
                
                unlinked_count = cursor.rowcount
                utils.logger.info(f"âœ“ Unlinked and unmarked {unlinked_count} interactions from cache ID {cached_id}")
                
                # Now delete the cached question
                cursor.execute('''
                    DELETE FROM cached_scientific_questions 
                    WHERE id = %s
                    RETURNING id
                ''', (cached_id,))
                
                deleted = cursor.fetchone()
                
                if deleted:
                    conn.commit()
                    utils.logger.info(f"âœ“ Successfully deleted cached question ID {cached_id}")
                    return jsonify({
                        'success': True,
                        'message': f'Cached answer deleted successfully. {unlinked_count} interactions unmarked as corrected.',
                        'affected_interactions': affected_ids
                    })
                else:
                    conn.rollback()
                    utils.logger.warning(f"âš ï¸ Cached question ID {cached_id} not found")
                    return jsonify({
                        'success': False,
                        'error': 'Cached question not found'
                    })
        
        except Exception as e:
            conn.rollback()
            utils.logger.error(f"Error deleting cached question: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Database error: {str(e)}'
            })
        
        finally:
            conn.close()
    
    except Exception as e:
        utils.logger.error(f"Error in delete_cached_question: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/interaction/delete/<int:interaction_id>', methods=['DELETE'])
@login_required
def delete_interaction(interaction_id):
    """
    Delete a single interaction record.
    
    This can be used to remove incorrect interactions entirely.
    """
    try:
        utils.logger.info(f"ðŸ—‘ï¸ Attempting to delete interaction ID {interaction_id}")
        
        success = database.delete_interaction_by_id(interaction_id)
        
        if success:
            utils.logger.info(f"âœ“ Successfully deleted interaction {interaction_id}")
            return jsonify({
                'success': True, 
                'message': f'Interaction {interaction_id} deleted successfully.'
            })
        else:
            utils.logger.warning(f"âš ï¸ Interaction {interaction_id} not found")
            return jsonify({
                'success': False, 
                'error': f'Interaction {interaction_id} not found.'
            })
    
    except Exception as e:
        utils.logger.error(f"Error deleting interaction {interaction_id}: {e}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': str(e)
        })


@app.route('/api/cache/clear-old', methods=['POST'])
@login_required
def clear_old_cache():
    """
    API endpoint to clear cache entries older than specified days.
    
    This is a maintenance route to clean up old, unused cache entries.
    """
    try:
        data = request.get_json()
        days = data.get('days', 90)
        min_usage = data.get('min_usage', 3)
        
        utils.logger.info(f"ðŸ§¹ Clearing cache entries older than {days} days with less than {min_usage} uses")
        
        conn = database.get_db_connection()
        
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
            
            conn.close()
            
            utils.logger.info(f"âœ“ Cleared {len(deleted_ids)} old cache entries")
            
            return jsonify({
                'success': True,
                'message': f'Cleared {len(deleted_ids)} old cache entries',
                'count': len(deleted_ids)
            })
        
        except Exception as e:
            conn.rollback()
            conn.close()
            utils.logger.error(f"Error clearing old cache: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    except Exception as e:
        utils.logger.error(f"Error in clear_old_cache: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/cache/force-update', methods=['POST'])
@login_required
def force_update_cache():
    """
    Admin utility: Manually force update a cached question.
    Useful for fixing cache inconsistencies.
    """
    try:
        data = request.get_json()
        question_text = data.get('question_text')
        new_answer = data.get('new_answer')
        
        if not all([question_text, new_answer]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Find similar cached question
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        similar_cached = loop.run_until_complete(
            deduplicator.find_similar_question(
                question_text=question_text,
                image_hash=None
            )
        )
        loop.close()
        
        if similar_cached:
            cached_id = similar_cached['id']
            success = database.update_cached_question_answer(
                cached_question_id=cached_id,
                new_answer=new_answer,
                correction_source='manual_force_update'
            )
            
            if success:
                utils.logger.info(f"âœ“ Force updated cached question ID {cached_id}")
                return jsonify({
                    'success': True,
                    'message': f'Updated cached question ID {cached_id}',
                    'cached_id': cached_id
                })
        
        return jsonify({
            'success': False,
            'message': 'No matching cached question found'
        })
            
    except Exception as e:
        utils.logger.error(f"Error in force_update_cache: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# BROADCAST FEATURE SETUP
# ==========================================

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'mp3', 'opus', 'wav', 'm4a', 'pdf'}
UPLOAD_FOLDERS = {
    'photo': os.path.join(ASSETS_DIR, 'photos'),
    'video': os.path.join(ASSETS_DIR, 'videos'),
    'audio': os.path.join(ASSETS_DIR, 'audio'),
    'pdf': os.path.join(ASSETS_DIR, 'pdf')
}

# Create upload folders
for folder in UPLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/broadcast/send', methods=['POST'])
@login_required
def handle_broadcast():
    """Handles sending all types of broadcasts with targeted user support."""
    try:
        broadcast_type = request.form.get('broadcast_type')
        target_mode = request.form.get('target_mode', 'all')
        target_user_ids = None
        
        # Parse target user IDs if specific mode is selected
        if target_mode == 'specific':
            target_user_ids_str = request.form.get('target_user_ids')
            if target_user_ids_str:
                try:
                    target_user_ids = json.loads(target_user_ids_str)
                    if not isinstance(target_user_ids, list) or len(target_user_ids) == 0:
                        return jsonify({'success': False, 'error': 'Invalid target_user_ids format. Must be a non-empty list.'})
                    # Convert to integers and validate
                    target_user_ids = [int(uid) for uid in target_user_ids]
                except (json.JSONDecodeError, ValueError) as e:
                    return jsonify({'success': False, 'error': f'Invalid user IDs format: {str(e)}'})
            else:
                return jsonify({'success': False, 'error': 'No target user IDs provided for specific broadcast.'})
        
        if broadcast_type in ['announcement', 'video', 'voice', 'pdf']:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file part in the request.'})
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected.'})

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                folder_key_map = {
                    'announcement': 'photo',
                    'voice': 'audio',
                    'video': 'video',
                    'pdf': 'pdf'
                }
                folder_key = folder_key_map.get(broadcast_type)
                
                if not folder_key:
                    return jsonify({'success': False, 'error': f'Invalid broadcast type for file upload: {broadcast_type}'})

                upload_folder = UPLOAD_FOLDERS[folder_key]
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)

                caption = request.form.get('caption', '')
                
                # Pass target_user_ids to broadcaster
                broadcaster.run_broadcast(
                    broadcast_type, 
                    target_user_ids=target_user_ids,
                    file_path=file_path, 
                    caption=caption
                )
                
                target_info = f"{len(target_user_ids)} specific users" if target_user_ids else "all users"
                return jsonify({
                    'success': True, 
                    'message': f'{broadcast_type.capitalize()} broadcast started successfully to {target_info}.'
                })
            
            return jsonify({'success': False, 'error': 'File type not allowed.'})

        elif broadcast_type == 'quiz':
            quiz_data_str = request.form.get('quiz_data')
            if not quiz_data_str:
                return jsonify({'success': False, 'error': 'Missing quiz data.'})
            
            try:
                quiz_data = json.loads(quiz_data_str)
                if not isinstance(quiz_data, list) or len(quiz_data) == 0:
                    return jsonify({'success': False, 'error': 'Invalid quiz data format. Expected a list of questions.'})

            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Could not decode quiz data.'})
                
            # Pass target_user_ids to broadcaster
            broadcaster.run_broadcast(
                'quiz', 
                target_user_ids=target_user_ids,
                quiz_data=quiz_data
            )
            
            target_info = f"{len(target_user_ids)} specific users" if target_user_ids else "all users"
            return jsonify({
                'success': True, 
                'message': f'Quiz broadcast started successfully to {target_info}.'
            })

        else:
            return jsonify({'success': False, 'error': f'Invalid broadcast type: {broadcast_type}'})

    except Exception as e:
        utils.logger.error(f"Error in handle_broadcast: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# ERROR HANDLERS
# ==========================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('error.html', error='Page Not Found'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return render_template('error.html', error='Internal Server Error'), 500



# ==========================================
# DEBUGGING
# ==========================================

@app.route('/api/debug/cache-inspect')
@login_required
def debug_cache_inspect():
    """Debug endpoint to inspect cache entries and why they're not matching."""
    try:
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=database.DictCursor) as cursor:
            # Get all cache entries with full details
            cursor.execute('''
                SELECT 
                    id,
                    question_text,
                    answer_text,
                    image_hash,
                    is_corrected,
                    times_used,
                    created_at,
                    corrected_at,
                    correction_source
                FROM cached_scientific_questions
                ORDER BY created_at DESC
                LIMIT 20
            ''')
            
            cache_entries = []
            for row in cursor.fetchall():
                entry = dict(row)
                
                # Extract signature for debugging
                if entry['question_text']:
                    from enhanced_question_deduplication import deduplicator
                    sig = deduplicator._create_question_signature(entry['question_text'])
                    entry['signature'] = {
                        'fingerprint': sig['fingerprint'][:100],
                        'formulas': list(sig['formulas']),
                        'keywords': list(sig['keywords']),
                        'numbers': list(sig['numbers'])
                    }
                
                cache_entries.append(entry)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'cache_entries': cache_entries,
            'total': len(cache_entries)
        })
        
    except Exception as e:
        utils.logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/debug/test-match', methods=['POST'])
@login_required
def debug_test_match():
    """Test matching logic with a sample question."""
    try:
        data = request.get_json()
        question_text = data.get('question_text')
        image_hash = data.get('image_hash', None)
        
        if not question_text:
            return jsonify({'success': False, 'error': 'question_text required'})
        
        utils.logger.info(f"ðŸ§ª Testing match for: {question_text[:100]}...")
        
        # Run the matching logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from enhanced_question_deduplication import deduplicator
            
            # Get signature
            sig = deduplicator._create_question_signature(question_text)
            
            # Try to find match
            match = loop.run_until_complete(
                deduplicator.find_similar_question(
                    question_text=question_text,
                    image_hash=image_hash
                )
            )
            
            result = {
                'success': True,
                'incoming_signature': {
                    'fingerprint': sig['fingerprint'],
                    'formulas': list(sig['formulas']),
                    'keywords': list(sig['keywords']),
                    'numbers': list(sig['numbers'])
                },
                'match_found': match is not None
            }
            
            if match:
                result['matched_cache'] = {
                    'id': match['id'],
                    'question': match['question_text'][:200],
                    'times_used': match['times_used'],
                    'is_corrected': match['is_corrected']
                }
            
            return jsonify(result)
            
        finally:
            loop.close()
        
    except Exception as e:
        utils.logger.error(f"Error in test match: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == '__main__':
    print("=" * 60)
    print("Starting Admin Dashboard with Enhanced Cache Management...")
    print("=" * 60)
    print(f"Dashboard URL: http://localhost:5000")
    print(f"Knowledge Base: {KNOWLEDGE_BASE_DIR}")
    print(f"Scientific KB: {os.path.join(BASE_DIR, 'scientific_kb')}")
    print(f"Data Directory: {DATA_DIR}")
    print()
    print("âœ“ Cache correction fixes enabled")
    print("âœ“ Corrections Hub available at /corrections-hub")
    print("âœ“ All routes initialized successfully")
    print("=" * 60)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)