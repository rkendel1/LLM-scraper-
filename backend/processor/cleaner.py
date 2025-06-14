# processor/cleaner.py

import trafilatura
from langdetect import detect
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize splitter
splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)

def extract_content(html: str, url: str = None, force_language: str = 'en'):
    """
    Extracts clean, LLM-ready content from HTML or raw text.
    
    Args:
        html (str): Raw HTML or plain text
        url (str, optional): Source URL for metadata
        force_language (str, optional): Language code to filter by (default: 'en')

    Returns:
        dict: Cleaned content and metadata, or None if filtering fails
    """
    try:
        result = trafilatura.bare_extraction(html, favor_recall=True)

        if not result or not result.get('text'):
            logger.warning("No text extracted from HTML.")
            return None

        full_text = result['text']
        title = result.get('title', '')
        description = result.get('excerpt', '')
        pub_date = result.get('date', None)

        # Language detection and filtering
        detected_lang = detect(full_text)
        if force_language and detected_lang != force_language:
            logger.info(f"Skipping non-{force_language} content (detected: {detected_lang})")
            return None

        # Quality check: minimum length
        if len(full_text.split()) < 200:
            logger.warning("Content too short (<200 words), skipping.")
            return None

        # Chunking for LLM context windows
        chunks = splitter.split_text(full_text)

        return {
            'title': title,
            'description': description,
            'text': full_text,
            'chunks': chunks,
            'url': url or result.get('url'),
            'pub_date': pub_date,
            'language': detected_lang,
        }

    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        return None
