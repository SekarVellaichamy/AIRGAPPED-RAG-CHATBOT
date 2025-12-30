
import logging
import json
import time
from typing import Optional, List, Dict, Any, Generator, Iterator
from dataclasses import dataclass

from sqlmodel import Session, select, desc
from app.models.models import User, ChatSession, Message
from app.services.llm import get_llm_service
from app.services.ingestion.rag_service import RAGService
from app.core.config import settings
import html

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.llm_service = get_llm_service()
        self.rag_service = RAGService()

    def get_user_sessions(self, user_id: int) -> List[ChatSession]:
        return self.db_session.exec(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.created_at))
        ).all()

    def get_or_create_session(self, user_id: int, session_id: Optional[int] = None) -> ChatSession:
        if session_id:
            session = self.db_session.get(ChatSession, session_id)
            if session and session.user_id == user_id:
                return session
        
        # Create new if not found or not provided
        new_session = ChatSession(user_id=user_id, name="New Chat")
        self.db_session.add(new_session)
        self.db_session.commit()
        self.db_session.refresh(new_session)
        return new_session

    def get_messages(self, session_id: int) -> List[Message]:
        return self.db_session.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()
        
    def delete_session(self, user_id: int, session_id: int) -> bool:
        session = self.db_session.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return False
            
        messages = self.db_session.exec(select(Message).where(Message.session_id == session_id)).all()
        for message in messages:
            self.db_session.delete(message)
        
        self.db_session.delete(session)
        self.db_session.commit()
        return True

    def rename_session(self, user_id: int, session_id: int, new_name: str) -> Optional[ChatSession]:
        session = self.db_session.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            return None
        
        session.name = new_name
        self.db_session.add(session)
        self.db_session.commit()
        self.db_session.refresh(session)
        return session

    def process_chat_message(
        self,
        user: User,
        message: str,
        session_id: Optional[int] = None,
        mode: str = "general"
    ) -> Iterator[str]:
        """
        Process a chat message and yield response chunks.
        This generator yields JSON strings conforming to the streaming protocol.
        """
        start_time = time.time()
        
        # 1. Setup Session
        chat_session = self.get_or_create_session(user.id, session_id)
        session_id = chat_session.id
        
        # Auto-rename if needed
        if chat_session.name == "New Chat":
            chat_session.name = message[:30] + "..." if len(message) > 30 else message
            self.db_session.add(chat_session)
            self.db_session.commit()
        
        # 2. Persist User Message
        user_msg = Message(session_id=session_id, role="user", content=message)
        self.db_session.add(user_msg)
        self.db_session.commit()
        
        # 3. Build User HTML and Yield
        user_html = self._render_user_html(message)
        yield json.dumps({"type": "user_html", "html": user_html}) + "\n"

        # 4. RAG Retrieval (if needed)
        retrieval_results = []
        rag_time = 0.0
        confidence_info = {"level": "none", "score": 0.0}
        
        llm_messages = self._build_context(session_id)
        
        # Inject Thinking Prompt
        if settings.ENABLE_THINKING:
             llm_messages.insert(0, {"role": "system", "content": "You are a helpful assistant. Detailed thought process should be enclosed in <think> tags. Please think before you answer."})

        if mode == "policy":
            rag_start = time.time()
            retrieval_results = self.rag_service.hybrid_retrieve(message, self.db_session)
            confidence_info = self.rag_service.calculate_confidence(retrieval_results)
            rag_time = time.time() - rag_start
            
            system_prompt = self._build_rag_system_prompt(retrieval_results)
            llm_messages.insert(0, {"role": "system", "content": system_prompt})

        # 5. Send AI Start Event
        yield json.dumps({"type": "ai_start"}) + "\n"
        
        # 6. Generate Response (Streaming)
        llm_start = time.time()
        ai_response_text = ""
        
        try:
            # We always use generate_stream here for consistency, even if underlying config
            # implies non-streaming, we can wrap it. But our LLM service supports stream.
            for chunk in self.llm_service.generate_stream(llm_messages):
                ai_response_text += chunk
                yield json.dumps({"type": "token", "content": chunk}) + "\n"
        except Exception as e:
            logger.error(f"Generation error: {e}")
            ai_response_text += f" [Error: {str(e)}]"
            yield json.dumps({"type": "token", "content": f" [Error: {str(e)}]"}) + "\n"
            
        llm_time = time.time() - llm_start
        
        # 7. Generate Sources HTML
        sources_html = ""
        if mode == "policy" and retrieval_results:
             sources_html = self._render_sources_html(retrieval_results, confidence_info)
             yield json.dumps({"type": "sources", "html": sources_html}) + "\n"
             
        # 8. Persist AI Message
        ai_msg = Message(
            session_id=session_id, 
            role="assistant", 
            content=ai_response_text, 
            citations=sources_html if sources_html else None
        )
        self.db_session.add(ai_msg)
        self.db_session.commit()
        
        # 9. Log Metrics
        total_time = time.time() - start_time
        self._log_metrics(session_id, total_time, llm_time, rag_time)
        
        yield json.dumps({"type": "done", "sessionId": session_id}) + "\n"

    def _build_context(self, session_id: int, limit: int = 10) -> List[Dict]:
        history = self.db_session.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()[-limit:]
        
        return [{"role": m.role, "content": m.content} for m in history]

    def _render_user_html(self, message: str) -> str:
        return f"""
        <div class="message-wrapper user-wrapper">
            <div class="message-bubble user-message">{html.escape(message)}</div>
            <div class="message-actions">
                <button class="msg-action-btn btn-copy-msg" title="Copy"><i class="bi bi-clipboard"></i></button>
            </div>
        </div>
        """

    def _build_rag_system_prompt(self, retrieval_results: List) -> str:
        if not retrieval_results:
            return "You are a policy assistant. You do not have any relevant documents to answer this specific question. Please inform the user that you cannot answer based on available policies."
            
        context_content = "\n\n".join([f"--- Source {i+1} ---\n{r.window_content if hasattr(r, 'window_content') and r.window_content else r.chunk.content}" for i, r in enumerate(retrieval_results)])
        
        return f"""You are a helpful and strict policy assistant. Your goal is to answer user questions ACCURATELY based ONLY on the provided context documents.

INSTRUCTIONS:
1.  **Analyze the Request**: Understand the user's question and what specific policy information is needed.
2.  **Analyze the Context**: Carefully read the "CONTEXT_DOCUMENTS" provided below. This includes the relevant sections and their surrounding context.
3.  **Formulate Answer**: 
    - Answer the question directly using ONLY the information from the context.
    - Provide a detailed explanation if the context supports it.
    - If the context contains the answer, be comprehensive.
4.  **Anti-Hallucination**: 
    - Do NOT use any outside knowledge, assumptions, or information not explicitly present in the context.
    - If the answer is NOT in the context, strictly state: "I cannot answer this question based on the available policy documents."
5.  **Citations**: Cite your sources by referring to the specific Source numbers (e.g., "According to Source 1...").

CONTEXT_DOCUMENTS:
{context_content}
"""

    def _render_sources_html(self, retrieval_results: List, confidence_info: Dict) -> str:
        if not retrieval_results:
            return ""
            
        confidence_class = f"confidence-{confidence_info['level']}"
        confidence_icon = {
            "high": "bi-check-circle-fill",
            "medium": "bi-exclamation-circle-fill", 
            "low": "bi-question-circle-fill",
            "none": "bi-x-circle-fill"
        }.get(confidence_info['level'], "bi-info-circle")
        
        sources_html = f"""
        <div class="sources-container {confidence_class}">
            <div class="sources-header">
                <span class="sources-toggle"><i class="bi bi-chevron-right"></i></span>
                <span class="sources-title">
                    <i class="bi {confidence_icon}"></i> 
                    {confidence_info['num_sources']} Source{'s' if confidence_info['num_sources'] != 1 else ''} 
                    <span class="confidence-badge">{confidence_info['level'].title()} Confidence</span>
                </span>
            </div>
            <div class="sources-content">
        """
        
        for i, result in enumerate(retrieval_results):
            page_info = f" (Page {result.page_number})" if result.page_number else ""
            escaped_content = html.escape(result.chunk.content)
            preview_content = escaped_content[:200] + ('...' if len(escaped_content) > 200 else '')
            doc_id = result.chunk.document_id
            
            sources_html += f"""
                <div class="source-item" data-source-id="{i}">
                    <div class="source-header">
                        <span class="source-doc"><i class="bi bi-file-earmark-text"></i> {html.escape(result.document_name)}{page_info}</span>
                        <div class="source-actions">
                            <span class="source-score">{result.score * 100:.0f}% match</span>
                            <a href="/documents/{doc_id}/download" class="source-download-btn" title="Download document" target="_blank">
                                <i class="bi bi-download"></i>
                            </a>
                            <button class="source-copy-btn" title="Copy source text">
                                <i class="bi bi-clipboard"></i>
                            </button>
                        </div>
                    </div>
                    <div class="source-preview">{preview_content}</div>
                    <div class="source-full-content" style="display:none;">{escaped_content}</div>
                </div>
            """
        sources_html += "</div></div>"
        return sources_html

    def _log_metrics(self, session_id, total, llm, rag):
        app_overhead = total - llm - rag
        logger.info(
            f"Inference Time Breakdown (Session {session_id}): "
            f"Total: {total:.2f}s (100.0%), "
            f"App Overhead: {app_overhead:.2f}s ({app_overhead/total*100:.1f}%), "
            f"LLM: {llm:.2f}s ({llm/total*100:.1f}%), "
            f"RAG: {rag:.2f}s ({rag/total*100:.1f}%)"
        )
