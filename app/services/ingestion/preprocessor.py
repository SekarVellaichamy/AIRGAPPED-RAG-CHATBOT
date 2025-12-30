"""
Text Preprocessor for RAG System.
Cleans and normalizes text before chunking to improve retrieval quality.
"""

import re
import logging
import unicodedata
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """
    Text preprocessing pipeline for document content.
    Applies various cleaning and normalization steps to improve RAG quality.
    """
    
    def __init__(self):
        # Common header/footer patterns to remove
        self.header_footer_patterns = [
            r'Page \d+ of \d+',
            r'Page \d+',
            r'^\d+$',  # Standalone page numbers
            r'©.*?\d{4}',  # Copyright notices
            r'All [Rr]ights [Rr]eserved',
            r'Confidential',
            r'CONFIDENTIAL',
            r'DRAFT',
        ]
        
    def preprocess(self, text: str, options: Optional[Dict[str, bool]] = None) -> str:
        """
        Full preprocessing pipeline.
        
        Args:
            text: Raw text content
            options: Dict to enable/disable specific steps:
                - normalize_whitespace (default: True)
                - remove_headers_footers (default: True)
                - clean_unicode (default: True)
                - repair_hyphenation (default: True)
        
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        opts = {
            'normalize_whitespace': True,
            'remove_headers_footers': True,
            'clean_unicode': True,
            'repair_hyphenation': True,
        }
        if options:
            opts.update(options)
        
        result = text
        
        if opts['clean_unicode']:
            result = self.clean_unicode(result)
            
        if opts['repair_hyphenation']:
            result = self.repair_hyphenation(result)
            
        if opts['remove_headers_footers']:
            result = self.remove_headers_footers(result)
            
        if opts['normalize_whitespace']:
            result = self.normalize_whitespace(result)
        
        return result.strip()
    
    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace: collapse multiple spaces/newlines.
        """
        # Replace tabs with spaces
        text = text.replace('\t', ' ')
        
        # Collapse multiple spaces to single space
        text = re.sub(r' +', ' ', text)
        
        # Collapse 3+ newlines to 2 (preserve paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove trailing spaces on each line
        text = re.sub(r' +\n', '\n', text)
        
        # Remove leading spaces on each line
        text = re.sub(r'\n +', '\n', text)
        
        return text
    
    def remove_headers_footers(self, text: str) -> str:
        """
        Remove common header/footer patterns.
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            is_header_footer = False
            
            for pattern in self.header_footer_patterns:
                if re.match(pattern, line_stripped):
                    is_header_footer = True
                    break
            
            if not is_header_footer:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def clean_unicode(self, text: str) -> str:
        """
        Clean and normalize unicode characters.
        """
        # Normalize unicode (NFC form)
        text = unicodedata.normalize('NFC', text)
        
        # Replace common problematic characters
        replacements = {
            '\u2018': "'",   # Left single quote
            '\u2019': "'",   # Right single quote
            '\u201c': '"',   # Left double quote
            '\u201d': '"',   # Right double quote
            '\u2013': '-',   # En dash
            '\u2014': '-',   # Em dash
            '\u2026': '...', # Ellipsis
            '\u00a0': ' ',   # Non-breaking space
            '\u200b': '',    # Zero-width space
            '\ufeff': '',    # BOM
            '\r\n': '\n',    # Windows line endings
            '\r': '\n',      # Old Mac line endings
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove control characters except newlines and tabs
        text = ''.join(c for c in text if c == '\n' or c == '\t' or not unicodedata.category(c).startswith('C'))
        
        return text
    
    def repair_hyphenation(self, text: str) -> str:
        """
        Repair words split across lines with hyphens.
        Common in PDFs and scanned documents.
        """
        # Pattern: word- at end of line followed by continuation
        # e.g., "docu-\nment" -> "document"
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        
        return text
    
    def table_to_markdown(self, table_data: List[List[str]], include_header: bool = True) -> str:
        """
        Convert table data to markdown format for LLM-friendly representation.
        
        Args:
            table_data: 2D list of cell values
            include_header: If True, first row is treated as header
            
        Returns:
            Markdown table string
        """
        if not table_data or not table_data[0]:
            return ""
        
        # Determine column widths
        num_cols = max(len(row) for row in table_data)
        
        # Normalize rows to have same number of columns
        normalized = []
        for row in table_data:
            normalized_row = list(row) + [''] * (num_cols - len(row))
            # Clean cell content - handle None values
            normalized_row = [str(cell).strip().replace('|', '\\|') if cell is not None else '' for cell in normalized_row]
            normalized.append(normalized_row)
        
        lines = []
        
        if include_header and len(normalized) > 0:
            # Header row
            header = '| ' + ' | '.join(normalized[0]) + ' |'
            lines.append(header)
            
            # Separator
            sep = '| ' + ' | '.join(['---'] * num_cols) + ' |'
            lines.append(sep)
            
            # Data rows
            for row in normalized[1:]:
                line = '| ' + ' | '.join(row) + ' |'
                lines.append(line)
        else:
            # All rows as data
            for row in normalized:
                line = '| ' + ' | '.join(row) + ' |'
                lines.append(line)
        
        return '\n'.join(lines)
    
    def table_to_text(self, table_data: List[List[str]], header_row: bool = True) -> str:
        """
        Convert table to natural language format for better RAG retrieval.
        
        Args:
            table_data: 2D list of cell values
            header_row: If True, first row contains column headers
            
        Returns:
            Text representation of table data
        """
        if not table_data or not table_data[0]:
            return ""
        
        if not header_row or len(table_data) < 2:
            # Simple row-by-row format
            lines = []
            for row in table_data:
                line = ', '.join(str(cell).strip() for cell in row if cell)
                if line:
                    lines.append(line)
            return '\n'.join(lines)
        
        # Use headers to create key-value pairs
        headers = [str(h).strip() for h in table_data[0]]
        lines = []
        
        for row in table_data[1:]:
            parts = []
            for i, cell in enumerate(row):
                cell_value = str(cell).strip() if cell else ''
                if cell_value and i < len(headers):
                    header = headers[i] if headers[i] else f'Column {i+1}'
                    parts.append(f"{header}: {cell_value}")
            if parts:
                lines.append('; '.join(parts))
        
        return '\n'.join(lines)
