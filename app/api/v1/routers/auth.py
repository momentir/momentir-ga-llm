from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth_models import (
    LoginRequest, LoginResponse, SignUpRequest, RequestEmailVerificationRequest,
    RequestEmailVerificationResponse, VerifyEmailRequest, RequestPasswordResetRequest,
    ResetPasswordRequest, FindMyEmailResponse, ErrorResponse, MessageResponse
)
from app.api.v1.services.auth_service import AuthService
from app.api.v1.services.email_service import EmailService
from app.middleware.auth_middleware import get_current_user
from app.db_models.auth_models import User
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/auth", tags=["인증"])

# 설정 및 서비스 인스턴스 생성
settings = get_settings()
email_service = EmailService(
    aws_region=settings.AWS_REGION,
    access_key=settings.AWS_SES_ACCESS_KEY,
    secret_key=settings.AWS_SES_SECRET_ACCESS_KEY,
    from_email=settings.AWS_SES_FROM_EMAIL
)
auth_service = AuthService(email_service, settings.JWT_SECRET_KEY)


@router.post("/login", response_model=LoginResponse, summary="사용자 로그인")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    이메일과 비밀번호를 통해 사용자 로그인 처리
    """
    try:
        # 로그인 실패 횟수 확인
        failure_count = await auth_service.get_login_failure_count(db, request.email)
        if failure_count >= 3:
            raise HTTPException(
                status_code=400,
                detail="Too many login attempts. Please try again later."
            )
        
        response = await auth_service.login(db, request.email, request.password)
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout", response_model=MessageResponse, summary="사용자 로그아웃")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    인증된 사용자 로그아웃 처리
    """
    return MessageResponse(message="Logged out successfully")


@router.get("/find-my-email", response_model=FindMyEmailResponse, summary="이메일 찾기")
async def find_my_email(
    name: str = Query(..., description="사용자 이름"),
    phone: str = Query(..., description="전화번호"),
    db: AsyncSession = Depends(get_db)
):
    """
    이름과 전화번호를 통해 등록된 이메일 주소 찾기
    """
    try:
        if not name or not phone:
            raise HTTPException(
                status_code=400,
                detail="Name and phone are required"
            )
        
        response = await auth_service.find_my_email(db, name, phone)
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Find email error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reset-password", response_model=MessageResponse, summary="비밀번호 재설정 요청")
async def request_password_reset(
    request: RequestPasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    이메일로 비밀번호 재설정 링크 발송
    """
    try:
        await auth_service.request_password_reset(db, request.email)
        return MessageResponse(message="Password reset email sent")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/reset-password/password", response_model=MessageResponse, summary="비밀번호 재설정")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    재설정 토큰을 통해 새로운 비밀번호로 변경
    """
    try:
        await auth_service.reset_password(db, request.token, request.new_password)
        return MessageResponse(message="Password reset successful")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/request-email-verification", response_model=RequestEmailVerificationResponse, summary="이메일 인증 요청")
async def request_email_verification(
    request: RequestEmailVerificationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    이메일 주소로 인증 코드 발송 요청
    """
    try:
        response = await auth_service.request_email_verification(db, request.email)
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Email verification request error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/verify-email-account", response_model=MessageResponse, summary="이메일 계정 인증")
async def verify_email_account(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    발송된 인증 코드를 통해 이메일 계정 인증 처리
    """
    try:
        await auth_service.verify_email_account(
            db, request.email, request.verification_code, request.verification_id
        )
        return MessageResponse(message="Email account verified successfully.")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sign-up", response_model=LoginResponse, summary="사용자 회원가입")
async def sign_up(
    request: SignUpRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 사용자 계정 생성
    """
    try:
        response = await auth_service.sign_up(db, request)
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Sign up error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")