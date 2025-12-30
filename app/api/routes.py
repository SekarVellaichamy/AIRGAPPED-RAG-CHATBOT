from fastapi import APIRouter, UploadFile, File, Form, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse

from fastapi.templating import Jinja2Templates
from typing import List, Annotated, Optional
from sqlmodel import Session, select, desc
import shutil
import os
import logging
import json
import time

from app.core.config import settings
from app.services.llm import get_llm_service
from app.services.ingestion.parser import DocumentParser
from app.services.chat_service import ChatService
from app.core.database import get_session
from app.models.models import User, ChatSession, Message, Document
from app.api.deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)

@router.get("/", response_class=HTMLResponse)
async def get_chat_interface(
    request: Request,
    session_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_session)
):
    # Fetch all sessions for this user, ordered by latest
    sessions = db_session.exec(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.created_at))
    ).all()

    # Auto-load latest session or create new one if no session_id provided
    if not session_id:
        if sessions:
            return RedirectResponse(url=f"/?session_id={sessions[0].id}")
        else:
            # Create new session
            new_session = ChatSession(user_id=current_user.id, name="New Chat")
            db_session.add(new_session)
            db_session.commit()
            db_session.refresh(new_session)
            return RedirectResponse(url=f"/?session_id={new_session.id}")

    current_chat_session = None
    messages = []
    
    if session_id:
        current_chat_session = db_session.get(ChatSession, session_id)
        # Verify ownership
        if current_chat_session and current_chat_session.user_id == current_user.id:
            messages = db_session.exec(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at)
            ).all()
        else:
            # Invalid session or not owner, redirect to new chat
            return RedirectResponse(url="/")
            
    return templates.TemplateResponse("chat.html", {
        "request": request, 
        "llm_provider": settings.LLM_PROVIDER,
        "user": current_user,
        "sessions": sessions,
        "current_session": current_chat_session,
        "messages": messages,
        "enable_streaming": settings.ENABLE_STREAMING
    })

@router.post("/chat/new", response_class=RedirectResponse)
async def create_new_chat(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_session)
):
    chat_service = ChatService(db_session)
    new_session = chat_service.get_or_create_session(current_user.id)
    return RedirectResponse(url=f"/?session_id={new_session.id}", status_code=303)

@router.post("/chat", response_class=StreamingResponse)
async def chat(
    request: Request, 
    message: Annotated[str, Form()],
    session_id: Annotated[Optional[int], Form()] = None,
    mode: Annotated[str, Form()] = "general",
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_session)
):
    chat_service = ChatService(db_session)
    
    # Validate mode
    if mode not in ["general", "policy"]:
        mode = "general"
        
    return StreamingResponse(
        chat_service.process_chat_message(current_user, message, session_id, mode),
        media_type="application/x-ndjson"
    )

@router.delete("/chat/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_session)
):
    chat_service = ChatService(db_session)
    success = chat_service.delete_session(current_user.id, session_id)
    
    if not success:
        raise HTTPException(status_code=403, detail="Invalid session or not authorized")
    
    return {"success": True, "sessionId": session_id}


@router.put("/chat/{session_id}")
async def rename_chat_session(
    session_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_session)
):
    # Parse JSON body
    body = await request.json()
    new_name = body.get("name", "").strip()
    
    if not new_name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    
    if len(new_name) > 100:
        raise HTTPException(status_code=400, detail="Name is too long (max 100 characters)")
        
    chat_service = ChatService(db_session)
    session = chat_service.rename_session(current_user.id, session_id, new_name)
    
    if not session:
        raise HTTPException(status_code=403, detail="Invalid session or not authorized")
    
    return {"success": True, "sessionId": session_id, "name": session.name}


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_session)
):
    """Download a reference document by its ID."""
    document = db_session.get(Document, document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Build file path with path traversal protection
    # Sanitize filename to prevent directory traversal attacks
    safe_filename = os.path.basename(document.filename)  # Remove any path components
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    
    # Resolve to absolute path and verify it's within UPLOAD_DIR
    abs_file_path = os.path.realpath(file_path)
    abs_upload_dir = os.path.realpath(settings.UPLOAD_DIR)
    
    if not abs_file_path.startswith(abs_upload_dir):
        logger.warning(f"Path traversal attempt detected: {document.filename}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(abs_file_path):
        logger.warning(f"Document file not found on disk: {abs_file_path}")
        raise HTTPException(status_code=404, detail="Document file not found on disk")
    
    # Determine media type based on file extension
    media_type_map = {
        "pdf": "application/pdf",
        "txt": "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "md": "text/markdown",
    }
    
    file_ext = document.file_type.lower()
    media_type = media_type_map.get(file_ext, "application/octet-stream")
    
    logger.info(f"User {current_user.username} downloading document: {document.filename}")
    
    return FileResponse(
        path=abs_file_path,
        filename=safe_filename,
        media_type=media_type
    )
