from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Request, Cookie
from jose import JWTError, jwt
from sqlmodel import Session
from app.core.database import get_session
from app.models.models import User
from app.core.security import SECRET_KEY, ALGORITHM

async def get_current_user_optional(
    request: Request,
    session: Session = Depends(get_session)
) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        # Remove "Bearer " prefix if present (though we just store the token directly usually)
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
        
    user = session.query(User).filter(User.username == username).first()
    return user

async def get_current_user(
    request: Request,
    current_user: Annotated[Optional[User], Depends(get_current_user_optional)]
) -> User:
    if not current_user:
        # Check if this is a browser request (accepts HTML) vs API request
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"X-Requires-Auth": "true"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user
