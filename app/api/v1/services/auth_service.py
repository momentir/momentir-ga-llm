from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
import jwt
import secrets
import random
import string
from uuid import uuid4

from app.db_models.auth_models import User, EmailVerification, LoginFailure, PasswordResetToken
from app.models.auth_models import (
    LoginResponse, SignUpRequest, RequestEmailVerificationResponse,
    FindMyEmailResponse
)
from app.services.email_service import EmailService


class AuthService:
    def __init__(self, email_service: EmailService, jwt_secret: str):
        self.email_service = email_service
        self.jwt_secret = jwt_secret
        self.jwt_expires_in = 60 * 60 * 24  # 24 hours
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    async def login(self, db: AsyncSession, email: str, password: str) -> LoginResponse:
        # Check user exists and is completed
        stmt = select(User).where(
            User.email == email,
            User.sign_up_status == "COMPLETED",
            User.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            await self._record_login_failure(db, email, "INVALID_EMAIL")
            failure_count = await self._get_login_failure_count(db, email)
            raise ValueError(f"계정 또는 비밀번호에 오류가 있습니다. (실패횟수: {failure_count})")
        
        # Verify password
        if not self.pwd_context.verify(password, user.encrypted_password):
            await self._record_login_failure(db, email, "INVALID_PASSWORD")
            failure_count = await self._get_login_failure_count(db, email)
            raise ValueError(f"계정 또는 비밀번호에 오류가 있습니다. (실패횟수: {failure_count})")
        
        # Generate JWT token
        token = self._generate_jwt_token(user)
        
        return LoginResponse(
            token=token,
            expires_in=self.jwt_expires_in
        )
    
    async def get_login_failure_count(self, db: AsyncSession, email: str) -> int:
        return await self._get_login_failure_count(db, email)
    
    async def _get_login_failure_count(self, db: AsyncSession, email: str) -> int:
        one_hour_ago = datetime.now() - timedelta(hours=1)
        from sqlalchemy import func
        stmt = select(func.count(LoginFailure.id)).where(
            LoginFailure.email == email,
            LoginFailure.created_at > one_hour_ago
        )
        result = await db.execute(stmt)
        return result.scalar()
    
    async def _record_login_failure(self, db: AsyncSession, email: str, reason: str):
        failure = LoginFailure(
            email=email,
            failure_reason=reason
        )
        db.add(failure)
        await db.commit()
    
    async def request_email_verification(self, db: AsyncSession, email: str) -> RequestEmailVerificationResponse:
        code = self._generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        verification = EmailVerification(
            email=email,
            verification_code=code,
            expires_at=expires_at
        )
        
        db.add(verification)
        await db.flush()  # Flush to get the ID
        await db.refresh(verification)
        
        # Debug: Print verification ID
        print(f"DEBUG: verification.id = {verification.id}")
        
        if verification.id is None:
            raise ValueError("Failed to create verification record.")
        
        await db.commit()
        
        try:
            await self.email_service.send_verification_code_email(email, code)
        except Exception as e:
            raise ValueError("Failed to send verification email. Please try again.")
        
        return RequestEmailVerificationResponse(
            message="Verification email sent. Please check your inbox.",
            verification_id=verification.id
        )
    
    async def verify_email_account(self, db: AsyncSession, email: str, code: str, verification_id: int) -> None:
        stmt = select(EmailVerification).where(
            EmailVerification.id == verification_id,
            EmailVerification.email == email
        )
        result = await db.execute(stmt)
        verification = result.scalar_one_or_none()
        
        if not verification:
            raise ValueError("Verification request not found or email does not match.")
        
        if verification.verified_at:
            raise ValueError("This email verification request has already been completed.")
        
        if datetime.now() > verification.expires_at:
            raise ValueError("Verification code has expired. Please request a new one.")
        
        if verification.verification_code != code:
            raise ValueError("Invalid verification code.")
        
        verification.verified_at = datetime.now()
        await db.commit()
    
    async def sign_up(self, db: AsyncSession, req: SignUpRequest) -> LoginResponse:
        # Check if email is verified
        email_verification = db.query(EmailVerification).filter(
            EmailVerification.email == req.email
        ).order_by(EmailVerification.created_at.desc()).first()
        
        if not email_verification or not email_verification.verified_at:
            raise ValueError("이메일 주소가 인증되지 않았습니다. 이메일 인증 후 다시 시도해주세요.")
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == req.email).first()
        if existing_user:
            if existing_user.sign_up_status == "COMPLETED":
                raise ValueError("이미 가입한 이메일 주소입니다.")
            # Delete incomplete user
            db.delete(existing_user)
            db.commit()
        
        # Create new user
        hashed_password = self.pwd_context.hash(req.password)
        
        user = User(
            name=req.name,
            email=req.email,
            phone=req.phone,
            encrypted_password=hashed_password,
            sign_up_token=str(uuid4()),
            agreed_marketing_opt_in=req.agreed_marketing_opt_in,
            sign_up_status="COMPLETED"
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Generate JWT token
        token = self._generate_jwt_token(user)
        
        return LoginResponse(
            token=token,
            expires_in=self.jwt_expires_in
        )
    
    async def find_my_email(self, db: AsyncSession, name: str, phone: str) -> FindMyEmailResponse:
        user = db.query(User).filter(
            User.name == name,
            User.phone == phone,
            User.sign_up_status == "COMPLETED",
            User.deleted_at.is_(None)
        ).first()
        
        if not user:
            raise ValueError("가입한 이메일이 존재하지 않습니다.")
        
        masked_email = self._mask_email(user.email)
        return FindMyEmailResponse(masked_email=masked_email)
    
    async def request_password_reset(self, db: AsyncSession, email: str) -> None:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("User not found")
        
        # Generate password reset token
        payload = {
            "sub": user.id,
            "email": user.email,
            "type": "password_reset",
            "exp": datetime.now() + timedelta(hours=1)
        }
        
        token_string = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token_string,
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        db.add(reset_token)
        db.commit()
        
        await self.email_service.send_password_reset_email(email, token_string)
    
    async def reset_password(self, db: AsyncSession, token_string: str, new_password: str) -> None:
        try:
            payload = jwt.decode(token_string, self.jwt_secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
        
        user_id = payload.get("sub")
        email = payload.get("email")
        token_type = payload.get("type")
        
        if token_type != "password_reset":
            raise ValueError("Invalid token type for password reset")
        
        user = db.query(User).filter(
            User.id == user_id,
            User.email == email
        ).first()
        
        if not user:
            raise ValueError("User not found")
        
        # Update password
        hashed_password = self.pwd_context.hash(new_password)
        user.encrypted_password = hashed_password
        
        # Delete all password reset tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id
        ).delete()
        
        db.commit()
    
    def verify_token(self, token_string: str) -> dict:
        try:
            payload = jwt.decode(token_string, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    def _generate_jwt_token(self, user: User) -> str:
        payload = {
            "userId": user.id,
            "email": user.email,
            "name": user.name,
            "exp": datetime.now() + timedelta(seconds=self.jwt_expires_in),
            "iat": datetime.now()
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
    
    def _generate_verification_code(self) -> str:
        return f"{random.randint(100000, 999999):06d}"
    
    def _mask_email(self, email: str) -> str:
        parts = email.split("@")
        if len(parts) != 2:
            return email
        
        name = parts[0]
        domain = parts[1]
        name_len = len(name)
        mask_len = name_len // 2
        
        if mask_len == 0:
            mask_len = 1
        
        masked = name[:name_len - mask_len] + "*" * mask_len
        return f"{masked}@{domain}"