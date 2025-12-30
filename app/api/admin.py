from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Annotated

from app.core.database import get_session
from app.models.models import User, Document, DocumentChunk
from app.api.deps import get_current_admin

from app.services.admin_service import AdminService
from app.services.ingestion.parser import DocumentParser
from typing import List
import shutil
import os
import logging
from fastapi import UploadFile, File
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_admin)])
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_session)):
    stats = AdminService.get_dashboard_stats(session)
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "stats": stats,
        "active_page": "dashboard"
    })

@router.get("/users", response_class=HTMLResponse)
async def manage_users(request: Request, session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return templates.TemplateResponse("admin/users.html", {
        "request": request, 
        "users": users,
        "active_page": "users"
    })

@router.post("/users/create")
async def create_user_route(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    is_admin: Annotated[bool, Form()] = False,
    session: Session = Depends(get_session)
):
    try:
        AdminService.create_user(session, username, password, is_admin, email)
        # return HTML fragment for HTMX to append to table, or just reload page for simplicity
        return RedirectResponse(url="/admin/users", status_code=303)
    except Exception as e:
        # Simple error handling
        return f"Error: {e}"

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user:
        session.delete(user)
        session.commit()
        return {"success": True, "userId": user_id}
    return {"success": False, "error": "User not found"}

@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    new_password: Annotated[str, Form()],
    session: Session = Depends(get_session)
):
    """Reset a user's password."""
    result = AdminService.reset_password(session, user_id, new_password)
    return {
        "success": result.get("success", False),
        "userId": user_id,
        "wasLdap": result.get("was_ldap", False),
        "error": result.get("error")
    }

@router.post("/users/{user_id}/update-email")
async def update_email(
    user_id: int,
    email: Annotated[str, Form()] = "",
    session: Session = Depends(get_session)
):
    """Update a user's email address."""
    result = AdminService.update_email(session, user_id, email)
    return {
        "success": result.get("success", False),
        "userId": user_id,
        "oldEmail": result.get("old_email"),
        "newEmail": result.get("new_email"),
        "error": result.get("error")
    }

@router.post("/users/{user_id}/update")
async def update_user(
    user_id: int,
    email: Annotated[str, Form()] = None,
    is_admin: Annotated[bool, Form()] = None,
    session: Session = Depends(get_session)
):
    """Update user details (email and/or admin status)."""
    result = AdminService.update_user(session, user_id, email, is_admin)
    return {
        "success": result.get("success", False),
        "userId": user_id,
        "changes": result.get("changes", []),
        "error": result.get("error")
    }

@router.post("/users/{user_id}/set-ldap")
async def set_ldap_auth(
    user_id: int,
    session: Session = Depends(get_session)
):
    """Convert a user to LDAP-only authentication."""
    result = AdminService.set_ldap_auth(session, user_id)
    return {
        "success": result.get("success", False),
        "userId": user_id,
        "error": result.get("error")
    }

@router.post("/users/create-ldap")
async def create_ldap_user_route(
    request: Request,
    username: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    is_admin: Annotated[bool, Form()] = False,
    session: Session = Depends(get_session)
):
    """Create a user that will authenticate via LDAP only."""
    try:
        AdminService.create_ldap_user(session, username, email, is_admin)
        return RedirectResponse(url="/admin/users", status_code=303)
    except Exception as e:
        return f"Error: {e}"


@router.get("/files", response_class=HTMLResponse)
async def manage_files(request: Request, session: Session = Depends(get_session)):
    documents = session.exec(select(Document)).all()
    return templates.TemplateResponse("admin/files.html", {
        "request": request, 
        "documents": documents,
        "active_page": "files"
    })

@router.delete("/files/{doc_id}")
async def delete_file(doc_id: int, session: Session = Depends(get_session)):
    result = AdminService.delete_document(session, doc_id)
    return {
        "success": result.get("success", False),
        "docId": doc_id,
        "warnings": result.get("warnings", []),
        "error": result.get("error")
    }

@router.delete("/files/reset/all")
async def reset_all_files(session: Session = Depends(get_session)):
    """Delete all documents, their chunks (vectors), and physical files."""
    result = AdminService.reset_all_documents(session)
    return {
        "success": result.get("success", False),
        "documentsDeleted": result.get("documents_deleted", 0),
        "chunksDeleted": result.get("chunks_deleted", 0),
        "filesDeleted": result.get("files_deleted", 0),
        "warnings": result.get("warnings", []),
        "error": result.get("error")
    }

@router.post("/files/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    parser = DocumentParser()
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    
    results = []
    
    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        try:
            # Save file - use await file.read() for reliable complete file reading
            file_content = await file.read()
            logger.info(f"Received file {file.filename}: {len(file_content)} bytes from upload")
            
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
            
            # Verify saved file size
            saved_size = os.path.getsize(file_path)
            logger.info(f"Saved file {file.filename} to {file_path}: {saved_size} bytes on disk")
            
            if saved_size != len(file_content):
                logger.error(f"File size mismatch! Received {len(file_content)} bytes but saved {saved_size} bytes")
            
            # Parse file (Ingestion)
            logger.info(f"Parsing file: {file.filename} ({file.content_type})")
            content = parser.parse_file(file_path, file.content_type)
            logger.info(f"Successfully parsed {file.filename}. extracted {len(content)} chars.")
            
            # Save Document Record
            doc = Document(filename=file.filename, file_type=file.content_type)
            session.add(doc)
            session.commit()
            session.refresh(doc)
            
            # RAG Indexing
            from app.services.ingestion.rag_service import RAGService
            rag_service = RAGService()
            await rag_service.index_document(doc.id, content, session)
            
            results.append(f"✅ {file.filename} ({len(content)} chars) - Indexed")
            
        except Exception as e:
            logger.error(f"Failed to process file {file.filename}: {str(e)}", exc_info=True)
            results.append(f"❌ {file.filename}: {str(e)}")
            
    # For HTMX, we can just return a reload or the same list
    # Let's return a redirect to the files page which will reload the list
    return RedirectResponse(url="/admin/files", status_code=303)

@router.get("/files/{doc_id}/download")
async def download_file(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if not doc:
        return HTMLResponse("Document not found", status_code=404)
    
    file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        return HTMLResponse("Physical file not found", status_code=404)
        
    return FileResponse(file_path, filename=doc.filename)

@router.get("/files/{doc_id}/inspect", response_class=HTMLResponse)
async def inspect_file(
    request: Request, 
    doc_id: int, 
    session: Session = Depends(get_session)
):
    doc = session.get(Document, doc_id)
    if not doc:
        return HTMLResponse("Document not found", status_code=404)
        
    chunks = session.exec(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.id)
    ).all()
    
    
    return templates.TemplateResponse("admin/file_inspect.html", {
        "request": request,
        "document": doc,
        "chunks": chunks,
        "active_page": "files"
    })

@router.get("/tools/convert", response_class=HTMLResponse)
async def convert_tool(request: Request, session: Session = Depends(get_session)):
    """Render the MarkItDown conversion tool page."""
    return templates.TemplateResponse("admin/convert.html", {
        "request": request,
        "active_page": "tools"
    })

@router.post("/tools/convert")
async def convert_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Handle file conversion to Markdown."""
    parser = DocumentParser()
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save temporarily
    temp_path = os.path.join(upload_dir, f"temp_{file.filename}")
    
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
            
        # Parse
        logger.info(f"Converting file: {file.filename}")
        markdown_content = parser.parse_file(temp_path, file.content_type)
        
        return {
            "success": True,
            "filename": file.filename,
            "markdown": markdown_content
        }
        
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
