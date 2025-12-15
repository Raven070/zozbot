"""
Enhanced Question Deduplication System for Scientific Questions
"""

import logging
import numpy as np
import re
from typing import Optional, Dict, List, Tuple
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import SCIENTIFIC_GENAI_API_KEY
import database
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Matching thresholds - tuned for chemistry questions
EXACT_MATCH_THRESHOLD = 0.95          # Almost identical text
HIGH_CONFIDENCE_THRESHOLD = 0.85      # Very likely same question
MEDIUM_CONFIDENCE_THRESHOLD = 0.75    # Possibly same question
SEMANTIC_EMBEDDING_THRESHOLD = 0.82   # Semantic similarity via embeddings


class EnhancedQuestionDeduplicator:
    """
    Advanced deduplication system with multi-layer intelligent matching.
    
    Handles the same question from:
    - Different photo angles/lighting
    - Different booklets/sources
    - Minor transcription differences
    """
    
    def __init__(self):
        """Initialize the enhanced deduplicator."""
        try:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=SCIENTIFIC_GENAI_API_KEY
            )
            logger.info("✓ Enhanced question deduplicator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize deduplicator: {e}")
            self.embeddings = None
    
    def _extract_chemical_formulas(self, text: str) -> set:
        """
        Extract all chemical formulas from text.
        Examples: Fe2O3, H2SO4, NaCl, K2Cr2O7
        """
        formulas = set()
        
        # Pattern for chemical formulas
        # Matches: Capital letter, optional lowercase, optional numbers, repeated
        pattern = r'\b[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*\b'
        matches = re.findall(pattern, text)
        
        # Filter out common English words that match the pattern
        english_words = {'A', 'I', 'In', 'On', 'As', 'At', 'An', 'Is', 'It', 'To', 'Be'}
        
        for match in matches:
            if match not in english_words and len(match) > 1:
                formulas.add(match.upper())
        
        return formulas
    
    def _extract_numbers_and_units(self, text: str) -> set:
        """Extract numbers with units (important for chemistry problems)."""
        numbers = set()
        
        # Pattern for numbers with optional decimal and optional units
        patterns = [
            r'\d+\.?\d*\s*(?:mol|g|kg|L|mL|M|atm|Pa|K|°C|J|kJ|eV)',  # with units
            r'\b\d+\.?\d*\b'  # standalone numbers
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.update(matches)
        
        return numbers
    
    def _extract_chemistry_keywords(self, text: str) -> set:
        """Extract key chemistry terms that identify the question topic."""
        keywords = set()
        
        # Common chemistry terms
        chemistry_terms = [
            'oxidation', 'reduction', 'electron', 'atom', 'molecule', 'ion',
            'compound', 'element', 'reaction', 'bond', 'orbital', 'configuration',
            'valence', 'charge', 'state', 'number', 'mass', 'molar', 'concentration',
            'acid', 'base', 'salt', 'pH', 'buffer', 'equilibrium', 'catalyst',
            'transition', 'metal', 'nonmetal', 'periodic', 'table', 'group', 'period',
            'alkali', 'halogen', 'noble', 'gas', 'solid', 'liquid',
            'solution', 'solvent', 'solute', 'dissolve', 'precipitate',
            'exothermic', 'endothermic', 'energy', 'enthalpy', 'entropy'
        ]
        
        text_lower = text.lower()
        for term in chemistry_terms:
            if term in text_lower:
                keywords.add(term)
        
        return keywords
    
    def _normalize_answer_choices(self, text: str) -> str:
        """
        Normalize answer choice formats to standard format.
        
        Converts:
        - (a) → a)
        - a- → a)
        - a. → a)
        - [a] → a)
        """
        # Remove various choice format markers
        text = re.sub(r'\([a-d]\)', lambda m: m.group(0)[1] + ')', text, flags=re.IGNORECASE)
        text = re.sub(r'\[[a-d]\]', lambda m: m.group(0)[1] + ')', text, flags=re.IGNORECASE)
        text = re.sub(r'([a-d])-\s*', r'\1) ', text, flags=re.IGNORECASE)
        text = re.sub(r'([a-d])\.\s*', r'\1) ', text, flags=re.IGNORECASE)
        
        return text
    
    def _extract_question_fingerprint(self, text: str) -> str:
        """
        Create a "fingerprint" of the question by removing noise.
        
        This creates a normalized version that remains consistent
        across different photo angles and minor variations.
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove question numbers (e.g., "Question 5:", "5)", "Q5:")
        text = re.sub(r'(?:question|q)?\s*\d+[:\)\.-]?\s*', ' ', text, flags=re.IGNORECASE)
        
        # Normalize choice formats
        text = self._normalize_answer_choices(text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common filler words that don't change meaning
        fillers = [' the ', ' a ', ' an ', ' is ', ' are ', ' of ', ' in ', ' at ', ' to ', ' from ', ' with ']
        for filler in fillers:
            text = text.replace(filler, ' ')
        
        # Normalize chemical formulas (remove spaces between elements and numbers)
        text = re.sub(r'([A-Z][a-z]?)\s+(\d+)', r'\1\2', text)
        
        # Remove punctuation except essential chemistry symbols
        text = re.sub(r'[^\w\s\+\-\=\(\)\[\]]', '', text)
        
        # Final cleanup
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _create_question_signature(self, text: str) -> Dict:
        """
        Create a comprehensive signature of the question.
        
        Returns a dict with:
        - fingerprint: normalized text
        - formulas: set of chemical formulas
        - numbers: set of numbers/measurements
        - keywords: set of chemistry keywords
        """
        fingerprint = self._extract_question_fingerprint(text)
        formulas = self._extract_chemical_formulas(text)
        numbers = self._extract_numbers_and_units(text)
        keywords = self._extract_chemistry_keywords(text)
        
        return {
            'fingerprint': fingerprint,
            'formulas': formulas,
            'numbers': numbers,
            'keywords': keywords
        }
    
    def _compute_fuzzy_similarity(self, text1: str, text2: str) -> float:
        """Compute fuzzy text similarity using SequenceMatcher."""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _compute_cosine_similarity(self, embedding1: list, embedding2: list) -> float:
        """Compute cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _compute_set_overlap(self, set1: set, set2: set) -> float:
        """Compute Jaccard similarity between two sets."""
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _compute_signature_similarity(self, sig1: Dict, sig2: Dict) -> Dict[str, float]:
        """
        Compute similarity scores between two question signatures.
        
        Returns detailed breakdown of different similarity metrics.
        """
        scores = {}
        
        # 1. Fingerprint similarity (text-based)
        scores['fingerprint'] = self._compute_fuzzy_similarity(
            sig1['fingerprint'],
            sig2['fingerprint']
        )
        
        # 2. Chemical formulas overlap (VERY important!)
        scores['formulas'] = self._compute_set_overlap(
            sig1['formulas'],
            sig2['formulas']
        )
        
        # 3. Numbers/measurements overlap
        scores['numbers'] = self._compute_set_overlap(
            sig1['numbers'],
            sig2['numbers']
        )
        
        # 4. Keywords overlap
        scores['keywords'] = self._compute_set_overlap(
            sig1['keywords'],
            sig2['keywords']
        )
        
        # 5. Combined weighted score
        # Formulas and fingerprint are most important for chemistry
        scores['combined'] = (
            scores['fingerprint'] * 0.40 +
            scores['formulas'] * 0.35 +
            scores['keywords'] * 0.15 +
            scores['numbers'] * 0.10
        )
        
        return scores
    
    async def find_similar_question(
        self, 
        question_text: str, 
        image_hash: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Find similar question using intelligent multi-layer matching.
        
        Matching Strategy (in priority order):
        1. Exact image hash (if available and matches)
        2. Question signature matching (formulas + fingerprint)
        3. Semantic embedding matching
        
        Args:
            question_text: The transcribed question text
            image_hash: Optional hash of the image (used as backup)
            
        Returns:
            Cached question data if found, None otherwise
        """
        if not self.embeddings:
            logger.warning("⚠️  Embeddings not available")
            return None
        
        try:
            logger.info("=" * 70)
            logger.info("🔍 INTELLIGENT QUESTION MATCHING STARTED")
            logger.info(f"📝 Question: '{question_text[:100]}...'")
            logger.info("=" * 70)
            
            # ============================================================
            # LAYER 1: EXACT IMAGE HASH (Fast backup check)
            # ============================================================
            if image_hash:
                logger.info(f"🔑 Layer 1: Checking exact image hash: {image_hash[:16]}...")
                exact_match = database.get_cached_question_by_image_hash(image_hash)
                
                if exact_match and exact_match.get('is_corrected'):
                    logger.info(
                        f"✅ EXACT IMAGE MATCH! (ID: {exact_match['id']}, "
                        f"used {exact_match['times_used']} times)"
                    )
                    logger.info("=" * 70)
                    return exact_match
                logger.info("   ❌ No exact image match")
            
            # ============================================================
            # LAYER 2: INTELLIGENT SIGNATURE MATCHING
            # ============================================================
            logger.info("🔍 Layer 2: Extracting question signature...")
            
            # Create signature for incoming question
            incoming_sig = self._create_question_signature(question_text)
            
            logger.info(f"   📊 Fingerprint: '{incoming_sig['fingerprint'][:60]}...'")
            logger.info(f"   🧪 Formulas: {incoming_sig['formulas']}")
            logger.info(f"   🔢 Numbers: {incoming_sig['numbers']}")
            logger.info(f"   🔑 Keywords: {incoming_sig['keywords']}")
            
            # Get recent cached questions (only approved/corrected ones)
            cached_questions = database.get_recent_cached_questions(limit=200)
            logger.info(f"   📚 Comparing against {len(cached_questions)} cached questions")
            
            best_match = None
            best_score = 0.0
            best_scores_detail = {}
            
            for cached_q in cached_questions:
                # Only check approved/corrected questions
                if not cached_q.get('is_corrected'):
                    continue
                
                cached_text = cached_q.get('question_text', '')
                cached_sig = self._create_question_signature(cached_text)
                
                # Compute detailed similarity
                scores = self._compute_signature_similarity(incoming_sig, cached_sig)
                
                # Log high-scoring matches
                if scores['combined'] > 0.70:
                    logger.debug(
                        f"   🎯 Potential match (ID: {cached_q['id']}, "
                        f"score: {scores['combined']:.3f})\n"
                        f"      Breakdown: FP={scores['fingerprint']:.2f}, "
                        f"Formulas={scores['formulas']:.2f}, "
                        f"Keywords={scores['keywords']:.2f}, "
                        f"Numbers={scores['numbers']:.2f}"
                    )
                
                if scores['combined'] > best_score:
                    best_score = scores['combined']
                    best_match = cached_q
                    best_scores_detail = scores
            
            # Check if we have a confident match
            if best_score >= HIGH_CONFIDENCE_THRESHOLD:
                logger.info("")
                logger.info("✅ HIGH CONFIDENCE MATCH FOUND!")
                logger.info(f"   📍 Cached Question ID: {best_match['id']}")
                logger.info(f"   ⭐ Combined Score: {best_score:.3f}")
                logger.info(f"   📊 Details:")
                logger.info(f"      - Fingerprint: {best_scores_detail['fingerprint']:.3f}")
                logger.info(f"      - Formulas: {best_scores_detail['formulas']:.3f}")
                logger.info(f"      - Keywords: {best_scores_detail['keywords']:.3f}")
                logger.info(f"      - Numbers: {best_scores_detail['numbers']:.3f}")
                logger.info(f"   🔄 Times Used: {best_match['times_used']}")
                logger.info("=" * 70)
                return best_match
            
            # Medium confidence - still use but log for review
            if best_score >= MEDIUM_CONFIDENCE_THRESHOLD:
                logger.info("")
                logger.info("⚠️  MEDIUM CONFIDENCE MATCH")
                logger.info(f"   📍 Cached Question ID: {best_match['id']}")
                logger.info(f"   ⭐ Combined Score: {best_score:.3f}")
                logger.info(f"   ⚠️  Consider manual review if answer seems wrong")
                logger.info("=" * 70)
                return best_match
            
            # ============================================================
            # LAYER 3: SEMANTIC EMBEDDING (Deep understanding)
            # ============================================================
            logger.info("")
            logger.info("🧠 Layer 3: Performing semantic embedding search...")
            
            question_embedding = self.embeddings.embed_query(question_text)
            
            best_semantic_match = None
            best_semantic_score = 0.0
            
            for cached_q in cached_questions:
                if not cached_q.get('is_corrected') or not cached_q.get('embedding'):
                    continue
                
                semantic_sim = self._compute_cosine_similarity(
                    question_embedding,
                    cached_q['embedding']
                )
                
                if semantic_sim > best_semantic_score:
                    best_semantic_score = semantic_sim
                    best_semantic_match = cached_q
            
            if best_semantic_score >= SEMANTIC_EMBEDDING_THRESHOLD:
                logger.info("")
                logger.info("✅ SEMANTIC MATCH FOUND!")
                logger.info(f"   📍 Cached Question ID: {best_semantic_match['id']}")
                logger.info(f"   🧠 Semantic Similarity: {best_semantic_score:.3f}")
                logger.info("=" * 70)
                return best_semantic_match
            
            # ============================================================
            # NO MATCH FOUND
            # ============================================================
            logger.info("")
            logger.info("❌ NO SIMILAR QUESTION FOUND")
            logger.info(f"   Best signature score: {best_score:.3f} (threshold: {HIGH_CONFIDENCE_THRESHOLD})")
            logger.info(f"   Best semantic score: {best_semantic_score:.3f} (threshold: {SEMANTIC_EMBEDDING_THRESHOLD})")
            logger.info("   ℹ️  This appears to be a NEW question")
            logger.info("=" * 70)
            return None
            
        except Exception as e:
            logger.error(f"Error finding similar question: {e}", exc_info=True)
            return None
    
    async def cache_question(
        self,
        question_text: str,
        answer_text: str,
        image_hash: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        
        if not self.embeddings:
            logger.warning("Embeddings not available, skipping caching")
            return False
        
        try:
            # Create normalized version
            signature = self._create_question_signature(question_text)
            normalized_text = signature['fingerprint']
            
            # Generate embedding
            question_embedding = self.embeddings.embed_query(question_text)
            
            # Store in database
            cached_id = database.cache_scientific_question(
                question_text=question_text,
                normalized_text=normalized_text,
                answer_text=answer_text,
                embedding=question_embedding,
                image_hash=image_hash,
                metadata=metadata
            )
            
            if cached_id:
                logger.info(f"✅ Question cached successfully with ID {cached_id}")
                logger.info(f"   🔑 Signature: {len(signature['formulas'])} formulas, {len(signature['keywords'])} keywords")
                return True
            else:
                logger.warning("❌ Failed to cache question")
                return False
                
        except Exception as e:
            logger.error(f"Error caching question: {e}", exc_info=True)
            return False
    
    async def update_cached_answer(
        self,
        cached_question_id: int,
        new_answer: str,
        correction_source: str = 'manual'
    ) -> bool:
        """Update a cached answer when corrected."""
        try:
            success = database.update_cached_question_answer(
                cached_question_id=cached_question_id,
                new_answer=new_answer,
                correction_source=correction_source
            )
            
            if success:
                logger.info(
                    f"✅ Updated cached answer for question ID {cached_question_id}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating cached answer: {e}", exc_info=True)
            return False
    
    def get_statistics(self) -> Dict:
        """Get deduplication statistics."""
        try:
            stats = database.get_cache_statistics()
            return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


# Singleton instance
deduplicator = EnhancedQuestionDeduplicator()