import re
from typing import List, Optional, Dict, Any

class MarkdownChunker:
    """
    Splits Markdown text into chunks respecting semantic structure.
    Prioritizes headers, then code blocks, then paragraphs.
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
    def split_text(self, text: str) -> List[str]:
        """
        Split text using Markdown structure.
        """
        if not text:
            return []
            
        # 1. Split by major sections (Headers Level 1 & 2)
        # Regex looks for lines starting with # or ##
        # We prefer to keep the header with the content that follows
        sections = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
        
        chunks = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            if len(section) <= self.chunk_size:
                chunks.append(section)
            else:
                # 2. If section is too big, split by sub-headers (Level 3+)
                sub_sections = re.split(r'(?=^#{3,} )', section, flags=re.MULTILINE)
                for sub in sub_sections:
                    sub = sub.strip()
                    if not sub: 
                        continue
                        
                    if len(sub) <= self.chunk_size:
                        chunks.append(sub)
                    else:
                        # 3. If still too big, split by paragraphs
                        self._split_by_paragraphs(sub, chunks)
                        
        # 4. Merge small chunks if possible (optional optimization)
        # This implementation keeps it simple for now
        
        # 5. Add overlap if needed (handled by caller or simple append here)
        # Note: Implementing overlap for structural chunks is tricky. 
        # For now, we rely on RAG service's generic overlap or just good structural splitting.
        # But let's add a basic overlap wrapper if requested.
        
        return list(self._merge_small_chunks(chunks))

    def _split_by_paragraphs(self, text: str, chunks: List[str]):
        """
        Split text by double newlines (paragraphs).
        """
        paragraphs = re.split(r'\n\s*\n', text)
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk = (current_chunk + "\n\n" + para).strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If paragraph itself is huge, split by sentences (fallback)
                if len(para) > self.chunk_size:
                     chunks.extend(self._split_by_sentences(para))
                     current_chunk = ""
                else:
                    current_chunk = para
                    
        if current_chunk:
            chunks.append(current_chunk)

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Basic sentence splitter for very large blocks.
        """
        # Simple split by punctuation followed by space
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) + 1 <= self.chunk_size:
                current = (current + " " + sent).strip()
            else:
                if current: chunks.append(current)
                current = sent
        if current:
            chunks.append(current)
        return chunks

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """
        Merge valid structural chunks that are too small to be useful on their own.
        """
        if not chunks: 
            return []
            
        merged = []
        current = chunks[0]
        
        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            if len(current) + len(next_chunk) + 2 <= self.chunk_size:
                current = current + "\n\n" + next_chunk
            else:
                merged.append(current)
                current = next_chunk
        merged.append(current)
        return merged


class AgenticChunker:
    """
    Uses LLM to summarize large sections and create a hierarchy of chunks.
    """
    def __init__(self, llm_service, chunk_size: int = 500, chunk_overlap: int = 50):
        self.llm_service = llm_service
        self.base_chunker = MarkdownChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
    def split_and_summarize(self, text: str) -> List[Dict[str, Any]]:
        """
        Splits text into high-level sections, generates summaries, and details.
        Returns a list of dicts:
        [
            {
                "content": "Summary of section...",
                "is_summary": True,
                "children": ["Detail 1...", "Detail 2..."]
            },
            ...
        ]
        """
        if not text:
            return []
            
        # 1. Split by Level 1 or 2 Headers to get logical sections
        sections = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
        
        results = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # If section is very short, just treat as a normal chunk, no summary needed
            if len(section) < 500:
                results.append({
                    "content": section,
                    "is_summary": False, # Treat as standalone or childless parent? 
                                         # Let's treat as simple chunk for now, or maybe child without parent.
                                         # Actually, let's just make it a detail chunk.
                    "children": [] 
                })
                continue
                
            # 2. Generate Summary for this section
            summary = self._generate_summary(section)
            
            # 3. Split section into detailed chunks
            detail_chunks = self.base_chunker.split_text(section)
            
            results.append({
                "content": summary,
                "is_summary": True,
                "children": detail_chunks
            })
            
        return results

    def _generate_summary(self, text: str) -> str:
        """
        Generates a concise summary for the provided text.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        prompt = f"""Summarize the following text in 2-3 concise sentences, capturing the main ideas and context.
        
Text:
{text[:2000]}  # Truncate to avoid context limit if huge

Summary:"""
        
        messages = [{"role": "user", "content": prompt}]
        try:
            logger.info("⚡ ACTIVATING LLM for Section Summarization...")
            summary = self.llm_service.generate_response(messages)
            logger.info(f"✅ LLM Summary Generated: {summary[:50]}...")
            return summary
        except Exception as e:
            logger.error(f"❌ LLM Summarization failed: {e}")
            # Fallback if LLM fails
            return text[:200] + "..."
