# --- FILE: knowledge_processor.py ---

import os
import logging
from langchain_community.document_loaders import TextLoader, JSONLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from config import KNOWLEDGE_BASE_DIR, VECTOR_STORE_DIR, GENAI_API_KEY, SCIENTIFIC_GENAI_API_KEY, BASE_DIR 

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the new directory path for scientific knowledge
SCIENTIFIC_KB_DIR = os.path.join(BASE_DIR, 'scientific_kb')


def create_vector_store():
    """
    Loads all .md and .json documents from the ADMINISTRATIVE knowledge base, chunks them,
    creates embeddings, and saves them to a FAISS vector store.
    """
    try:
        logging.info("Starting ADMINISTRATIVE knowledge base processing...")
        
        # Loader for Markdown (.md) files
        loader_md = DirectoryLoader(
            os.path.join(KNOWLEDGE_BASE_DIR, 'documents'),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'},
            show_progress=True,
            use_multithreading=True
        )
        
        # Loader for JSON (.json) files for FAQs
        loader_json = DirectoryLoader(
            os.path.join(KNOWLEDGE_BASE_DIR, 'faqs'),
            glob="**/*.json",
            loader_cls=JSONLoader,
            loader_kwargs={
                'jq_schema': '.[] | {page_content: (.question + " A: " + .answer)}',
                'text_content': False
            },
            show_progress=True,
            use_multithreading=True,
        )

        docs_md = loader_md.load()
        docs_json = loader_json.load()
        all_documents = docs_md + docs_json

        if not all_documents:
            logging.warning("No administrative documents were loaded from the knowledge base. This may be normal.")
            return

        logging.info(f"Loaded {len(all_documents)} administrative document sections in total.")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        docs = text_splitter.split_documents(all_documents)
        logging.info(f"Split administrative documents into {len(docs)} chunks.")

        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=GENAI_API_KEY)

        logging.info("Building FAISS vector store for administrative data...")
        vector_store = FAISS.from_documents(docs, embeddings)

        vector_store_path = os.path.join(VECTOR_STORE_DIR, "faqs_index")
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        vector_store.save_local(vector_store_path)
        
        logging.info(f"Administrative vector store created and saved successfully at {vector_store_path}")

    except Exception as e:
        logging.error(f"An error occurred during administrative vector store creation: {e}", exc_info=True)


def create_scientific_vector_store():
   
    try:
        logging.info("Starting SCIENTIFIC knowledge base processing with per-lesson FAQs...")
        os.makedirs(SCIENTIFIC_KB_DIR, exist_ok=True)
        
        all_scientific_docs = []
        
        # === PART 1: Load MD files from chapter folders ===
        logging.info("Loading lesson content (MD files)...")
        for chapter_folder in os.listdir(SCIENTIFIC_KB_DIR):
            chapter_path = os.path.join(SCIENTIFIC_KB_DIR, chapter_folder)
            
            # Skip the 'faqs' folder
            if chapter_folder == 'faqs' or not os.path.isdir(chapter_path):
                continue
                
            for lesson_file in os.listdir(chapter_path):
                if lesson_file.endswith(".md"):
                    lesson_path = os.path.join(chapter_path, lesson_file)
                    try:
                        loader = TextLoader(lesson_path, encoding='utf-8')
                        docs = loader.load()
                        
                        # Add metadata to each document
                        for doc in docs:
                            doc.metadata = {
                                "chapter": chapter_folder.replace("_", " ").title(),
                                "lesson": lesson_file.replace(".md", "").replace("_", " ").title(),
                                "type": "lesson_content"
                            }
                        all_scientific_docs.extend(docs)
                        logging.info(f"  ✓ Loaded: {chapter_folder}/{lesson_file}")
                    except Exception as e:
                        logging.error(f"  ✗ Error loading {chapter_folder}/{lesson_file}: {e}")
        
        logging.info(f"Loaded {len(all_scientific_docs)} lesson documents (MD files).")
        
        # === PART 2: Load JSON FAQs organized by chapter/lesson ===
        logging.info("Loading FAQs (JSON files organized by chapter/lesson)...")
        faqs_base_path = os.path.join(SCIENTIFIC_KB_DIR, 'faqs')
        
        if os.path.exists(faqs_base_path):
            faq_count = 0
            
            # Iterate through chapter folders inside faqs/
            for chapter_folder in os.listdir(faqs_base_path):
                chapter_faq_path = os.path.join(faqs_base_path, chapter_folder)
                
                if not os.path.isdir(chapter_faq_path):
                    continue
                
                # Iterate through JSON files (one per lesson)
                for faq_file in os.listdir(chapter_faq_path):
                    if faq_file.endswith(".json"):
                        faq_file_path = os.path.join(chapter_faq_path, faq_file)
                        
                        try:
                            loader = JSONLoader(
                                file_path=faq_file_path,
                                jq_schema='.[] | {page_content: (.question + " A: " + .answer)}',
                                text_content=False
                            )
                            
                            faq_docs = loader.load()
                            
                            # Add metadata matching the lesson structure
                            lesson_name = faq_file.replace(".json", "").replace("_", " ").title()
                            for doc in faq_docs:
                                doc.metadata = {
                                    "chapter": chapter_folder.replace("_", " ").title(),
                                    "lesson": lesson_name,
                                    "type": "faq"
                                }
                            
                            all_scientific_docs.extend(faq_docs)
                            faq_count += len(faq_docs)
                            logging.info(f"  âœ“ Loaded: faqs/{chapter_folder}/{faq_file} ({len(faq_docs)} questions)")
                            
                        except Exception as e:
                            logging.error(f"  âœ— Error loading faqs/{chapter_folder}/{faq_file}: {e}")
            
            logging.info(f"Loaded {faq_count} FAQ entries from JSON files.")
        else:
            logging.warning("No 'faqs' folder found in scientific_kb. To add FAQs, create: scientific_kb/faqs/chapter_X/lesson_Y.json")

        if not all_scientific_docs:
            logging.error("No scientific documents were loaded. Please check the 'scientific_kb' directory structure.")
            return

        logging.info(f"Total scientific documents loaded: {len(all_scientific_docs)}")

        # === PART 3: Chunk and add unique IDs ===
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = text_splitter.split_documents(all_scientific_docs)
        
        # Add a unique ID to each chunk's metadata for precise citation
        for i, chunk in enumerate(chunks):
            doc_type = chunk.metadata.get('type', 'content')
            chapter = chunk.metadata.get('chapter', 'Unknown')
            lesson = chunk.metadata.get('lesson', 'Unknown')
            chunk.metadata["source_id"] = f"{chapter}-{lesson}-{doc_type}-chunk{i}"

        logging.info(f"Split scientific documents into {len(chunks)} chunks with metadata.")

        # === PART 4: Build and save vector store ===
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=SCIENTIFIC_GENAI_API_KEY
        )

        logging.info("Building FAISS vector store for scientific data...")
        vector_store = FAISS.from_documents(chunks, embeddings)

        vector_store_path = os.path.join(VECTOR_STORE_DIR, "scientific_index")
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        vector_store.save_local(vector_store_path)
        
        logging.info("=" * 60)
        logging.info(f"Scientific vector store created successfully!")
        logging.info(f"Location: {vector_store_path}")
        logging.info(f"Total chunks indexed: {len(chunks)}")
        logging.info("=" * 60)

    except Exception as e:
        logging.error(f"An error occurred during scientific vector store creation: {e}", exc_info=True)


if __name__ == '__main__':
    create_vector_store()
    create_scientific_vector_store()