from fastapi import APIRouter, Depends, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import timedelta
from typing import Annotated
import logging

from app.core.database import get_session
from app.models.models import User
from app.core.security import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.config import settings
from app.services.ldap_service import ldap_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Placeholder hash for LDAP-authenticated users (they don't have local passwords)
LDAP_USER_PLACEHOLDER_HASH = "LDAP_EXTERNAL_AUTH"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    session: Session = Depends(get_session)
):
    user = None
    
    # Step 1: Check if user exists in database (required)
    db_user = session.exec(select(User).where(User.username == username)).first()
    
    if not db_user:
        # User must exist in database - no auto-creation
        logger.info(f"Login attempt for non-existent user: {username}")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    # Step 2: Check if user is active
    if not db_user.is_active:
        logger.info(f"Login attempt for inactive user: {username}")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Your account is inactive. Please contact your administrator."
        })
    
    # Step 3: Authenticate the existing user
    if db_user.hashed_password == LDAP_USER_PLACEHOLDER_HASH:
        # This is an LDAP-only user - must authenticate via LDAP
        if ldap_service.is_available():
            ldap_result = ldap_service.authenticate(username, password)
            if ldap_result:
                user = db_user
                # Update email from LDAP if not set locally
                if ldap_result.get("email") and not db_user.email:
                    db_user.email = ldap_result["email"]
                    session.add(db_user)
                    session.commit()
                logger.info(f"LDAP user {username} authenticated via LDAP")
        else:
            # LDAP not available - inform user
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "LDAP authentication is currently unavailable. Please contact your administrator."
            })
    else:
        # Regular local user - try local password first
        if verify_password(password, db_user.hashed_password):
            user = db_user
            logger.info(f"User {username} authenticated via local database")
        elif ldap_service.is_available():
            # Local password failed - try LDAP as fallback
            ldap_result = ldap_service.authenticate(username, password)
            if ldap_result:
                user = db_user
                logger.info(f"User {username} authenticated via LDAP (fallback)")
    
    # Step 4: Authentication failed
    if not user:
        logger.info(f"Authentication failed for user: {username}")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    # Step 5: Create session token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Check if admin to redirect correctly
    redirect_url = "/admin/dashboard" if user.is_admin else "/"
    
    # We return a redirect, but we set the cookie on it
    resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="access_token", 
        value=f"{access_token}", 
        httponly=True,
        samesite="lax",  # CSRF protection
        secure=settings.SECURE_COOKIES,  # Only send over HTTPS when enabled
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return resp


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response
