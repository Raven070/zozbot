import os
import json
import asyncio
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from psycopg2.extras import DictCursor

from redis_client import redis_conn, BOT_STATE_KEY
import database
import utils
from config import GENAI_API_KEY, TEACHER_NAME, SUPPORT_CONTACT, VECTOR_STORE_DIR

# Define Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# === ENHANCED DATA STRUCTURES ===
@dataclass
class BotResponse:
    """A structured class for all bot responses."""
    text: str
    images: List[str] = None
    confidence: float = 0.0
    intent: str = ""
    response_type: str = "text"
    interaction_id: int = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        self.images = self.images or []
        self.metadata = self.metadata or {}

@dataclass
class ConversationContext:
    """Manages the state of a conversation with a specific user."""
    user_id: str
    chat_history: List[Dict[str, str]]
    session_start: datetime = None
    
    def __post_init__(self):
        if self.session_start is None:
            self.session_start = datetime.now()

# === BOT STATE MANAGEMENT ===

def is_bot_enabled() -> bool:
    """Check if bot is enabled via Redis."""
    state = redis_conn.get(BOT_STATE_KEY)
    if state is None:
        return True # Default to ON
    return state == 'true'

# === DATABASE-BASED CORRECTION SYSTEM ===

def get_correction_for_input(user_input: str, user_id: str) -> Optional[str]:
    """Get correction directly from the PostgreSQL database for a specific user and input pattern."""
    conn = None
    try:
        conn = database.get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Method 1: Direct exact match on corrected interactions
            exact_match_query = """
                SELECT corrected_text 
                FROM interactions 
                WHERE user_id = %s 
                  AND user_input = %s 
                  AND is_corrected = TRUE 
                  AND corrected_text IS NOT NULL
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            cursor.execute(exact_match_query, (user_id, user_input))
            result = cursor.fetchone()
            if result and result['corrected_text']:
                return result['corrected_text']
            
            # Method 2: Fuzzy match on similar inputs (if exact match fails)
            # Note: This uses SQL LIKE which is very basic.
            similar_match_query = """
                SELECT user_input, corrected_text, 
                       (CASE 
                        WHEN user_input = %s THEN 1.0
                        WHEN user_input LIKE '%%' || %s || '%%' OR %s LIKE '%%' || user_input || '%%' THEN 0.8
                        ELSE 0.0
                       END) as similarity_score
                FROM interactions 
                WHERE user_id = %s 
                  AND is_corrected = TRUE
                  AND corrected_text IS NOT NULL
                ORDER BY similarity_score DESC, timestamp DESC
                LIMIT 1
            """
            cursor.execute(similar_match_query, (user_input, user_input, user_input, user_id))
            result = cursor.fetchone()
            if result and result['corrected_text'] and result['similarity_score'] > 0.7:
                return result['corrected_text']
                
    except Exception as e:
        utils.logger.error(f"Error getting correction from database: {e}")
    finally:
        if conn:
            conn.close()
    
    return None

# === ENHANCED AI CORE CLASS ===

class EnhancedAICore:
    """Professional AI Core with database-based correction system."""
    
    def __init__(self):
        self.logger = utils.logger
        self.local_knowledge_base = utils.load_local_knowledge()
        self.models = self._initialize_models()
        self.vector_store = self._initialize_vector_store()
        self.conversation_contexts = {}
        self.faq_with_images = self._load_faqs_with_images()

    def _initialize_vector_store(self):
        """Initializes the FAISS vector store from the local index."""
        try:
            vector_store_path = os.path.join(VECTOR_STORE_DIR, "faqs_index")
            if not os.path.exists(vector_store_path):
                self.logger.error(f"FAISS index not found in {VECTOR_STORE_DIR}. Please run knowledge_processor.py first.")
                return None
            
            embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=GENAI_API_KEY)
            vector_store = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
            self.logger.info("FAISS Vector Store initialized successfully.")
            return vector_store
            
        except Exception as e:
            self.logger.error(f"Error initializing vector store: {e}", exc_info=True)
            return None

    def _initialize_models(self) -> Dict:
        """Initialize all AI models (LLM)."""
        models = {}
        try:
            genai.configure(api_key=GENAI_API_KEY)
            models['gemini'] = genai.GenerativeModel('gemini-2.5-flash')
            self.logger.info("Gemini model initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing models: {e}", exc_info=True)
        return models
    
    # --- CORE RESPONSE LOGIC WITH DATABASE CORRECTIONS ---

    async def get_enhanced_response(self, user_input: str, user_id: str) -> BotResponse:
        """Main method to get bot responses with image support."""
        if not is_bot_enabled():
            return BotResponse(
                text="Bot is currently offline for maintenance. Please try again later.",
                confidence=1.0,
                intent="bot_disabled",
                response_type="system_message"
            )

        start_time = datetime.now()
        context = self.conversation_contexts.get(user_id, ConversationContext(user_id=user_id, chat_history=[]))
        
        response = None
        try:
            # 1. Check for manual correction
            corrected_response = get_correction_for_input(user_input, user_id)
            if corrected_response:
                response = BotResponse(
                    text=corrected_response,
                    confidence=1.0,
                    intent="database_correction",
                    response_type="corrected_response"
                )

            # 2. Try RAG 
            if not response:
                rag_response = self._get_rag_response_with_images(user_input)
                if rag_response:
                    response = rag_response
            
            # 3. LLM fallback
            if not response:
                response = await self._get_gemini_fallback_response(user_input, context)

        except Exception as e:
            self.logger.error(f"Error in get_enhanced_response: {e}", exc_info=True)
            response = BotResponse(
                text="An error occurred. Please try again.",
                confidence=0.0, intent="error", response_type="fallback"
            )

        response_time = (datetime.now() - start_time).total_seconds()
        interaction_id = database.log_interaction(
            user_id=user_id,
            user_input=user_input,
            bot_response=response.text,
            intent=response.intent,
            response_type=response.response_type,
            confidence=response.confidence,
            response_time=response_time
        )
        response.interaction_id = interaction_id
        
        self._update_context(context, user_input, response.text)
        
        return response

    def _get_rag_response_with_confidence(self, user_input: str, threshold=0.7) -> Optional[BotResponse]:
        if not self.vector_store:
            return None

        try:
            results_with_scores = self.vector_store.similarity_search_with_score(user_input, k=1)
            
            if not results_with_scores:
                return None
            
            best_doc, score = results_with_scores[0]
            # FAISS returns L2 distance, so a lower score is better. We convert it to a similarity score.
            similarity = 1.0 / (1.0 + score) 

            self.logger.info(f"RAG search for '{user_input[:30]}...' -> Best match with similarity: {similarity:.4f}")

            if similarity >= threshold:
                content = best_doc.page_content
                answer = content.split('A: ')[-1] if 'A: ' in content else content
                
                return BotResponse(
                    text=answer.strip(),
                    confidence=similarity,
                    intent="rag_high_confidence",
                    response_type="knowledge_base"
                )
        except Exception as e:
            self.logger.error(f"Error in RAG search: {e}", exc_info=True)
        
        return None

    # --- NEW METHODS FOR IMAGE SUPPORT ---

    def _load_faqs_with_images(self) -> dict:
        """Load FAQs that include image paths."""
        faq_dict = {}
        try:
            faq_dir = os.path.join(BASE_DIR, 'knowledge_base', 'faqs')
            
            for filename in os.listdir(faq_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(faq_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        faqs = json.load(f)
                        
                        for faq in faqs:
                            question = faq.get('question', '').lower()
                            # Store the full FAQ entry including images
                            faq_dict[question] = {
                                'answer': faq.get('answer', ''),
                                'images': faq.get('images', [])
                            }
            
            self.logger.info(f"Loaded {len(faq_dict)} FAQs with potential images")
            return faq_dict
            
        except Exception as e:
            self.logger.error(f"Error loading FAQs with images: {e}")
            return {}

    def _get_rag_response_with_images(self, user_input: str, threshold=0.7) -> Optional[BotResponse]:
        """Enhanced RAG search that includes images in responses."""
        if not self.vector_store:
            return None

        try:
            results_with_scores = self.vector_store.similarity_search_with_score(user_input, k=1)
            
            if not results_with_scores:
                return None
            
            best_doc, score = results_with_scores[0]
            similarity = 1.0 / (1.0 + score)

            self.logger.info(f"RAG search for '{user_input[:30]}...' -> similarity: {similarity:.4f}")

            if similarity >= threshold:
                content = best_doc.page_content
                
                # Extract question from content
                question_part = content.split('A: ')[0].strip() if 'A: ' in content else content
                answer_part = content.split('A: ')[-1].strip() if 'A: ' in content else content
                
                # Check if this FAQ has associated images
                images = []
                for q, data in self.faq_with_images.items():
                    if q in question_part.lower() or question_part.lower() in q:
                        images = data.get('images', [])
                        # Use the full answer from the FAQ if it has images
                        if images:
                            answer_part = data.get('answer', answer_part)
                        break
                
                # Convert relative image paths to absolute paths
                full_image_paths = []
                if images:
                    base_path = os.path.join(BASE_DIR, 'assets')
                    for img_path in images:
                        full_path = os.path.join(base_path, img_path)
                        if os.path.exists(full_path):
                            full_image_paths.append(full_path)
                        else:
                            self.logger.warning(f"Image not found: {full_path}")
                
                return BotResponse(
                    text=answer_part,
                    images=full_image_paths,
                    confidence=similarity,
                    intent="rag_high_confidence",
                    response_type="knowledge_base_with_images" if full_image_paths else "knowledge_base"
                )
        except Exception as e:
            self.logger.error(f"Error in RAG search with images: {e}", exc_info=True)
        
        return None

    # --- FALLBACK AND UTILITY METHODS ---

    async def _get_gemini_fallback_response(self, user_input: str, context: ConversationContext) -> BotResponse:
        chat_history = self._format_chat_history(context.chat_history)
        prompt = f"""
# Role and Persona
You are "Zoz AI", the specialized and professional AI assistant for Dr. {TEACHER_NAME}'s chemistry students. Your persona is supportive, motivational, and highly helpful. Address students in a friendly and respectful Egyptian Arabic dialect.

# Primary Task
Your main job is to answer student questions accurately and concisely based ONLY on the provided Context below. Do not use any external information.

# Provided Context
---
{self.local_knowledge_base}
---

# Conversation History
---
{chat_history}
---

# Strict Rules
1. **Never answer academic or scientific questions about chemistry.** If asked, politely refuse and direct them to the mini-groups or the teacher:
   "سؤالك العلمي ممتاز يا بطل، والمكان الأفضل لإجابته هو مع {TEACHER_NAME} أو المساعدين في الـ mini group عشان تاخد إجابة دقيقة ومتكاملة. أنا هنا لأي استفسار إداري أو دعم نفسي."
2. **If the Provided Context does not contain an answer to the user's question**, state that you do not have this information and provide the support link:
   "للأسف معنديش المعلومة الدقيقة دي حالياً، أفضل حاجة تتواصل مع فريق الدعم على اللينك ده وهم هيساعدوك فوراً: {SUPPORT_CONTACT}"
3. Keep your answers concise and directly related to the user's question.
4. If the question is ambiguous, ask for clarification in a friendly way.
5. Be kind with the students and talk with them as you are their friend and start your words by 'يا زوز'.

## ðŸš¨ CRITICAL FORMATTING RULES ðŸš¨

### THIS IS FOR TELEGRAM 
âŒ ABSOLUTELY FORBIDDEN:  Asterisks: *, **, * item 

Use plain text only


# Student's Question
{user_input}

# Your Answer (in Egyptian Arabic PLAIN TEXT ONLY , NO asterisks ):
"""
        try:
            response = await self.models['gemini'].generate_content_async(
                prompt,
                generation_config={'temperature': 0.6}
            )
            response_text = response.text or "I was unable to find an answer."
            confidence = 0.4 # Confidence is lower as it's a fallback
            
            return BotResponse(
                text=response_text, confidence=confidence,
                intent="gemini_fallback", response_type="llm_generated"
            )
        except Exception as e:
            self.logger.error(f"Error in Gemini fallback response: {e}")
            return BotResponse(
                text="An error occurred. Please try again.",
                confidence=0.0, intent="error", response_type="fallback"
            )

    # --- Utility Methods ---
    def _format_chat_history(self, chat_history: List[Dict[str, str]], max_length: int = 4) -> str:
        if not chat_history: return "No previous conversation history."
        recent_history = chat_history[-max_length:]
        formatted = [f"Student: {ex.get('user', '')}\nAssistant: {ex.get('bot', '')}" for ex in recent_history]
        return '\n'.join(formatted)

    def _update_context(self, context: ConversationContext, user_input: str, bot_response: str):
        context.chat_history.append({'user': user_input, 'bot': bot_response, 'timestamp': datetime.now().isoformat()})
        if len(context.chat_history) > 10:
            context.chat_history.pop(0)
        self.conversation_contexts[context.user_id] = context

# === SINGLETON INSTANCE ===
enhanced_ai_core = EnhancedAICore()

# === BACKWARD COMPATIBILITY FUNCTION ===
async def get_bot_response_wrapper(user_input: str, user_id: str) -> BotResponse:
    """Backward compatible wrapper for existing code, now returning the full response object."""
    response = await enhanced_ai_core.get_enhanced_response(user_input, user_id=user_id)
    return response