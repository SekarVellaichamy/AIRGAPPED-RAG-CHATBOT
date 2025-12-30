"""
Document Parser for RAG System.
Parses various document formats and extracts text content.
Uses compiled MarkItDown for efficient conversion to Markdown.
"""

import logging
import os
from markitdown import MarkItDown
from openai import OpenAI

from app.services.ingestion.ocr import OCRService
from app.services.ingestion.preprocessor import TextPreprocessor
from app.core.config import settings

logger = logging.getLogger(__name__)

class DocumentParser:
    """
    Document parser using Microsoft MarkItDown.
    """
    
    def __init__(self):
        self.ocr_service = OCRService()
        self.preprocessor = TextPreprocessor()
        
        # Initialize OpenAI client for MarkItDown to use with Ollama
        try:
            self.llm_client = OpenAI(
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
                api_key="ollama" # generic key for ollama
            )
            self.llm_model = settings.LLM_MODEL
            self.md = MarkItDown(llm_client=self.llm_client, llm_model=self.llm_model)
            logger.info(f"MarkItDown initialized with LLM support (model: {self.llm_model})")
        except Exception as e:
            logger.warning(f"Failed to initialize MarkItDown with LLM: {e}. Falling back to standard init.")
            self.md = MarkItDown()
            self.llm_client = None
        
    def parse_file(self, file_path: str, file_type: str) -> str:
        """
        Route the file to the appropriate parser.
        MarkItDown handles most formats natively.
        """
        logger.info(f"Parsing file: {file_path} (type: {file_type})")
        
        try:
            # Handle images separately via OCR service
            if file_type.startswith("image/"):
                raw_text = self.ocr_service.extract_text_from_image(file_path)
            
            # Handle PDF via OCR (per user request)
            elif file_type == "application/pdf" or file_path.lower().endswith(".pdf"):
                logger.info("Routing PDF to OCR service")
                raw_text = self.ocr_service.extract_text_from_pdf(file_path)
                
            elif file_type in ("text/plain", "text/markdown") or file_path.endswith(('.txt', '.md')):
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_text = f.read()
            else:
                # Use MarkItDown for all other supported formats (Office, HTML, XML, JSON, etc.)
                # MarkItDown will automatically detect the format based on file extension/content
                logger.info("Routing to MarkItDown")
                result = self.md.convert(file_path)
                raw_text = result.text_content
                
            # Apply preprocessing
            preprocessed = self.preprocessor.preprocess(raw_text)
            logger.info(f"Parsing complete. Raw: {len(raw_text)} chars, After preprocessing: {len(preprocessed)} chars")
            return preprocessed
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}", exc_info=True)
            return ""

