# extra_sources_handlers.py
import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import config
import utils

logger = utils.logger

# Load extra source answers
def load_extra_answers():
    """Load all extra source JSON files"""
    gareeda_path = os.path.join(config.QUESTIONS_DIR, 'gareda.json')
    with open(gareeda_path, 'r', encoding='utf-8') as file:
        gareeda_answers = json.load(file)
    
    moaaser_path = os.path.join(config.QUESTIONS_DIR, 'Moaaser.json')
    with open(moaaser_path, 'r', encoding='utf-8') as file:
        moaaser_answers = json.load(file)
    
    tafwoq_path = os.path.join(config.QUESTIONS_DIR, 'Tafwoq.json')
    with open(tafwoq_path, 'r', encoding='utf-8') as file:
        tafwoq_answers = json.load(file)
    
    logger.info("Loaded extra source answer files")
    return gareeda_answers, moaaser_answers, tafwoq_answers

# Initialize answers
gareeda_answers, moaaser_answers, tafwoq_answers = load_extra_answers()


async def handle_extra_sources(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str, query) -> bool:
    """
    Handle all extra sources related callbacks.
    Returns True if the choice was handled, False otherwise.
    """
    
    # Main extra sources menu
    if choice == 'extra_sources':
        keyboard = [
            [InlineKeyboardButton("Gareeda", callback_data='gareeda')],
            [InlineKeyboardButton("Tafwoq", callback_data='tafwoq')],
            [InlineKeyboardButton("Moaaser Chapters", callback_data='moasser_chapters')],
            [InlineKeyboardButton("Moaaser Models", callback_data='moasser_models')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text('Hello, enter the source:', reply_markup=reply_markup)
        return True

    # ==================== GAREEDA HANDLERS ====================
    if choice == 'gareeda':
        chapters = []
        
        # Generate buttons for chapters 1 to 5
        for i in range(1, 6):
            chapters.append([InlineKeyboardButton(f"Chapter {i}", callback_data=f'gareeda_chapter_{i}')])
        
        reply_markup = InlineKeyboardMarkup(chapters)
        await query.message.reply_text(text="Which chapter:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_1':
        parts = [
            [InlineKeyboardButton("part 1", callback_data='gareeda_chapter_1_pt1')],
            [InlineKeyboardButton("part 2", callback_data='gareeda_chapter_1_pt2')],
            [InlineKeyboardButton("part essay", callback_data='gareeda_chapter_1_essay')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_2':
        parts = [
            [InlineKeyboardButton("part 1", callback_data='gareeda_chapter_2_pt1')],
            [InlineKeyboardButton("part 2", callback_data='gareeda_chapter_2_pt2')],
            [InlineKeyboardButton("part essay", callback_data='gareeda_chapter_2_essay')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_3':
        parts = [
            [InlineKeyboardButton("part 1", callback_data='gareeda_chapter_3_pt1')],
            [InlineKeyboardButton("part 2", callback_data='gareeda_chapter_3_pt2')],
            [InlineKeyboardButton("part essay", callback_data='gareeda_chapter_3_essay')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_4':
        parts = [
            [InlineKeyboardButton("part 1", callback_data='gareeda_chapter_4_pt1')],
            [InlineKeyboardButton("part 2", callback_data='gareeda_chapter_4_pt2')],
            [InlineKeyboardButton("part essay", callback_data='gareeda_chapter_4_essay')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
    


    elif choice == 'gareeda_chapter_5':
        parts = [
            [InlineKeyboardButton("part 1", callback_data='gareeda_chapter_5_pt1')],
            [InlineKeyboardButton("part 2", callback_data='gareeda_chapter_5_pt2')],
            [InlineKeyboardButton("part essay", callback_data='gareeda_chapter_5_essay')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which Part:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_1_pt1':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 46):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_1_pt1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_1_pt2':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 28):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_1_pt2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_1_essay':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 11):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_1_essay_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_2_pt1':
        questions = []
        for i in range(1, 34):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_2_pt1_question_{i}')])
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_2_pt2':
            questions = []
            for i in range(1, 33):
                questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_2_pt2_question_{i}')])
            reply_markup = InlineKeyboardMarkup(questions)
            await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_2_essay':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 11):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_2_essay_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
    

    elif choice == 'gareeda_chapter_3_pt1':
        questions = []
        for i in range(1, 25):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_3_pt1_question_{i}')])
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_3_pt2':
        questions = []
        for i in range(1, 37):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_3_pt2_question_{i}')])

        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_3_essay':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 11):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_3_essay_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)



    elif choice == 'gareeda_chapter_4_pt1':
        questions = []
        for i in range(1, 36):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_4_pt1_question_{i}')])
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_4_pt2':
        questions = []
        for i in range(1, 29):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_4_pt2_question_{i}')])
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)



    elif choice == 'gareeda_chapter_4_essay':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 11):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_4_essay_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_5_pt1':
        questions = []
        for i in range(1, 64):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_5_pt1_question_{i}')])
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'gareeda_chapter_5_pt2':
        questions = []
        for i in range(1, 92):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_5_pt2_question_{i}')])
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'gareeda_chapter_5_essay':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 11):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'gareeda_chapter_5_essay_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

#--------------------------------------------------------------------------------------------
                             
    

#Moaaser
    async def handle_moaaser_chapter(choice):
        logger.info(f"Handling query for choice: {choice}")

        # Define a dictionary mapping model numbers to their respective question ranges
        chapter_question_ranges = {
            1: (1, 71),
            2: (1, 75),
            3: (1, 83),
            4: (1, 64),
            5: (1, 58),
            6: (58,115)
            

        }

        if choice == 'moasser_chapters':
            chapter_Number = 6  # Define the total number of models dynamically or fetch it from your data
            
            
            chapters = []
            for i in range(1, chapter_Number + 1):
                chapters.append([InlineKeyboardButton(f"Chapter {i}", callback_data=f'moasser_chapters_{i}')])
            
            reply_markup = InlineKeyboardMarkup(chapters)
            await query.message.reply_text(text="Which chapter:", reply_markup=reply_markup)

        elif choice.startswith('moasser_chapters_'):
                chapter_Number = int(choice.split('_')[-1])  # Extract the chapter number from the callback_data
                logger.info(f"Selected Chapter number: {chapter_Number}")
                
                # Get the question range for the selected model from the dictionary
                
                question_range = chapter_question_ranges.get(chapter_Number, (1, 90))  # Default to (1, 47) if model number not found
                logger.info(f"Question range for chapter {chapter_Number}: {question_range}")
                
                start_question, end_question = question_range
                
                questions = []
                for i in range(start_question, end_question + 1):
                    question_key = f"Moaaser_chapter_{chapter_Number}_question_{i}"
                    #if question_key in Moaaser_answers:
                    questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'{question_key}')])

                    

                reply_markup = InlineKeyboardMarkup(questions)
                await query.message.reply_text(text=f"Which question from chapter {chapter_Number} :", reply_markup=reply_markup)

    await handle_moaaser_chapter(choice)
    
#Moaaser Models
    async def handle_moaaser_model(choice):
        logger.info(f"Handling query for choice: {choice}")

        # Define a dictionary mapping model numbers to their respective question ranges
        model_question_ranges = {
            1: (1, 50),
            2: (1, 46),
            3: (1, 46),
            4: (1, 50),
            5: (1, 50),
            6: (1, 30),
            7: (1, 50),
            8: (1, 50),
            9: (1, 50),
            10: (1, 46),
            11: (1, 46),
            12: (1, 46),
            13: (1, 46),
            14: (1, 46),
            15: (1, 46),
            16: (1, 46),
            17: (1, 46),
            18: (1, 46),
            19: (1, 46),
            20: (1, 46),
            21: (1, 46),
            22: (1, 46),
            23: (1, 46),
            24: (1, 46)
        }

        if choice == 'moasser_models':
            model_number = 24  # Define the total number of models dynamically or fetch it from your data


            models = []
            for i in range(10, model_number + 1):
                models.append([InlineKeyboardButton(f"Model {i}", callback_data=f'moasser_model_{i}')])
            
            reply_markup = InlineKeyboardMarkup(models)
            await query.message.reply_text(text="Which Model:", reply_markup=reply_markup)

        elif choice.startswith('moasser_model_'):
                model_number = int(choice.split('_')[-1])  # Extract the model number from the callback_data
                logger.info(f"Selected model number: {model_number}")
                
                # Get the question range for the selected model from the dictionary
                question_range = model_question_ranges.get(model_number, (1, 47))  # Default to (1, 47) if model number not found
                logger.info(f"Question range for model {model_number}: {question_range}")
                
                start_question, end_question = question_range
                
                questions = []
                for i in range(start_question, end_question + 1):
                    question_key = f"Moaaser_model_{model_number}_question_{i}"
                    #if question_key in Moaaser_answers:
                    questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'{question_key}')])
                    
                reply_markup = InlineKeyboardMarkup(questions)
                await query.message.reply_text(text=f"Which question from Model {model_number} :", reply_markup=reply_markup)

    # Example usage:
    # Assuming 'choice' is the callback_data received from the user interaction
    await handle_moaaser_model(choice)

#Tafwoqel
    if choice == 'tafwoq':
        options = [
            [InlineKeyboardButton("Chapters", callback_data='tafwoq_chapter')],
            [InlineKeyboardButton("Models", callback_data='tafwoq_model')]
        ]
        reply_markup = InlineKeyboardMarkup(options)
        await query.message.reply_text(text="Which option:", reply_markup=reply_markup) 


    elif choice == 'tafwoq_chapter':
        chapters = [
            [InlineKeyboardButton("chapter 1", callback_data='tafwoq_chapter_1')],
            [InlineKeyboardButton("chapter 2", callback_data='tafwoq_chapter_2')],
            [InlineKeyboardButton("chapter 3", callback_data='tafwoq_chapter_3')],
            [InlineKeyboardButton("chapter 4", callback_data='tafwoq_chapter_4')],
            #form 1 to 100
            [InlineKeyboardButton("chapter 5 ", callback_data='tafwoq_chapter_5')]
        ]
        reply_markup = InlineKeyboardMarkup(chapters)
        await query.message.reply_text(text="Which chapter:", reply_markup=reply_markup)

    

    elif choice == 'tafwoq_chapter_1':
        parts = [
            [InlineKeyboardButton("Lesson 1", callback_data='tafwoq_chapter_1_pt1')],
            [InlineKeyboardButton("Lesson 2", callback_data='tafwoq_chapter_1_pt2')],
            [InlineKeyboardButton("Exam", callback_data='tafwoq_chapter_1_exam')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which Part:", reply_markup=reply_markup)
        
    elif choice == 'tafwoq_chapter_2':
        parts = [
            [InlineKeyboardButton("Lesson 1", callback_data='tafwoq_chapter_2_pt1')],
            [InlineKeyboardButton("Lesson 2", callback_data='tafwoq_chapter_2_pt2')],
            [InlineKeyboardButton("Exam", callback_data='tafwoq_chapter_2_exam')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which Part:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_3':
        parts = [
            [InlineKeyboardButton("Lesson 1", callback_data='tafwoq_chapter_3_pt1')],
            [InlineKeyboardButton("Lesson 2", callback_data='tafwoq_chapter_3_pt2')],
            [InlineKeyboardButton("Exam", callback_data='tafwoq_chapter_3_exam')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which Part:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_4':
        parts = [
            [InlineKeyboardButton("Lesson 1", callback_data='tafwoq_chapter_4_pt1')],
            [InlineKeyboardButton("Lesson 2", callback_data='tafwoq_chapter_4_pt2')],
            [InlineKeyboardButton("Exam", callback_data='tafwoq_chapter_4_exam')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which Part:", reply_markup=reply_markup)


    elif choice == 'tafwoq_chapter_5':
        parts = [
            [InlineKeyboardButton("Lesson 1", callback_data='tafwoq_chapter_5_pt1')],
            [InlineKeyboardButton("Lesson 2", callback_data='tafwoq_chapter_5_pt2')],
            [InlineKeyboardButton("Lesson 3", callback_data='tafwoq_chapter_5_pt3')],
            [InlineKeyboardButton("Lesson 4", callback_data='tafwoq_chapter_5_pt4')],
            [InlineKeyboardButton("Exam", callback_data='tafwoq_chapter_5_exam')]
        ]
        reply_markup = InlineKeyboardMarkup(parts)
        await query.message.reply_text(text="Which Part:", reply_markup=reply_markup)



    elif choice == 'tafwoq_chapter_1_pt1':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_1_pt1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_1_pt2':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_1_pt2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_1_exam':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_1_exam_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup) 


    elif choice == 'tafwoq_chapter_2_pt1':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_2_pt1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_2_pt2':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_2_pt2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_2_exam':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_2_exam_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)



    elif choice == 'tafwoq_chapter_3_pt1':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_3_pt1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_3_pt2':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_3_pt2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_3_exam':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_3_exam_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)



    elif choice == 'tafwoq_chapter_4_pt1':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_4_pt1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_4_pt2':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_4_pt2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_4_exam':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_4_exam_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)



    elif choice == 'tafwoq_chapter_5_pt1':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_5_pt1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_5_pt2':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_5_pt2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_5_pt3':
        questions = []
        
        # Generate buttons for questions 1 to 4
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_5_pt3_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_5_pt4':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_5_pt4_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)

    elif choice == 'tafwoq_chapter_5_exam':
        questions = []
        
        # Generate buttons for questions 1 to 5
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_chapter_5_exam_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    elif choice == 'tafwoq_model':
        moodels = [
        [InlineKeyboardButton("Model 1", callback_data='tafwoq_model_1')],
        [InlineKeyboardButton("Model 2", callback_data='tafwoq_model_2')],
        [InlineKeyboardButton("Model 3", callback_data='tafwoq_model_3')],
        [InlineKeyboardButton("Model 4", callback_data='tafwoq_model_4')],
        [InlineKeyboardButton("Model 5", callback_data='tafwoq_model_5')],
        [InlineKeyboardButton("Model 6", callback_data='tafwoq_model_6')],
        [InlineKeyboardButton("Model 7", callback_data='tafwoq_model_7')],
        [InlineKeyboardButton("Model 8", callback_data='tafwoq_model_8')],
        [InlineKeyboardButton("Model 9", callback_data='tafwoq_model_9')],
        [InlineKeyboardButton("Model 10", callback_data='tafwoq_model_10')]
        ]
        reply_markup = InlineKeyboardMarkup(moodels)
        await query.message.reply_text(text="Which Model:", reply_markup=reply_markup)


    elif choice == 'tafwoq_model_1':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_1_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
    


    elif choice == 'tafwoq_model_2':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_2_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_3':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_3_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_4':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_4_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_5':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_5_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_6':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_6_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_7':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_7_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_8':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_8_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_9':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_9_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)
       


    elif choice == 'tafwoq_model_10':
        questions = []
        
        # Generate buttons for questions 1 to 71
        for i in range(1, 47):
            questions.append([InlineKeyboardButton(f"Question {i}", callback_data=f'tafwoq_model_10_question_{i}')])
        
        reply_markup = InlineKeyboardMarkup(questions)
        await query.message.reply_text(text="Which question:", reply_markup=reply_markup)


    # ==================== ANSWER DELIVERY ====================
    # Check if this is a final answer request
    elif choice in gareeda_answers:
        await query.message.reply_text(text=gareeda_answers[choice], parse_mode='HTML')
        return True
    elif choice in moaaser_answers:
        await query.message.reply_text(text=moaaser_answers[choice], parse_mode='HTML')
        return True
    elif choice in tafwoq_answers:
        await query.message.reply_text(text=tafwoq_answers[choice], parse_mode='HTML')
        return True

    # Not handled by this module
    return False