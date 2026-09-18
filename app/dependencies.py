from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.auth_utils import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class CurrentUser:
    def __init__(self, id: int, role: str):
        self.id = id
        self.role = role

async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return CurrentUser(id=int(payload["sub"]), role=payload["role"])

async def require_organizer(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "organizer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organizer role required")
    return user