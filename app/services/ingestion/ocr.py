import pytesseract
from PIL import Image
import logging
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

class OCRService:
    @staticmethod
    def extract_text_from_image(image_path: str) -> str:
        """
        Extract text from an image file using Tesseract.
        """
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            return ""

    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """
        Extract text from a PDF file by converting pages to images and running OCR.
        """
        try:
            # Convert PDF pages to images (requires poppler installed)
            images = convert_from_path(pdf_path)
            full_text = []
            
            for i, image in enumerate(images):
                logger.info(f"OCR processing PDF page {i+1}/{len(images)}")
                page_text = pytesseract.image_to_string(image)
                full_text.append(page_text)
                
            return "\n\n".join(full_text).strip()
        except Exception as e:
            logger.error(f"Error OCR processing PDF {pdf_path}: {str(e)}")
            return ""
