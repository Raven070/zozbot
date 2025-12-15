# broadcaster.py - OPTIMIZED VERSION WITH TARGETED BROADCASTING
import asyncio
import telegram
from telegram import Poll
from telegram.ext import Application
import config
import database
import utils
import os
import threading

bot = telegram.Bot(token=config.TELEGRAM_TOKEN)
logger = utils.logger

async def send_broadcast(broadcast_type, target_user_ids=None, **kwargs):
    """
    Asynchronously sends a broadcast message to all active users or specific users in batches.
    
    Args:
        broadcast_type: Type of broadcast (announcement, video, voice, pdf, quiz)
        target_user_ids: List of specific user IDs to target (None = all users)
        **kwargs: Additional parameters for the broadcast
    """
    logger.info(f"Starting broadcast of type '{broadcast_type}'...")
    
    successful_sends = 0
    failed_sends = 0
    batch_size = 100  # Process 100 users at a time
    offset = 0
    
    # Create a new application instance for this broadcast
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # Determine target users
    if target_user_ids:
        # Targeted broadcast to specific users
        total_users = len(target_user_ids)
        logger.info(f"Broadcasting to {total_users} specific users...")
        user_batches = [target_user_ids[i:i + batch_size] for i in range(0, len(target_user_ids), batch_size)]
    else:
        # Broadcast to all active users
        total_users = database.get_total_active_users()
        logger.info(f"Broadcasting to {total_users} active users in batches of {batch_size}...")
        user_batches = None
    
    # Process batches
    batch_index = 0
    while True:
        # Fetch next batch of user IDs
        if target_user_ids:
            # Use pre-defined batches for targeted broadcast
            if batch_index >= len(user_batches):
                break
            user_batch = user_batches[batch_index]
            batch_index += 1
        else:
            # Fetch from database for all users
            user_batch = database.get_user_ids_batch(offset, batch_size)
            if not user_batch:
                break
            offset += batch_size
        
        # Process this batch
        for chat_id in user_batch:
            try:
                if broadcast_type == 'announcement':
                    with open(kwargs['file_path'], 'rb') as photo_file:
                        await app.bot.send_photo(chat_id=chat_id, photo=photo_file, caption=kwargs['caption'])
                
                elif broadcast_type == 'video':
                    with open(kwargs['file_path'], 'rb') as video_file:
                        await app.bot.send_video(chat_id=chat_id, video=video_file, caption=kwargs['caption'])

                elif broadcast_type == 'voice':
                    with open(kwargs['file_path'], 'rb') as audio_file:
                        await app.bot.send_audio(chat_id=chat_id, audio=audio_file, caption=kwargs['caption'])
                
                elif broadcast_type == 'pdf':
                    with open(kwargs['file_path'], 'rb') as doc_file:
                        await app.bot.send_document(chat_id=chat_id, document=doc_file, caption=kwargs['caption'])

                elif broadcast_type == 'quiz':
                    quiz_data = kwargs.get('quiz_data', [])
                    for i, quiz_item in enumerate(quiz_data):
                        await app.bot.send_poll(
                            chat_id=chat_id,
                            question=quiz_item['question'],
                            options=quiz_item['options'],
                            type=Poll.QUIZ,
                            correct_option_id=quiz_item['correct_option_id'],
                            is_anonymous=True
                        )
                        if i < len(quiz_data) - 1:
                            await asyncio.sleep(0.5)
                
                successful_sends += 1
                await asyncio.sleep(0.05)  # Small delay to avoid rate limits

            except Exception as e:
                failed_sends += 1
                logger.error(f"Failed to send broadcast to {chat_id}: {e}")
        
        logger.info(f"Processed batch. Total sent: {successful_sends}, Failed: {failed_sends}")

    logger.info(f"Broadcast finished. Successful: {successful_sends}, Failed: {failed_sends}")


def _run_async_in_thread(broadcast_type, target_user_ids=None, **kwargs):
    """Helper function to run the asyncio event loop."""
    asyncio.run(send_broadcast(broadcast_type, target_user_ids=target_user_ids, **kwargs))

def run_broadcast(broadcast_type, target_user_ids=None, **kwargs):
    """
    Runs the broadcast function in a separate thread to avoid event loop conflicts with Flask.
    
    Args:
        broadcast_type: Type of broadcast
        target_user_ids: List of specific user IDs (None = all users)
        **kwargs: Additional parameters
    """
    try:
        broadcast_thread = threading.Thread(
            target=_run_async_in_thread,
            args=(broadcast_type,),
            kwargs={'target_user_ids': target_user_ids, **kwargs}
        )
        broadcast_thread.start()
        logger.info(f"Broadcast thread started for type '{broadcast_type}'. The web request will now complete.")
    except Exception as e:
        logger.error(f"An error occurred when starting the broadcast thread: {e}")
        raise e

# --- NEW FUNCTION FOR DIRECT MESSAGES (FIXED) ---

async def _send_direct_message_async(user_id, text):
    """
    Asynchronously sends a single direct message.
    *** Creates its own Application instance to avoid loop conflicts. ***
    """
    app = None
    try:
        # --- THIS IS THE FIX ---
        # Create a new, temporary Application instance for this thread
        app = Application.builder().token(config.TELEGRAM_TOKEN).build()
        
        # Use the bot from this new application
        await app.bot.send_message(chat_id=user_id, text=text)
        logger.info(f"Successfully sent direct message to {user_id}")
        # --- END OF FIX ---
        
    except Exception as e:
        # Add exc_info=True to get the full traceback for errors
        logger.error(f"Failed to send direct message to {user_id}: {e}", exc_info=True)
    finally:
        # Clean up the application if it was created
        if app:
            await app.shutdown()


def send_direct_message(user_id, text):
    """
    Runs the async direct message send in a separate thread 
    to avoid blocking Flask and manage asyncio loops.
    """
    def run_loop():
        """Helper to run the asyncio loop in a thread."""
        try:
            asyncio.run(_send_direct_message_async(user_id, text))
        except Exception as e:
             logger.error(f"Error in send_direct_message thread loop for {user_id}: {e}")
    
    try:
        msg_thread = threading.Thread(target=run_loop, daemon=True)
        msg_thread.start()
        logger.info(f"Direct message thread started for user {user_id}.")
    except Exception as e:
        logger.error(f"Failed to start direct message thread for {user_id}: {e}")