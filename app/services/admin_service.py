from sqlmodel import Session, select, func
from app.models.models import User, Document, Message, ChatSession, DocumentChunk
import os
import shutil
import logging
from app.core.config import settings

class AdminService:
    @staticmethod
    def get_dashboard_stats(session: Session):
        user_count = session.exec(select(func.count(User.id))).one()
        doc_count = session.exec(select(func.count(Document.id))).one()
        msg_count = session.exec(select(func.count(Message.id))).one()
        session_count = session.exec(select(func.count(ChatSession.id))).one()
        
        return {
            "users": user_count,
            "documents": doc_count,
            "messages": msg_count,
            "sessions": session_count
        }
    
    @staticmethod
    def delete_document(session: Session, doc_id: int) -> dict:
        """
        Delete a document, its chunks, and the physical file.
        Returns a dict with success status and any warnings.
        """
        result = {"success": False, "warnings": [], "doc_id": doc_id}
        
        doc = session.get(Document, doc_id)
        if not doc:
            result["error"] = "Document not found"
            return result
        
        # Delete file from disk - gracefully handle if file is missing
        file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Deleted file: {file_path}")
            except Exception as e:
                warning = f"Could not delete physical file {file_path}: {e}"
                logging.warning(warning)
                result["warnings"].append(warning)
        else:
            warning = f"Physical file not found: {file_path} (already deleted or moved)"
            logging.warning(warning)
            result["warnings"].append(warning)
        
        # Delete associated chunks first (explicit cleanup)
        try:
            chunks = session.exec(select(DocumentChunk).where(DocumentChunk.document_id == doc_id)).all()
            chunk_count = len(chunks)
            for chunk in chunks:
                session.delete(chunk)
            logging.info(f"Deleted {chunk_count} chunks for document {doc_id}")
        except Exception as e:
            warning = f"Error deleting chunks: {e}"
            logging.warning(warning)
            result["warnings"].append(warning)
        
        # Delete the document record
        try:
            session.delete(doc)
            session.commit()
            result["success"] = True
            logging.info(f"Deleted document {doc_id}: {doc.filename}")
        except Exception as e:
            session.rollback()
            result["error"] = f"Database error: {e}"
            logging.error(f"Failed to delete document {doc_id}: {e}")
        
        return result
    
    @staticmethod
    def reset_all_documents(session: Session) -> dict:
        """
        Delete ALL documents, chunks, and physical files.
        Returns a dict with counts and any warnings.
        """
        result = {
            "success": False,
            "documents_deleted": 0,
            "chunks_deleted": 0,
            "files_deleted": 0,
            "warnings": []
        }
        
        try:
            # Get all documents
            documents = session.exec(select(Document)).all()
            
            # Delete all physical files
            upload_dir = settings.UPLOAD_DIR
            if os.path.exists(upload_dir):
                for doc in documents:
                    file_path = os.path.join(upload_dir, doc.filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            result["files_deleted"] += 1
                        except Exception as e:
                            result["warnings"].append(f"Could not delete {doc.filename}: {e}")
            
            # Delete all chunks
            chunks = session.exec(select(DocumentChunk)).all()
            result["chunks_deleted"] = len(chunks)
            for chunk in chunks:
                session.delete(chunk)
            
            # Delete all documents
            result["documents_deleted"] = len(documents)
            for doc in documents:
                session.delete(doc)
            
            session.commit()
            result["success"] = True
            logging.info(f"Reset complete: {result['documents_deleted']} documents, {result['chunks_deleted']} chunks, {result['files_deleted']} files deleted")
            
        except Exception as e:
            session.rollback()
            result["error"] = str(e)
            logging.error(f"Reset failed: {e}")
        
        return result

    @staticmethod
    def create_user(session: Session, username, password, is_admin, email):
        from app.core.security import get_password_hash
        user = User(
            username=username,
            hashed_password=get_password_hash(password),
            is_admin=is_admin,
            email=email
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    
    @staticmethod
    def create_ldap_user(session: Session, username: str, email: str = None, is_admin: bool = False):
        """Create a user that will authenticate via LDAP only."""
        from app.api.auth import LDAP_USER_PLACEHOLDER_HASH
        user = User(
            username=username,
            hashed_password=LDAP_USER_PLACEHOLDER_HASH,
            is_admin=is_admin,
            email=email,
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        logging.info(f"Created LDAP user: {username}")
        return user
    
    @staticmethod
    def reset_password(session: Session, user_id: int, new_password: str) -> dict:
        """Reset a user's password to a new value."""
        from app.core.security import get_password_hash
        from app.api.auth import LDAP_USER_PLACEHOLDER_HASH
        
        result = {"success": False, "user_id": user_id}
        
        user = session.get(User, user_id)
        if not user:
            result["error"] = "User not found"
            return result
        
        # If user was LDAP-only, they now become a local user
        was_ldap = user.hashed_password == LDAP_USER_PLACEHOLDER_HASH
        
        user.hashed_password = get_password_hash(new_password)
        session.add(user)
        session.commit()
        
        result["success"] = True
        result["was_ldap"] = was_ldap
        if was_ldap:
            logging.info(f"User {user.username} converted from LDAP-only to local auth")
        else:
            logging.info(f"Password reset for user: {user.username}")
        
        return result
    
    @staticmethod
    def update_email(session: Session, user_id: int, new_email: str) -> dict:
        """Update a user's email address."""
        result = {"success": False, "user_id": user_id}
        
        user = session.get(User, user_id)
        if not user:
            result["error"] = "User not found"
            return result
        
        old_email = user.email
        user.email = new_email if new_email else None
        session.add(user)
        session.commit()
        
        result["success"] = True
        result["old_email"] = old_email
        result["new_email"] = user.email
        logging.info(f"Email updated for user {user.username}: {old_email} -> {new_email}")
        
        return result
    
    @staticmethod
    def update_user(session: Session, user_id: int, email: str = None, is_admin: bool = None) -> dict:
        """Update user details (email and/or admin status)."""
        result = {"success": False, "user_id": user_id}
        
        user = session.get(User, user_id)
        if not user:
            result["error"] = "User not found"
            return result
        
        changes = []
        if email is not None:
            old_email = user.email
            user.email = email if email else None
            if old_email != user.email:
                changes.append(f"email: {old_email} -> {user.email}")
        
        if is_admin is not None and user.is_admin != is_admin:
            user.is_admin = is_admin
            changes.append(f"is_admin: {is_admin}")
        
        if changes:
            session.add(user)
            session.commit()
            logging.info(f"User {user.username} updated: {', '.join(changes)}")
        
        result["success"] = True
        result["changes"] = changes
        return result
    
    @staticmethod
    def set_ldap_auth(session: Session, user_id: int) -> dict:
        """Convert a user to LDAP-only authentication."""
        from app.api.auth import LDAP_USER_PLACEHOLDER_HASH
        
        result = {"success": False, "user_id": user_id}
        
        user = session.get(User, user_id)
        if not user:
            result["error"] = "User not found"
            return result
        
        if user.hashed_password == LDAP_USER_PLACEHOLDER_HASH:
            result["error"] = "User is already LDAP-only"
            return result
        
        user.hashed_password = LDAP_USER_PLACEHOLDER_HASH
        session.add(user)
        session.commit()
        
        result["success"] = True
        logging.info(f"User {user.username} converted to LDAP-only auth")
        return result
