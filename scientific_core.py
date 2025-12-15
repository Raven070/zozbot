import os
import logging
import json
import hashlib
import asyncio
import time  # <-- ADDED FOR RETRY DELAY
from google.api_core.exceptions import ResourceExhausted  # <-- ADDED FOR 429 ERROR
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from sentence_transformers import CrossEncoder
from config import VECTOR_STORE_DIR, SCIENTIFIC_GENAI_API_KEY
import PIL.Image
from enhanced_question_deduplication import deduplicator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for the fallback messages
FALLBACK_NO_INFO = "يا زوز، سؤالك كويس جدا بس الإجابة مش موجودة بشكل مباشر في المحتوى اللي معايا. ممكن تسأل دكتور ناصر في الـ mini-group عشان تاخد إجابة دقيقة."
FALLBACK_ERROR = "معلش يا زوز، حصلت مشكلة وأنا بحاول أجاوب. ممكن تحاول تاني؟"

# --- Unified Persona and Style Guide ---
PERSONA_GUIDE = """
## ROLE AND PERSONA
You are "Zoz the Scientist," an AI Chemistry Tutor for Egyptian Thanaweya Amma students. You are a friendly, empathetic teaching assistant who thinks through problems WITH the student.

VERYYYY IMPORTANNTTTTTT
- **ALWAYS** use English terms like: 'compound', 'ions', 'electrons', 'oxidation state', 'charge', 'energy levels', 'orbitals', 'configuration', 'element', 'series', 'atomic number' , etc .
- NEVER NEVER NEVER USE ANY CHEMICAL EXPRESSION IN ARABIC LANGUAGE like : "العدد الذري" , "عنصر انتقالي" , "الجدول الدروي"

**ALWAYS BEGIN WITH "دا سؤال جميل تعالى نفكر فيه سوا"

## BEHAVIORAL STYLE (Adapt to the situation)
Based on the student's question, adopt ONE of the following conversational styles. Do not mix them unnaturally in a single response
- **The "Let's Think Together" Style:** Use for multi-step problems. (e.g., "تعالى نفهم ايه فكرة السؤال اصلا يا زوز مع بعض...")
- **The "Socratic / Guiding" Style:** Use when the problem is straightforward to guide the student. (e.g., "انا كدة ساعدتك شوية تلقط السؤال ، تقدر انت بقى تقوليلي الاجابة هتبقى ايه ❤؟")
- **The "Empathetic / Reassuring" Style:** Use when a question is tricky or contains a trap. (e.g., "هو فعلا معاكي حق... بس هو ساعات قليلة بيحشر الZn وسط الاختيارات... متخافيش يعني...")
- **The "Conceptual Explanation" Style:** Use for explaining core concepts. (e.g., "الElement X زي ما واضح هو يقدر يعمل lose ل five electrons بس طب احنا عرفنا منين؟...")

### EXTEREMLY IMPORTANNTTTTTT --> MAKE THE ANSWER WELL ORGANIZED AND DO NOT WRITE ENGLISH AND ARABIC WORDS IN THE SAME LINE BECUASE IT IS REFLECTED AND THIS SO ANNOYINGG ❌❌❌ 

## 🚨 CRITICAL FORMATTING RULES 🚨

### THIS IS FOR TELEGRAM - NO LaTeX SUPPORT!

❌ ABSOLUTELY FORBIDDEN:
- Dollar signs: $...$
- LaTeX subscripts: K_2Cr_2O_7
- LaTeX superscripts: Ni^{+4}
- LaTeX brackets: $[Ar] 3d^8$
- Asterisks: *, **, * item

✅ REQUIRED FORMAT:
- Plain text: K₂Cr₂O₇ (not $K_2Cr_2O_7$)
- Plain text: Ni+⁴ (not $Ni^{+4}$)
- Plain text: [Ar] 3d⁶ (not $[Ar] 3d^6$)
- Plain text: 4s² 3d⁶ (not $4s^2 3d^6$)
- Plain text: Fe+³ (not $Fe^{+3}$)
- Plain text: Zn (not $_{30}Zn$)

### CORRECT EXAMPLE:
```
دا سؤال جميل تعالى نفكر فيه سوا

طيب تعالى نشوف:

1. ال element X ده هو Iron
ال electronic configuration بتاعه [Ar] 4s² 3d⁶

2. ال element Y ده هو Cobalt
ال configuration بتاعه [Ar] 4s² 3d7

3. لما نشوف ال oxidation states
ال Iron في XO2 هيبقى Fe+⁴
ال configuration بتاعه هيبقى [Ar] 3d⁴
```

### WRONG EXAMPLE (NEVER DO THIS):
```
* X هو Iron ($Fe$), configuration $[Ar] 4s^2 3d^6$
* Y هو Cobalt ($Co$), configuration $[Ar] 4s^2 3d^7$
```

### LINE BREAKS:
- Use line breaks, and spcae between sections
"""


class ScientificCore:
    """
    Enhanced Scientific Core with CORRECTED Caching Logic.
    
    NEW BEHAVIOR:
    - DO NOT cache answers immediately
    - Only check cache for APPROVED answers
    - Cache only happens when admin approves/corrects in dashboard
    - All data persists in PostgreSQL database
    """
    
    def __init__(self):
        """Initialize the scientific core with all necessary components."""
        self.model = self._initialize_model()
        self.vector_store = self._initialize_vector_store()
        self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        
        if not self.vector_store or not self.model:
            logger.error("Scientific core is not fully available.")
        else:
            logger.info("Scientific core initialized - Cache-on-approval mode enabled")

    def _initialize_model(self):
        """Initialize the Gemini 2.0 Flash model."""
        try:
            genai.configure(api_key=SCIENTIFIC_GENAI_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("Gemini 2.0 Flash model initialized successfully")
            return model
        except Exception as e:
            logger.error(f"Error initializing scientific Gemini model: {e}", exc_info=True)
            return None

    def _initialize_vector_store(self):
        """Initialize the FAISS vector store for scientific knowledge."""
        try:
            vector_store_path = os.path.join(VECTOR_STORE_DIR, "scientific_index")
            if not os.path.exists(vector_store_path):
                logger.error(f"Scientific vector index not found at {vector_store_path}")
                return None
            
            embeddings = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004", 
                google_api_key=SCIENTIFIC_GENAI_API_KEY
            )
            vector_store = FAISS.load_local(
                vector_store_path, 
                embeddings, 
                allow_dangerous_deserialization=True
            )
            logger.info("Scientific vector store loaded successfully")
            return vector_store
        except Exception as e:
            logger.error(f"Error initializing scientific vector store: {e}", exc_info=True)
            return None

    def _compute_image_hash(self, image_path: str) -> str:
        """Compute SHA-256 hash of an image file for exact duplicate detection."""
        try:
            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            logger.debug(f"Computed image hash: {file_hash[:16]}...")
            return file_hash
        except Exception as e:
            logger.error(f"Error computing image hash: {e}")
            return None

    def _retrieve_and_rerank(self, question: str, top_k=8):
        """Retrieve relevant documents and rerank them using cross-encoder."""
        retrieved_docs = self.vector_store.similarity_search(question, k=20)
        
        if not retrieved_docs:
            logger.warning("No documents retrieved from vector store")
            return []
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents from vector store")
        
        # Rerank with cross-encoder
        pairs = [[question, doc.page_content] for doc in retrieved_docs]
        scores = self.reranker.predict(pairs)
        
        doc_scores = list(zip(retrieved_docs, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        top_docs = [doc for doc, score in doc_scores[:top_k]]
        logger.info(f"Reranked to top {len(top_docs)} documents")
        
        return top_docs

    def _relevance_gate(self, question: str, context_docs: list) -> bool:
        """Relevance gate to determine if context is sufficient to answer the question."""
        if not context_docs:
            logger.warning("Relevance gate: No context documents provided")
            return False

        context = "\n\n---\n\n".join([doc.page_content for doc in context_docs])

        prompt = f"""
        You are an expert gatekeeper. Your task is to determine if the provided context has enough information to answer the user's question.

        **User Question:**
        "{question}"

        **Provided Context:**
        ---
        {context}
        ---

        **Your Analysis:**
        1.  Read the user's question to understand what specific information is needed.
        2.  Carefully read the provided context to see if that information is present, even if it requires a calculation based on the context's data (like finding oxidation states).
        3.  Provide your reasoning and a final decision in a JSON format.

        **JSON Output:**
        {{
          "reasoning": "A brief explanation of why the context is or is not sufficient.",
          "decision": "YES" or "NO"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                logger.warning("Relevance gate received empty response from Gemini")
                return False
            
            clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
            result = json.loads(clean_json_str)

            logger.info(f"Relevance Gate Reasoning: {result.get('reasoning')}")
            decision = result.get('decision', 'NO').upper() == 'YES'
            
            if decision:
                logger.info("✓ Relevance gate PASSED - Context is sufficient")
            else:
                logger.warning("✗ Relevance gate FAILED - Context is insufficient")
            
            return decision

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Relevance Gate could not parse JSON response: {e}")
            return False
        except Exception as e:
            logger.error(f"Relevance Gate encountered an unknown error: {e}")
            return False

    async def classify_followup(self, message: str) -> str:
        """Classify the intent of a follow-up message."""
        prompt = f"""
        You are an expert intent classifier. Analyze the user's message and determine its intent.
        The user has just received an answer to a scientific question.

        Possible intents are:
        - "thanks": The user is expressing gratitude or confirmation of understanding (e.g., "thanks", "shokran", "تمام فهمت", "got it").
        - "re_explain": The user is expressing confusion or asking for more clarification (e.g., "I don't understand", "مش فاهم", "explain again", "وضح تاني").
        - "new_question": The user is asking a completely new and different question.

        User Message: "{message}"

        Provide your answer in JSON format with a single key "intent".
        """
        try:
            response = await self.model.generate_content_async(prompt)
            
            if not response or not response.text:
                logger.warning("Follow-up classification received empty response")
                return "new_question"
            
            clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
            result = json.loads(clean_json_str)
            intent = result.get("intent", "new_question")
            logger.info(f"Follow-up intent classified as: {intent}")
            return intent
        except Exception as e:
            logger.error(f"Could not classify follow-up intent: {e}")
            return "new_question"

    async def re_explain_answer(self, original_question: str, previous_answer: str) -> str:
        """Generate a new explanation while maintaining the "Zoz the Scientist" persona."""
        prompt = f"""
        {PERSONA_GUIDE}


        ## TASK:
        Re-explain the concept using a different approach.
        - Start with: "تعالى نفكر في السؤال تاني"
        - Keep same persona
        - Break down steps more clearly
        - NO LaTeX, NO asterisks
        - Use plain text only
        
         - option a) [text]
           [explanation]
       
       - option b) [text]
           [explanation]

           
### EXTEREMLY IMPORTANNTTTTTT --> MAKE THE ANSWER WELL ORGANIZED AND DO NOT WRITE ENGLISH AND ARABIC WORDS IN THE SAME LINE BECUASE IT IS REFLECTED AND THIS SO ANNOYINGG ❌❌❌ 

## 🚨 CRITICAL FORMATTING RULES 🚨

### THIS IS FOR TELEGRAM - NO LaTeX SUPPORT!

❌ ABSOLUTELY FORBIDDEN:
- Dollar signs: $...$
- LaTeX subscripts: K_2Cr_2O_7
- LaTeX superscripts: Ni^{+4}
- LaTeX brackets: $[Ar] 3d^8$
- Asterisks: *, **, * item

✅ REQUIRED FORMAT:
- Plain text: K₂Cr₂O₇ (not $K_2Cr_2O_7$)
- Plain text: Ni+⁴ (not $Ni^{+4}$)
- Plain text: [Ar] 3d⁶ (not $[Ar] 3d^6$)
- Plain text: 4s² 3d⁶ (not $4s^2 3d^6$)
- Plain text: Fe+³ (not $Fe^{+3}$)
- Plain text: Zn (not $_{30}Zn$)

        ## CONTEXT:
        **Original Question:** "{original_question}"
        **Your Previous Answer:** "{previous_answer}"

        ## Your New Explanation (PLAIN TEXT ONLY - NO LaTeX, NO asterisks):
        """
        
        try:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            response = await self.model.generate_content_async(
                prompt,
                safety_settings=safety_settings
            )
            
            if not response or not response.text:
                return "حصل مشكلة وأنا بحاول أشرح تاني. ممكن تبعت السؤال مرة تانية؟"
            
            logger.info("Re-explanation generated successfully")
            return response.text
        except Exception as e:
            logger.error(f"Error during re-explanation: {e}")
            return "حصل مشكلة وأنا بحاول أشرح تاني. ممكن تبعت السؤال مرة تانية؟"

    def _extract_json(self, text: str) -> str:
        """Extract JSON object from text that might contain additional content."""
        import re
        
        text = text.replace("```json", "").replace("```", "")
        
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            for match in reversed(matches):
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue
        
        last_brace = text.rfind('{')
        if last_brace != -1:
            potential_json = text[last_brace:]
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass
        
        return ""

    async def get_scientific_response_async(
        self, 
        user_question: str = None, 
        image_path: str = None
        
    ) -> tuple:
        
        if not self.vector_store or not self.model:
            logger.error("Scientific core not available")
            return FALLBACK_ERROR, None, None

        transcribed_question = None
        image_hash = None
        cached_question_id = None

        # ========================================
        # STEP 1: IMAGE TRANSCRIPTION (if provided)
        # ========================================
        if image_path:
            try:
                logger.info(f"📸 Processing image at {image_path}")
                
                # CRITICAL FIX: Compute hash from the ACTUAL file that was just saved
                image_hash = self._compute_image_hash(image_path)
                if image_hash:
                    logger.info(f"🔒 Computed image hash: {image_hash[:16]}...")
                else:
                    logger.warning("⚠️ Failed to compute image hash")
                
                img = PIL.Image.open(image_path)
                
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                
                # --- NEW RETRY LOGIC for 429 ResourceExhausted ---
                max_retries = 3
                base_delay_seconds = 2
                transcribed_question = None

                for attempt in range(max_retries):
                    try:
                        transcription_response = self.model.generate_content(
                            [
                                "Please transcribe the following chemistry question from the image. "
                                "Extract all text, including choices. Be consistent and precise and if is there side notes written by a student please neglect it (do not transcribe the side notes)", 
                                img
                            ],
                            safety_settings=safety_settings
                        )
                        
                        if not transcription_response or not transcription_response.text:
                            logger.error("Image transcription returned empty response")
                            # Don't retry on empty, just fail
                            return "معلش يا زوز، مقدرتش أقرأ الصورة اللي بعتها. ممكن تتأكد إنها واضحة وتبعتها تاني؟", None, None
                        
                        transcribed_question = transcription_response.text
                        logger.info(f"✓ Transcribed: '{transcribed_question[:100]}...'")
                        user_question = transcribed_question
                        break  # --- SUCCESS, exit retry loop ---

                    except ResourceExhausted as e:
                        if attempt < max_retries - 1:
                            # Exponential backoff: 2s, 4s, 8s
                            wait_time = base_delay_seconds * (2 ** attempt) 
                            logger.warning(f"Rate limit hit (429). Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                            time.sleep(wait_time) # Use time.sleep since generate_content is synchronous
                        else:
                            logger.error(f"✗ Failed to transcribe image after {max_retries} attempts due to rate limiting.")
                            raise e # Re-raise the final exception to be caught by the outer block
                # --- END RETRY LOGIC ---

                if not transcribed_question:
                    # This should only happen if the loop fails without an exception
                    raise Exception("Transcription failed after retries.")
                
            except Exception as e:
                logger.error(f"✗ Error processing image: {e}", exc_info=True)
                return "معلش يا زوز، مقدرتش أقرأ الصورة اللي بعتها. ممكن تتأكد إنها واضحة وتبعتها تاني؟", None, None

        if not user_question:
            logger.error("No question provided")
            return FALLBACK_ERROR, None, None

        # ========================================
        # STEP 2: CHECK CACHE - FIXED LOGIC
        # ========================================
        logger.info("🔍 Checking cache for APPROVED/CORRECTED answers...")
        
        # PRIORITY 1: Check by image hash first (most reliable)
        if image_hash:
            logger.info(f"🔍 Searching cache by image hash: {image_hash[:16]}...")
            similar_question = await deduplicator.find_similar_question(
                question_text=user_question,
                image_hash=image_hash
            )
            
            if similar_question and similar_question.get('is_corrected'):
                logger.info(
                    f"✓ CACHE HIT (IMAGE HASH)! Returning APPROVED answer "
                    f"(ID: {similar_question['id']}, used {similar_question['times_used']} times)"
                )
                cached_response = similar_question['answer_text']
                cached_question_id = similar_question['id']
                return cached_response, cached_question_id, user_question
            elif similar_question:
                logger.info(
                    f"ℹ️ Image hash match found (ID: {similar_question['id']}) "
                    f"BUT NOT YET APPROVED - processing normally"
                )
        else:
            # PRIORITY 2: Text-based search (for text-only questions)
            logger.info("🔍 No image - searching cache by text similarity...")
            similar_question = await deduplicator.find_similar_question(
                question_text=user_question,
                image_hash=None
            )
            
            if similar_question and similar_question.get('is_corrected'):
                logger.info(
                    f"✓ CACHE HIT (TEXT)! Returning APPROVED answer "
                    f"(ID: {similar_question['id']}, used {similar_question['times_used']} times)"
                )
                cached_response = similar_question['answer_text']
                cached_question_id = similar_question['id']
                return cached_response, cached_question_id, user_question
            elif similar_question:
                logger.info(
                    f"ℹ️ Similar question found (ID: {similar_question['id']}) "
                    f"BUT NOT YET APPROVED - processing normally"
                )

        # ========================================
        # STEP 3: NO APPROVED CACHE - PROCESS WITH RAG
        # ========================================
        logger.info("✗ No approved cache hit - processing with RAG pipeline")
        logger.info(f"📚 Starting retrieval for: '{user_question[:50]}...'")
        
        reranked_docs = self._retrieve_and_rerank(user_question)

        if not self._relevance_gate(user_question, reranked_docs):
            logger.warning("✗ Relevance gate failed")
            # Use transcribed_question if available, fall back to user_question
            return FALLBACK_NO_INFO, None, transcribed_question or user_question

        logger.info("✓ Relevance gate passed - generating answer")
        
        context_with_ids = "\n\n".join([
            f"Source ID: {doc.metadata['source_id']}\nContent: {doc.page_content}" 
            for doc in reranked_docs
        ])

        # ========================================
        # STEP 4: GENERATE ANSWER
        # ========================================
        generation_prompt = f"""
        {PERSONA_GUIDE}

        
        ## CRITICAL FORMATTING RULES FOR "final_answer":
        1. Start with: "دا سؤال جميل تعالى نفكر فيه سوا" on its own line
        2. Add a blank line after the opening
        3. Use proper paragraph breaks (\\n\\n) between major sections
        4. When listing options, use this EXACT format with proper spacing:
       طيب، تعال نشوف ال options اللي عندنا:
       
       - option a) [text]
           [explanation]
       
       - option b) [text]
           [explanation]



### EXTEREMLY IMPORTANNTTTTTT --> MAKE THE ANSWER WELL ORGANIZED AND DO NOT WRITE ENGLISH AND ARABIC WORDS IN THE SAME LINE BECUASE IT IS REFLECTED AND THIS SO ANNOYINGG ❌❌❌ 


        ## 🚨🚨🚨 TELEGRAM FORMAT - NO LaTeX 🚨🚨🚨

        BEFORE WRITING ANYTHING:
        1. ❌ NO dollar signs ($) anywhere
        2. ❌ NO subscripts with underscores (K_2)
        3. ❌ NO superscripts with carets (^2)
        4. ❌ NO asterisks (*) for bullets or bold
        5. ❌ NO LaTeX brackets: $[Ar] 3d^8$
        6. ✅ ONLY plain text: K₂Cr₂O₇, Ni+⁴, [Ar] 3d⁸, Fe+³, 4s2 3d⁸

        ## CORRECT JSON EXAMPLE:
        {{
          "final_answer": "دا سؤال جميل تعالى نفكر فيه سوا\\n\\nطيب تعالى نشوف:\\n\\n1. ال element X ده\\nال electronic configuration بتاعه [Ar] 4s2 3d6\\nلما يفقد 4 electrons هيبقى [Ar] 3d4\\n\\n2. ال element Y ده\\nال configuration بتاعه [Ar] 4s2 3d7\\nلما يفقد 3 electrons هيبقى [Ar] 3d6\\n\\nيبقى الاختيار الصح هو رقم 2",
          "sources": ["Chapter1-chunk5"]
        }}

        ## WRONG JSON EXAMPLE (NEVER DO THIS):
        {{
          "final_answer": "* X هو $Fe$, configuration $[Ar] 4s^2 3d^6$\\n* Y هو $Co$"
        }}

        ## TASK:
        Answer the student's question using ONLY the provided Curriculum Content.
        - Output MUST be JSON with "final_answer" and "sources"
        - Use ONLY plain text in final_answer (NO LaTeX, NO asterisks)
        - Start with: "دا سؤال جميل تعالى نفكر فيه سوا"
        - Use line breaks, and spcae between sections
        - NEVER mention Source IDs in the final answer
        - Write chemical formulas in plain text: Fe+³, [Ar] 3d⁸, K₂Cr₂O₇

        
        ---
        ## Curriculum Content
        {context_with_ids}
        ---

        ## Student's Question
        {user_question}

        ## Your JSON Output (PLAIN TEXT ONLY - NO $, NO LaTeX, NO asterisks):
        """

        try:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            response = self.model.generate_content(
                generation_prompt,
                safety_settings=safety_settings
            )

            if not response or not response.text:
                logger.error("Generation response empty or blocked")
                return FALLBACK_ERROR, None, transcribed_question or user_question

            response_text = response.text.strip()
            
            if not response_text:
                logger.error("Response text empty")
                return FALLBACK_ERROR, None, transcribed_question or user_question
            
            json_str = self._extract_json(response_text)
            
            if not json_str:
                logger.error("Could not extract JSON from response")
                return FALLBACK_ERROR, None, transcribed_question or user_question
            
            result = json.loads(json_str)
            final_answer = result.get("final_answer", "")
            sources = result.get("sources", [])
            
            if not final_answer:
                logger.warning("Final answer empty")
                return FALLBACK_NO_INFO, None, transcribed_question or user_question
            
            logger.info(f"✓ Answer generated ({len(final_answer)} chars)")
            
            # ========================================
            # Wait for admin approval/correction first
            # ========================================
            logger.info("ℹ️ Answer generated but NOT cached - waiting for admin approval")
            logger.info("📝 Answer will be saved to interactions table for admin review")
            
            return final_answer, None, transcribed_question or user_question
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return FALLBACK_ERROR, None, transcribed_question or user_question
        except Exception as e:
            logger.error(f"Unknown error: {e}", exc_info=True)
            return FALLBACK_ERROR, None, transcribed_question or user_question

    def get_scientific_response(
        self, 
        user_question: str = None, 
        image_path: str = None
    ) -> str:
        """Synchronous wrapper for get_scientific_response_async."""
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Update tuple unpacking to account for the third return value
            response, cached_id, transcribed_question = loop.run_until_complete(
                self.get_scientific_response_async(user_question, image_path)
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in synchronous wrapper: {e}", exc_info=True)
            return FALLBACK_ERROR


# ========================================
# SINGLETON INSTANCE
# ========================================
scientific_core_instance = ScientificCore()
