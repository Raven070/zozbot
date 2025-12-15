# bot_setup.py
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from config import TELEGRAM_TOKEN
import handlers

def create_application():
    """Builds the bot application and registers all handlers."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Register user-facing handlers
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button))

    # This routes photos to the correct handler based on user's selected mode
    # Must come BEFORE the text handler
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handlers.handle_photo))
    
    # Register the general text message handler (must be one of the last to be added)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    return application