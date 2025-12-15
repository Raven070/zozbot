# handlers.py
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Poll
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction 
import uuid
import utils
import ai_core
import config
import database
from extra_sources_handlers import handle_extra_sources
from scientific_core import scientific_core_instance
from image_issue_handler import site_issue_handler

# --- Initializations ---
logger = utils.logger
lol_answers = utils.load_lols()

# --- NEW HELPER FUNCTION for persistent typing indicator ---
async def send_typing_periodically(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Sends the 'typing' action every 4 seconds until the task is cancelled."""
    try:
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(6)  # Refresh typing status every 4 seconds
    except asyncio.CancelledError:
        # This is the expected and clean way to stop the task
        pass
    except Exception as e:
        logger.error(f"Error in send_typing_periodically task: {e}")


# --- Main Command and Message Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /start command."""
    chat_id = str(update.message.chat_id)
    user = update.effective_user
    
    # Register user in database 
    database.register_user(
        user_id=chat_id,
        username=user.username,
        first_name=user.first_name
    )

    photo_path = os.path.join(config.PHOTO_DIR, "image10.jpg")
    await context.bot.send_photo(chat_id=chat_id, photo=open(photo_path, 'rb'))

    voice_path = os.path.join(config.AUDIO_DIR, 'voice1.mp3')
    await update.message.reply_voice(voice=open(voice_path, 'rb'))

    keyboard = [
        [InlineKeyboardButton("Adminstrative", callback_data='adminstrative')],
        [InlineKeyboardButton("Scientific", callback_data='scientific')],
        [InlineKeyboardButton("Zoz Ai", callback_data='zoz_ai')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome ya zoz, How can I help you:', reply_markup=reply_markup)



async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for all inline button callbacks."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    

    handled = await handle_extra_sources(update, context, choice, query)
    if handled:
        return
    
    # --- Handle feedback buttons ---
    if choice.startswith('feedback_'):
        _, action, interaction_id_str = choice.split('_')
        interaction_id = int(interaction_id_str)


        if action == 'like':
            database.update_interaction_feedback(interaction_id, 1)
            await query.edit_message_text(
                text=query.message.text ,
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif action == 'dislike':
            database.update_interaction_feedback(interaction_id, -1)
            await query.edit_message_text(
                text=query.message.text + "\n\n*Thanks! We've logged your feedback to improve our responses.*",
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN
            )
        
        return # Stop processing after handling feedback

    # --- Existing button logic ---
    if choice == 'adminstrative':
        # Clear AI modes when entering the non-AI administrative flow
        context.user_data.pop('state', None)
        context.user_data.pop('choice', None)
        issues = [
            [InlineKeyboardButton("Centers", callback_data='centers')],
            [InlineKeyboardButton("Payment Method", callback_data='payment_method')],
            [InlineKeyboardButton("Site Issues", callback_data='site')],
            [InlineKeyboardButton("System", callback_data='system')],
        ]
        reply_markup = InlineKeyboardMarkup(issues)
        await query.message.reply_text(text="These are common issues for you:", reply_markup=reply_markup)

    elif choice == 'site':
        site_issues = [
            [InlineKeyboardButton("Reopen the session", callback_data='reopen_session')],
            [InlineKeyboardButton("Remove the block", callback_data='remove_block')],
            [InlineKeyboardButton("Extend the class deadline", callback_data='extend_deadline')],
        ]
        reply_markup = InlineKeyboardMarkup(site_issues)
        await query.message.reply_text(text="Which issue do you need help with?", reply_markup=reply_markup)

    elif choice in ['reopen_session', 'remove_block', 'extend_deadline']:
        context.user_data['issue'] = choice
        if choice in ['reopen_session', 'extend_deadline']:
            await query.message.reply_text("Please enter the session number.")
            context.user_data['awaiting_session'] = True
        else:
            await query.message.reply_text("Please send your site code.")

    elif choice == 'zoz_ai':
        context.user_data['choice'] = 'zoz_ai'
        context.user_data.pop('state', None)
        context.user_data.pop('last_scientific_question', None)
        context.user_data.pop('last_scientific_answer', None)
        context.user_data.pop('re_explain_count', None)
        await query.message.reply_text(
            text="*You selected Zoz Ai.* Please type your question \n\nIgnore these 👍 , 👎 if my response is good ",
            parse_mode=ParseMode.MARKDOWN
        )

    elif choice == 'centers':
        issues = [
            [InlineKeyboardButton("القاهرة والجيزة", callback_data='cairo_giza')],
            [InlineKeyboardButton("الاسكندرية ", callback_data='alexandaria')],
            [InlineKeyboardButton("الاسماعيلية ", callback_data='ismail')],
            [InlineKeyboardButton("قليوب", callback_data='qalyoub')],
            [InlineKeyboardButton("بنها", callback_data='benha')],
            [InlineKeyboardButton("أسيوط", callback_data='assuit')],
            [InlineKeyboardButton("البحر الأحمر (الغردقة)", callback_data='red_sea_hurgada')],
            [InlineKeyboardButton("الغربية (طنطا)", callback_data='gharbia_tanta')],
            [InlineKeyboardButton("المنصورة", callback_data='mansoura')],
            [InlineKeyboardButton("السويس", callback_data='suez')],
            [InlineKeyboardButton("المنوفية", callback_data='menofia')],
            [InlineKeyboardButton("الزقازيق", callback_data='zagazig')],
            [InlineKeyboardButton("قنا", callback_data='qena')],
        ]
        reply_markup = InlineKeyboardMarkup(issues)
        await query.message.reply_text(text="انت من انهي محافظة", reply_markup=reply_markup)

    elif choice == 'cairo_giza':
        locations = [
            [InlineKeyboardButton("مدينة نصر", callback_data='madint_nasr')],
            [InlineKeyboardButton("التجمع الخامس", callback_data='Tagamo3_elkhames')],
            [InlineKeyboardButton("التجمع الاول", callback_data='Tagamo3_elawl')],
            [InlineKeyboardButton("الرحاب", callback_data='elrhab')],
            [InlineKeyboardButton("مدينتي", callback_data='madinty')],
            [InlineKeyboardButton("الشروق", callback_data='elshrouk')],
            [InlineKeyboardButton("العبور", callback_data='elobour')],
            [InlineKeyboardButton("مصر الجديدة", callback_data='misr_gedida')],
            [InlineKeyboardButton("الف مسكن/ عين شمس", callback_data='alfmaskn_aynshams')],
            [InlineKeyboardButton("الزيتون", callback_data='elzayton')],
            [InlineKeyboardButton("الظاهر", callback_data='eldaher')],
            [InlineKeyboardButton("العباسية", callback_data='elabasya')],
            [InlineKeyboardButton("المقطم", callback_data='elmoqattam')],
            [InlineKeyboardButton("المعادي", callback_data='elmaadi')],
            [InlineKeyboardButton("زهراء المعادي  ", callback_data='zahra_elmaadi')],
            [InlineKeyboardButton("السيدة زينب", callback_data='sayeda_zeinab')],
            [InlineKeyboardButton("شبرا", callback_data='shobra')],
            [InlineKeyboardButton("الهرم", callback_data='elharm')],
            [InlineKeyboardButton("المهندسين", callback_data='elmohandeseen')],
            [InlineKeyboardButton("الشيخ زايد", callback_data='elsheikh_zayed')],
            [InlineKeyboardButton("٦ اكتوبر", callback_data='6_october')],
            [InlineKeyboardButton("حدايق اكتوبر", callback_data='hadyek_october')],
            [InlineKeyboardButton("حدايق الاهرام", callback_data='hadyek_elahrm')],
            [InlineKeyboardButton("الهضبة", callback_data='elhadaba')],
            [InlineKeyboardButton("الدقي", callback_data='eldokki')],
            [InlineKeyboardButton("حلوان", callback_data='helwan')],
            [InlineKeyboardButton("حدايق حلوان", callback_data='hadyek_helwan')],
        ]
        reply_markup = InlineKeyboardMarkup(locations)
        await query.message.reply_text(text="تختار انهي منطقة ؟ ", reply_markup=reply_markup)

    elif choice == 'alexandaria':
        centers = [
            [InlineKeyboardButton("سنتر جولدن", callback_data='سنتر_جولدن')],
            [InlineKeyboardButton("سنتر الأكاديمية الأمريكية ", callback_data='سنتر_الأكاديمية_الأمريكية')],
            [InlineKeyboardButton(" الأكاديمية فرع لوران", callback_data='الأكاديمية_فرع_لوران')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'mansoura':
        centers = [
            [InlineKeyboardButton("سنتر تالنت فرع أحمد ماهر ", callback_data='سنتر_تالنت_فرع_أحمد_ماهر')],
            [InlineKeyboardButton(" مكتبات الشاذلي", callback_data='مكتبات_الشاذلي')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'madint_nasr':
        centers = [
            [InlineKeyboardButton("سنتر اكسفورد سيتي", callback_data='سنتر_اكسفورد_سيتي')],
            [InlineKeyboardButton("سنتر اكسفورد عباس", callback_data='سنتر_اكسفورد_عباس')],
            [InlineKeyboardButton(" سنتر اكسفورد سراج", callback_data='سنتر_اكسفورد_سراج')],
            [InlineKeyboardButton("سنتر هارفارد", callback_data='سنتر_هارفاد')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'Tagamo3_elkhames':
        centers = [
            [InlineKeyboardButton("سنتر اكسالنت", callback_data='سنتر_اكسالنت')],
            [InlineKeyboardButton("سنتر فيوتشر دريم", callback_data='سنتر_فيوتشر_دريم')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'madinty':
        centers = [
            [InlineKeyboardButton("كايرو مدينتي سنتر داخل مكتبه برناسوس", callback_data='كايرو_مدينتي_سنتر_داخل_مكتبه_برناسوس')],
            [InlineKeyboardButton("سنتر Success إيست هب مول", callback_data='سنتر_Success_إيست_هب_مول')],
            [InlineKeyboardButton("مكتبه الصفتي البي 10 مدينتي", callback_data='مكتبه_الصفتي_البي_10_مدينتي')],
            [InlineKeyboardButton("Molis schoo", callback_data='molis_school')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elobour':
        centers = [
            [InlineKeyboardButton("سنتر النخبة الحي الثاني", callback_data='سنتر_النخبة_الحي_الثاني')],
            [InlineKeyboardButton("سنتر النخبة فرع الشباب", callback_data='سنتر_النخبة_فرع_الشباب')],
            [InlineKeyboardButton("سنتر النخبة الحي التاسع", callback_data='سنتر_النخبة_الحي_التاسع')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'misr_gedida':
        centers = [
            [InlineKeyboardButton("  سنتر هليوبوليس الميرالند", callback_data='سنتر_هليوبوليس_الميرالند')],
            [InlineKeyboardButton("كابيتال الحجاز  ", callback_data='كابيتال_الحجاز')],
            [InlineKeyboardButton(" اوبل مصر الجديدة ", callback_data='اوبل_مصر_الجديدة')],
            [InlineKeyboardButton(" EAY Cairo سنتر ", callback_data='EAY_Cairo_سنتر')],
            [InlineKeyboardButton(" سنتر Aone ", callback_data='سنتر_Aone')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elmoqattam':
        centers = [
            [InlineKeyboardButton(" سنتر ناسا المقطم ", callback_data='سنتر_ناسا_المقطم')],
            [InlineKeyboardButton(" ناسا الهضبة ", callback_data='ناسا_الهضبة')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elmaadi':
        centers = [
            [InlineKeyboardButton(" سنتر DHL ", callback_data='سنتر_DHL')],
            [InlineKeyboardButton(" سنتر نيو ستار ", callback_data='سنتر_نيو_ستار')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'shobra':
        centers = [
            [InlineKeyboardButton(" سنتر الراعي ", callback_data='سنتر_الراعي')],
            [InlineKeyboardButton(" سنتر هاني بيير ", callback_data='سنتر_هاني_بيير')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elharm':
        centers = [
            [InlineKeyboardButton(" سنتر مكة ", callback_data='سنتر_مكة')],
            [InlineKeyboardButton("مكة فرع اخناتون  ", callback_data='مكة_فرع_اخناتon')],
            [InlineKeyboardButton(" سنتر 1A ", callback_data='سنتر_1A')],
            [InlineKeyboardButton(" سنتر الفا الهرم ", callback_data='سنتر_الفا_الهرم')],
            [InlineKeyboardButton(" سنتر سمارت الهرم ", callback_data='سنتر_سمارت_الهرم')],
            [InlineKeyboardButton(" الفا فيصل ", callback_data='الفا_فيصل')],
            [InlineKeyboardButton(" الفا اللبيني ", callback_data='الفا_اللبيني')],
            [InlineKeyboardButton(" سنتر كوليدج الهرم ", callback_data='سنتر_كوليدج_الهرم')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elmohandeseen':
        centers = [
            [InlineKeyboardButton(" سنتر النخيل ", callback_data='سنتر_النخيل')],
            [InlineKeyboardButton("learn المهندسين  ", callback_data='learn_المهندسين')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elsheikh_zayed':
        centers = [
            [InlineKeyboardButton(" سنتر فيوتشر الشيخ زايد ", callback_data='سنتر_فيوتشر_الشيخ_زايد')],
            [InlineKeyboardButton(" سنتر سمارت الشيخ زايد ", callback_data='سنتر_سمارت_الشيخ_زايد')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == '6_october':
        centers = [
            [InlineKeyboardButton(" سنتر سمارت أكتوبر ", callback_data='سنتر_سمارت_أكتوبر')],
            [InlineKeyboardButton(" Capital education center ", callback_data='Capital_education_center')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'hadyek_elahrm':
        centers = [
            [InlineKeyboardButton(" سنتر teachers ", callback_data='سنتر_teachers')],
            [InlineKeyboardButton(" سنتر كوليدج النادي ", callback_data='سنتر_كوليدج_النادي')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'elhadaba':
        centers = [
            [InlineKeyboardButton(" سنتر 1A النادي ", callback_data='سنتر_1A_النادي')],
            [InlineKeyboardButton(" حورس College ", callback_data='حورس_College')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'helwan':
        centers = [
            [InlineKeyboardButton(" سنتر ناسا حلوان ", callback_data='سنتر_ناسا_حلوان')],
            [InlineKeyboardButton("  سنتر DHL حلوان", callback_data='سنتر_DHL_حلوان')],
            [InlineKeyboardButton("سنتر DHL مايو  ", callback_data='سنتر_DHL_مايو')],
        ]
        reply_markup = InlineKeyboardMarkup(centers)
        await query.message.reply_text(text="تختار انهي سنتر ؟ ", reply_markup=reply_markup)

    elif choice == 'alfmaskn_aynshams':
        await query.message.reply_text(text=lol_answers['سنتر_المنهل'], parse_mode='HTML')
    elif choice == 'Tagamo3_elawl':
        await query.message.reply_text(text="top academy سنتر")
    elif choice == 'elshrouk':
        await query.message.reply_text(text=lol_answers['ناسا_فرع_الشروق'], parse_mode='HTML')
    elif choice == 'elrhab':
        await query.message.reply_text(text=lol_answers['سنتر_المنهل'], parse_mode='HTML')
    elif choice == 'elzayton':
        await query.message.reply_text(text=lol_answers['سنتر_دار_السعادة'], parse_mode='HTML')
    elif choice == 'eldaher':
        await query.message.reply_text(text=lol_answers['هاني_بيير'], parse_mode='HTML')
    elif choice == 'elabasya':
        await query.message.reply_text(text=lol_answers['سنتر_نيو_فيوتشر_العباسية'], parse_mode='HTML')
    elif choice == 'zahra_elmaadi':
        await query.message.reply_text(text=lol_answers['سنتر_ناسا_المعادي'], parse_mode='HTML')
    elif choice == 'sayeda_zeinab':
        await query.message.reply_text(text=lol_answers['سنتر_ابو_العزايم'], parse_mode='HTML')
    elif choice == 'hadyek_october':
        await query.message.reply_text(text=lol_answers['الفردوس_College'], parse_mode='HTML')
    elif choice == 'eldokki':
        await query.message.reply_text(text=lol_answers['سنتر_Learn_الدقي'], parse_mode='HTML')
    elif choice == 'hadyek_helwan':
        await query.message.reply_text(text=lol_answers['ناسا_فرع_حدائق_حلوان'], parse_mode='HTML')
    elif choice == 'ismail':
        await query.message.reply_text(text=lol_answers['Innova_center'], parse_mode='HTML')
    elif choice == 'qalyoub':
        await query.message.reply_text(text=lol_answers['أكاديمية_التفوق_قليوب'], parse_mode='HTML')
    elif choice == 'benha':
        await query.message.reply_text(text=lol_answers['أكاديمية_التفوق_الفلل'], parse_mode='HTML')
    elif choice == 'assuit':
        await query.message.reply_text(text=lol_answers['مكتبة_جورج'], parse_mode='HTML')
    elif choice == 'red_sea_hurgada':
        await query.message.reply_text(text=lol_answers['مكتبة_الميناء_السقالة'], parse_mode='HTML')
    elif choice == 'gharbia_tanta':
        await query.message.reply_text(text=lol_answers['مكتبة_الدحيح'], parse_mode='HTML')
    elif choice == 'suez':
        await query.message.reply_text(text=lol_answers['داخل_مكتبة_الشاطر_fullmark_Center'], parse_mode='HTML')
    elif choice == 'menofia':
        await query.message.reply_text(text=lol_answers['الأكاديمية_السويسرية'], parse_mode='HTML')
    elif choice == 'zagazig':
        await query.message.reply_text(text=lol_answers['سنتر_المجد'], parse_mode='HTML')
    elif choice == 'qena':
        await query.message.reply_text(text=lol_answers['Community_Nook_مجتمع_نوك'], parse_mode='HTML')



    elif choice == 'scientific':
        issues = [
            [InlineKeyboardButton("Model Answers", callback_data='model_answers')],
            [InlineKeyboardButton("Roshetta", callback_data='roshetta')],
            [InlineKeyboardButton("Extra Sources", callback_data='extra_sources')],  
            [InlineKeyboardButton("PrescriptionTeam AI ", callback_data='scientific1')]

            
        ]
        reply_markup = InlineKeyboardMarkup(issues)
        await query.message.reply_text(text="Which option you need ?:", reply_markup=reply_markup)


    elif choice == 'scientific1':
        context.user_data['state'] = 'AWAITING_SCIENTIFIC_QUESTION'
        context.user_data.pop('choice', None)
        await query.message.reply_text(
            text="*تمام يا زوز، ابعتلي سؤالك  دلوقتي وأنا هجاوبك عليه.*",
            parse_mode=ParseMode.MARKDOWN
        )

    
    elif choice == 'model_answers':
        chapters = [
            [InlineKeyboardButton("Chapter 1 ", callback_data='chapter_1')],
            [InlineKeyboardButton("Chapter 2 ", callback_data='chapter_2')],
            [InlineKeyboardButton("Chapter 3 ", callback_data='chapter_3')],
            [InlineKeyboardButton("Chapter 4 ", callback_data='chapter_4')],
            [InlineKeyboardButton("Chapter 5 ", callback_data='chapter_5')],
            [InlineKeyboardButton("Latest one", callback_data='lastest')],
        ]
        reply_markup = InlineKeyboardMarkup(chapters)
        await query.message.reply_text(text="Which chapter ?:", reply_markup=reply_markup)

    elif choice == 'chapter_1':
        Lessons = [
            [InlineKeyboardButton("Lesson 1 ", callback_data='chapter_1_Lesson_1')],
            [InlineKeyboardButton("Lesson 2 ", callback_data='chapter_1_Lesson_2')],
            [InlineKeyboardButton("Lesson 3 ", callback_data='chapter_1_Lesson_3')],
            [InlineKeyboardButton("Lesson 4 ", callback_data='chapter_1_Lesson_4')],
            [InlineKeyboardButton("Lesson 5 ", callback_data='chapter_1_Lesson_5')],
        ]
        reply_markup = InlineKeyboardMarkup(Lessons)
        await query.message.reply_text(text="Which Lesson ?:", reply_markup=reply_markup)

    elif choice == 'chapter_2':
        Lessons = [
            [InlineKeyboardButton("Lesson 1 ", callback_data='chapter_2_Lesson_1')],
            [InlineKeyboardButton("Lesson 2 ", callback_data='chapter_2_Lesson_2')],
            [InlineKeyboardButton("Lesson 3 ", callback_data='chapter_2_Lesson_3')],
            [InlineKeyboardButton("Lesson 4 ", callback_data='chapter_2_Lesson_4')],
            [InlineKeyboardButton("Lesson 5 ", callback_data='chapter_2_Lesson_5')],
        ]
        reply_markup = InlineKeyboardMarkup(Lessons)
        await query.message.reply_text(text="Which Lesson ?:", reply_markup=reply_markup)

    elif choice == 'chapter_3':
        Lessons = [
            [InlineKeyboardButton("Lesson 1 ", callback_data='chapter_3_Lesson_1')],
            [InlineKeyboardButton("Lesson 2 ", callback_data='chapter_3_Lesson_2')],
            [InlineKeyboardButton("Lesson 3 ", callback_data='chapter_3_Lesson_3')],
            [InlineKeyboardButton("Lesson 4 ", callback_data='chapter_3_Lesson_4')],
            [InlineKeyboardButton("Lesson 5 ", callback_data='chapter_3_Lesson_5')],
        ]
        reply_markup = InlineKeyboardMarkup(Lessons)
        await query.message.reply_text(text="Which Lesson ?:", reply_markup=reply_markup)

    elif choice == 'chapter_4':
        Lessons = [
            [InlineKeyboardButton("Lesson 1 ", callback_data='chapter_4_Lesson_1')],
            [InlineKeyboardButton("Lesson 2 ", callback_data='chapter_4_Lesson_2')],
            [InlineKeyboardButton("Lesson 3 ", callback_data='chapter_4_Lesson_3')],
            [InlineKeyboardButton("Lesson 4 ", callback_data='chapter_4_Lesson_4')],
            [InlineKeyboardButton("Lesson 5 ", callback_data='chapter_4_Lesson_5')],
        ]
        reply_markup = InlineKeyboardMarkup(Lessons)
        await query.message.reply_text(text="Which Lesson ?:", reply_markup=reply_markup)

    elif choice == 'chapter_5':
        Lessons = [
            [InlineKeyboardButton("Lesson 1 ", callback_data='chapter_5_Lesson_1')],
            [InlineKeyboardButton("Lesson 2 ", callback_data='chapter_5_Lesson_2')],
            [InlineKeyboardButton("Lesson 3 ", callback_data='chapter_5_Lesson_3')],
            [InlineKeyboardButton("Lesson 4 ", callback_data='chapter_5_Lesson_4')],
            [InlineKeyboardButton("Lesson 5 ", callback_data='chapter_5_Lesson_5')],
            [InlineKeyboardButton("Lesson 6 ", callback_data='chapter_5_Lesson_6')],
            [InlineKeyboardButton("Lesson 7 ", callback_data='chapter_5_Lesson_7')],
            [InlineKeyboardButton("Lesson 8 ", callback_data='chapter_5_Lesson_8')],
            [InlineKeyboardButton("Lesson 9 ", callback_data='chapter_5_Lesson_9')],
            [InlineKeyboardButton("Lesson 10 ", callback_data='chapter_5_Lesson_10')]
        ]
        reply_markup = InlineKeyboardMarkup(Lessons)
        await query.message.reply_text(text="Which Lesson ?:", reply_markup=reply_markup)

    elif choice == 'chapter_1_Lesson_1':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 1 ch.1.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_1_Lesson_2':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 2 chapter  1.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_1_Lesson_3':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 3 chapter 1.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_1_Lesson_4':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 4 chapter  1 aa.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_1_Lesson_5':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 5 chapter  1.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_2_Lesson_1':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 1 chapter 2.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_2_Lesson_2':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 2 chapter 2.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_2_Lesson_3':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 3 chapter 2.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_2_Lesson_4':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 4 ch.2.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'chapter_2_Lesson_5':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer lesson 5 chapter 2.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))
    elif choice == 'lastest':
        pdf_file = os.path.join(config.PDF_DIR, 'Model answer Lesson 5 Chapter 3.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))

    elif choice == 'roshetta':
        chapters = [
            [InlineKeyboardButton("Batteries ", callback_data='batteries')],
            [InlineKeyboardButton("Iron", callback_data='iron')],
        ]
        reply_markup = InlineKeyboardMarkup(chapters)
        await query.message.reply_text(text="Which one ?:", reply_markup=reply_markup)

    elif choice == 'batteries':
        pdf_file = os.path.join(config.PDF_DIR, 'ch 4 batteries.pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))

    elif choice == 'iron':
        pdf_file = os.path.join(config.PDF_DIR, 'DOC-20230921-WA0187..pdf')
        await query.message.reply_document(document=open(pdf_file, 'rb'))

    elif choice == 'system':
        photo_paths = [os.path.join(config.PHOTO_DIR, f"image{i}.jpg") for i in range(1, 9)]
        media = [InputMediaPhoto(open(photo_path, 'rb')) for photo_path in photo_paths]
        await query.message.reply_text(text=lol_answers['system1'], parse_mode='HTML')
        await query.message.reply_media_group(media=media)

    elif choice == 'payment_method':
        await query.message.reply_text(text=lol_answers['payment_method1'], parse_mode='HTML')

    # Generic handler for choices that map directly to lol_answers
    elif choice in lol_answers:
        await query.message.reply_text(text=lol_answers[choice], parse_mode='HTML')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for general text messages."""
    user_state = context.user_data.get('state')
    user_question = update.message.text
    typing_task = None
    
    # --- Route to SCIENTIFIC CORE based on 'state' ---
    if user_state in ['AWAITING_SCIENTIFIC_QUESTION', 'AWAITING_SCIENTIFIC_FOLLOWUP']:
        try:
            start_time = datetime.now()
            typing_task = asyncio.create_task(
                send_typing_periodically(context, update.effective_chat.id)
            )
            
            # Handle scientific follow-up questions
            if user_state == 'AWAITING_SCIENTIFIC_FOLLOWUP':
                intent = await scientific_core_instance.classify_followup(user_question)

                if intent == 'thanks':
                    await update.message.reply_text(
                        "العفو يا زوز، تحت أمرك في أي وقت! لو عندك سؤال تاني ابعته عادي. 💪",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    context.user_data['state'] = 'AWAITING_SCIENTIFIC_QUESTION'
                    context.user_data.pop('last_scientific_question', None)
                    context.user_data.pop('last_scientific_answer', None)
                    context.user_data.pop('re_explain_count', None)
                    return

                elif intent == 're_explain':
                    re_explain_count = context.user_data.get('re_explain_count', 0)
                    
                    if re_explain_count >= 1:
                        await update.message.reply_text(
                            "أنا حاولت أشرحها بطريقتين مختلفتين. ممكن يكون أفضل تسأل حد من الـ assistants على الـ mini-group عشان يشرحهالك بشكل مباشر أكتر. هما هيساعدوك تفهم بالظبط الجزء اللي واقف معاك! 💙\n\nلو عندك سؤال تاني، ابعته عادي."
                        )
                        context.user_data['state'] = 'AWAITING_SCIENTIFIC_QUESTION'
                        context.user_data.pop('last_scientific_question', None)
                        context.user_data.pop('last_scientific_answer', None)
                        context.user_data.pop('re_explain_count', None)
                        return

                    context.user_data['re_explain_count'] = 1 
                    last_question = context.user_data.get('last_scientific_question')
                    last_answer = context.user_data.get('last_scientific_answer')

                    if last_question and last_answer:
                        new_explanation = await scientific_core_instance.re_explain_answer(last_question, last_answer)
                        
                        if typing_task:
                            typing_task.cancel()
                        
                        response_time = (datetime.now() - start_time).total_seconds()
                        interaction_id = database.log_scientific_interaction(
                            user_id=str(update.effective_user.id),
                            user_input=user_question + " [re-explain request]",
                            bot_response=new_explanation,
                            response_time=response_time
                        )
                        
                        # ADD FEEDBACK BUTTONS FOR RE-EXPLANATION
                        if interaction_id:
                            feedback_keyboard = [
                                [
                                    InlineKeyboardButton("👍", callback_data=f'feedback_like_{interaction_id}'),
                                    InlineKeyboardButton("👎", callback_data=f'feedback_dislike_{interaction_id}')
                                ]
                            ]
                            reply_markup = InlineKeyboardMarkup(feedback_keyboard)
                            await update.message.reply_text(new_explanation, reply_markup=reply_markup)
                        else:
                            await update.message.reply_text(new_explanation)
                        
                        context.user_data['last_scientific_answer'] = new_explanation
                        return
                    else:
                        await update.message.reply_text("معلش، الذاكرة عندي خانتني. ممكن تبعتلي السؤال تاني عشان أشرحهولك؟")
                        context.user_data['state'] = 'AWAITING_SCIENTIFIC_QUESTION'
                        return
            
            # Handle initial and new scientific questions 
            response_text, cached_id, transcribed_text = await scientific_core_instance.get_scientific_response_async(
                user_question=user_question
            )
            
            if typing_task:
                typing_task.cancel()
            
            # Log the scientific interaction
            response_time = (datetime.now() - start_time).total_seconds()
            interaction_id = database.log_scientific_interaction(
                user_id=str(update.effective_user.id),
                user_input=transcribed_text or user_question,
                bot_response=response_text,
                response_time=response_time,
                cached_question_id=cached_id
            )
            
            # ADD FEEDBACK BUTTONS FOR SCIENTIFIC RESPONSES
            if interaction_id:
                feedback_keyboard = [
                    [
                        InlineKeyboardButton("👍", callback_data=f'feedback_like_{interaction_id}'),
                        InlineKeyboardButton("👎", callback_data=f'feedback_dislike_{interaction_id}')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(feedback_keyboard)
                await update.message.reply_text(response_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(response_text)
            
            context.user_data['state'] = 'AWAITING_SCIENTIFIC_FOLLOWUP'
            context.user_data['last_scientific_question'] = transcribed_text or user_question
            context.user_data['last_scientific_answer'] = response_text
            context.user_data['re_explain_count'] = 0
            return
        finally:
            if typing_task:
                typing_task.cancel()

    # --- Route to ADMINISTRATIVE AI CORE based on 'choice' ---
    elif context.user_data.get('choice') == 'zoz_ai':
        try:
            typing_task = asyncio.create_task(
                send_typing_periodically(context, update.effective_chat.id)
            )
            
            bot_response_obj = await ai_core.get_bot_response_wrapper(
                update.message.text, 
                user_id=str(update.effective_user.id)
            )
            
            if typing_task:
                typing_task.cancel()

            # Send text response with feedback buttons
            if bot_response_obj.interaction_id:
                interaction_id = bot_response_obj.interaction_id
                feedback_keyboard = [
                    [
                        InlineKeyboardButton("👍", callback_data=f'feedback_like_{interaction_id}'),
                        InlineKeyboardButton("👎", callback_data=f'feedback_dislike_{interaction_id}')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(feedback_keyboard)
                await update.message.reply_text(bot_response_obj.text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(bot_response_obj.text)

            # NEW: Send response images if available
            if bot_response_obj.images and len(bot_response_obj.images) > 0:
                logger.info(f"Sending {len(bot_response_obj.images)} images with response")
                
                if len(bot_response_obj.images) == 1:
                    # Send single image
                    try:
                        with open(bot_response_obj.images[0], 'rb') as img:
                            await update.message.reply_photo(photo=img)
                    except Exception as e:
                        logger.error(f"Error sending single image: {e}")
                else:
                    # Send multiple images as media group
                    try:
                        media = []
                        for img_path in bot_response_obj.images[:10]: # Telegram limit: 10 images
                            if os.path.exists(img_path):
                                with open(img_path, 'rb') as img:
                                    # Reading the file content into memory
                                    media.append(InputMediaPhoto(media=img.read()))
                        
                        if media:
                            await update.message.reply_media_group(media=media)
                    except Exception as e:
                        logger.error(f"Error sending media group: {e}")
                        
        except Exception as e:
            logger.error(f"Error in Zoz Ai handler: {e}")
            await update.message.reply_text("An error occurred. Please try again.")
        finally:
            if typing_task:
                typing_task.cancel()

    # --- Handle Administrative Site Issues ---
    elif 'issue' in context.user_data:
        if context.user_data.get('awaiting_session', False):
            session_number = update.message.text
            context.user_data['session_number'] = session_number
            context.user_data['awaiting_session'] = False
            await update.message.reply_text("Now, please send your site code.")
        else:
            student_code = update.message.text
            issue_type = context.user_data['issue']
            session_number = context.user_data.get('session_number')

            try:
                # --- THIS IS THE FIX ---
                user_id = str(update.effective_user.id) # <-- GET THE USER ID
                database.create_site_issue(
                    user_id=user_id,                      # <-- PASS THE USER ID
                    issue_type=issue_type,
                    student_code=student_code,
                    session_number=session_number
                )
                logger.info(f"Saved issue to database: user={user_id}, type={issue_type}, code={student_code}, session={session_number}")
                # --- END OF FIX ---

                del context.user_data['issue']
                if 'session_number' in context.user_data:
                    del context.user_data['session_number']

                await update.message.reply_text("We have recorded your issue and details. We will fix your issue in 15 minutes.")
            except Exception as e:
                logger.error(f"Error processing and saving issue to database: {e}")
                await update.message.reply_text("An error occurred while processing your request. Please try again later.")

    else:
        await update.message.reply_text("Please select an option from the main menu by typing /start")


# ============================================================================
# MAIN PHOTO ROUTER
# ============================================================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Unified handler for all photo messages.
    Only accepts photos if user has selected a mode (Scientific or Zoz AI).
    Otherwise, prompts user to choose a mode first.
    """
    user_state = context.user_data.get('state')
    user_choice = context.user_data.get('choice')
    
    # ✅ Route to SCIENTIFIC handler if in scientific mode
    if user_state in ['AWAITING_SCIENTIFIC_QUESTION', 'AWAITING_SCIENTIFIC_FOLLOWUP']:
        await handle_scientific_photo(update, context)
        return
    
    # ✅ Route to ADMINISTRATIVE/SITE ISSUE handler if in zoz_ai mode
    if user_choice == 'zoz_ai':
        await handle_site_issue_photo(update, context)
        return
    
    # ❌ User hasn't selected a mode - prompt them to choose
    keyboard = [
        [InlineKeyboardButton("🔬 PrescriptionTeam AI (Scientific)", callback_data='scientific1')],
        [InlineKeyboardButton("⚙️ Zoz Ai (Administrative)", callback_data='zoz_ai')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "يا زوز، لازم تختار الأول إنت عايز تسأل عن إيه:\n\n"
        "🔬 *PrescriptionTeam AI* ← لو سؤال علمي  \n"
        "⚙️ *Zoz Ai* ← لو مشكلة إدارية أو في الموقع\n\n"
        "اختار من الأزرار اللي تحت، أو اضغط /start ",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


# ============================================================================
# SITE ISSUE PHOTO HANDLER (Administrative)
# ============================================================================

async def handle_site_issue_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle photos of site issues (administrative problems).
    Only called when user is in 'zoz_ai' mode.
    """
    typing_task = None
    full_save_path = None
    
    try:
        start_time = datetime.now()
        
        # Show typing indicator
        typing_task = asyncio.create_task(
            send_typing_periodically(context, update.effective_chat.id)
        )
        
        # Save the uploaded image
        upload_dir = os.path.join(config.ASSETS_DIR, 'site_issue_uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        photo_file = await update.message.photo[-1].get_file()
        filename = f"issue_{uuid.uuid4()}.jpg"
        full_save_path = os.path.join(upload_dir, filename)
        await photo_file.download_to_drive(full_save_path)
                
        # Create the relative path for the database
        db_image_path = os.path.join('site_issue_uploads', filename).replace('\\', '/')
        logger.info(f"Site issue image saved: {full_save_path}, DB path: {db_image_path}")
        
        
        # Analyze the image to identify the issue using Gemini Vision
        issue_type, response_data = await site_issue_handler.analyze_issue_image(full_save_path)
        
        if typing_task:
            typing_task.cancel()
        
        # Send the text response
        await update.message.reply_text(
            response_data["text"],
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send the solution images
        response_images = site_issue_handler.get_response_images_paths(issue_type)
        
        if response_images:
            if len(response_images) == 1:
                # Send single image
                with open(response_images[0], 'rb') as img:
                    await update.message.reply_photo(photo=img)
            else:
                # Send multiple images as media group (up to 10)
                media = []
                for img_path in response_images[:10]: # Telegram limit
                    with open(img_path, 'rb') as img:
                        media.append(InputMediaPhoto(media=img.read()))
                
                if media:
                    await update.message.reply_media_group(media=media)
        
        # Log the interaction
        response_time = (datetime.now() - start_time).total_seconds()
        
        
        # Use the caption as user_input, or a placeholder if no caption
        caption = update.message.caption or ""
        user_input_text = caption if caption else "[Image Question]" # Use caption or a generic placeholder

        interaction_id = database.log_interaction(
            user_id=str(update.effective_user.id),
            user_input=user_input_text, # <-- Use the new text
            bot_response=response_data["text"],
            intent="site_issue_image",
            response_type="image_recognition",
            confidence=0.9,
            response_time=response_time,
            image_path=db_image_path # <-- Pass the relative image path
        )
        
        
    except Exception as e:
        logger.error(f"Error handling site issue photo: {e}", exc_info=True)

# ============================================================================
# SCIENTIFIC PHOTO HANDLER (already exists, keeping for reference)
# ============================================================================

async def handle_scientific_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles photo messages when the user is in a scientific Q&A state."""
    user_state = context.user_data.get('state')
    typing_task = None

    if user_state in ['AWAITING_SCIENTIFIC_QUESTION', 'AWAITING_SCIENTIFIC_FOLLOWUP']:
        full_save_path = None
        try:
            start_time = datetime.now()
            typing_task = asyncio.create_task(
                send_typing_periodically(context, update.effective_chat.id)
            )

            upload_dir = os.path.join(config.ASSETS_DIR, 'scientific_question_images')
            os.makedirs(upload_dir, exist_ok=True)
            
            photo_file = await update.message.photo[-1].get_file()
            
            filename = f"{uuid.uuid4()}.jpg"
            full_save_path = os.path.join(upload_dir, filename)
            await photo_file.download_to_drive(full_save_path)
            
            db_image_path = os.path.join('scientific_question_images', filename).replace('\\', '/')

            logger.info(f"Photo downloaded to {full_save_path}, DB path set to {db_image_path}")
            
            #  Get transcribed text from scientific_core
            response_text, cached_id, transcribed_text = await scientific_core_instance.get_scientific_response_async(
                user_question=(update.message.caption or None), 
                image_path=full_save_path
            )

            if typing_task:
                typing_task.cancel()

            response_time = (datetime.now() - start_time).total_seconds()
            
            #  Store actual transcribed text, not placeholder!
            interaction_id = database.log_scientific_interaction(
                user_id=str(update.effective_user.id),
                user_input=transcribed_text or update.message.caption or "[Image Question]",
                bot_response=response_text,
                image_path=db_image_path,
                response_time=response_time,
                cached_question_id=cached_id
            )
            
            # ADD FEEDBACK BUTTONS FOR IMAGE QUESTIONS
            if interaction_id:
                feedback_keyboard = [
                    [
                        InlineKeyboardButton("👍", callback_data=f'feedback_like_{interaction_id}'),
                        InlineKeyboardButton("👎", callback_data=f'feedback_dislike_{interaction_id}')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(feedback_keyboard)
                await update.message.reply_text(response_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(response_text)
            
            context.user_data['state'] = 'AWAITING_SCIENTIFIC_FOLLOWUP'
            context.user_data['last_scientific_question'] = transcribed_text or update.message.caption or "[Question from image]"
            context.user_data['last_scientific_answer'] = response_text
            context.user_data['re_explain_count'] = 0

        except Exception as e:
            logger.error(f"Error handling scientific photo: {e}")
            await update.message.reply_text("An error occurred while processing the image. Please try again.")
        finally:
            if typing_task:
                typing_task.cancel()
    else:
        await update.message.reply_text("If this is a scientific question, please select the 'Scientific' option from the /start menu first.")