from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from typing import Optional

from app.database import get_db
from app.db_models.auth_models import User
from app.services.auth_service import AuthService


security = HTTPBearer()


class AuthMiddleware:
    def __init__(self, auth_service: AuthService):
        self.auth_service = auth_service
    
    async def __call__(self, 
                       credentials: HTTPAuthorizationCredentials,
                       db: AsyncSession) -> User:
        """
        JWT 토큰을 검증하고 사용자 정보를 반환하는 의존성
        """
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = credentials.credentials
        
        try:
            # JWT 토큰 검증
            payload = self.auth_service.verify_token(token)
            user_id = payload.get("userId")
            email = payload.get("email")
            
            if not user_id or not email:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token payload",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # 사용자 존재 여부 확인
            from sqlalchemy import select
            stmt = select(User).where(
                User.id == user_id,
                User.email == email,
                User.deleted_at.is_(None)
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            return user
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail="Token validation failed",
                headers={"WWW-Authenticate": "Bearer"}
            )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """현재 인증된 사용자를 반환하는 의존성"""
    auth_service = AuthService(db)
    auth_middleware = AuthMiddleware(auth_service)
    return await auth_middleware(credentials, db)


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    선택적으로 현재 인증된 사용자를 반환하는 의존성
    토큰이 없거나 유효하지 않아도 에러를 발생시키지 않음
    """
    if not credentials:
        return None
    
    try:
        auth_service = AuthService(db)
        auth_middleware = AuthMiddleware(auth_service)
        return await auth_middleware(credentials, db)
    except HTTPException:
        return None