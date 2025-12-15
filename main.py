#!/usr/bin/env python3
"""
Heroku Bot - Handles text + site images
Forwards only chemistry images to AWS
"""
import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from flask import Flask

# Import both cores
from ai_core import EnhancedAICore
from image_issue_handler import site_issue_handler

app = Flask(__name__)
ai_core = EnhancedAICore()

# AWS Scientific Worker (only for chemistry)
AWS_WORKER_URL = os.getenv("AWS_WORKER_URL")

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(), application.bot)
    
    if update.message and update.message.photo:
        # It's an image—decide which handler to use
        return await route_image(update)
    else:
        # Text question
        return await handle_text(update)

async def route_image(update):
    """Route image to correct handler"""
    # Download photo
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"/tmp/{update.update_id}.jpg"
    await photo_file.download_to_drive(photo_path)
    
    # Try administrative image handler first
    issue_type, response = await site_issue_handler.analyze_issue_image(photo_path)
    
    if issue_type != "go_back_to_the_page":
        # It's a site issue (administrative) - handle on Heroku
        await update.message.reply_text(response['text'])
        os.remove(photo_path)
        return "OK", 200
    else:
        # It's likely a chemistry problem - forward to AWS
        return await forward_to_aws(update, photo_path)

async def forward_to_aws(update, photo_path):
    """Forward chemistry image to AWS Scientific Worker"""
    try:
        with open(photo_path, 'rb') as f:
            image_data = f.read()
        
        question = update.message.caption or "Solve this chemistry problem"
        
        response = requests.post(
            AWS_WORKER_URL,
            files={'image': image_data},
            data={'question': question},
            headers={'X-API-Key': os.getenv('AWS_WORKER_API_KEY')},
            timeout=30
        )
        
        if response.status_code == 200:
            answer = response.json()['answer']
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(
                "Sorry, I couldn't process the chemistry question. Please contact Dr. Nasser."
            )
        
        os.remove(photo_path)
        return "OK", 200
        
    except Exception as e:
        logger.error(f"AWS forwarding failed: {e}")
        os.remove(photo_path)
        await update.message.reply_text("Error processing image. Please try again.")
        return "ERROR", 500

async def handle_text(update):
    """Fast text processing on Heroku"""
    user_input = update.message.text
    user_id = str(update.message.from_user.id)
    
    response = await ai_core.get_enhanced_response(user_input, user_id)
    await update.message.reply_text(response.text)
    return "OK", 200

if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=PORT)