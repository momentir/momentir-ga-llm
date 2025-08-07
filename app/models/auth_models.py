from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="사용자 이메일 주소", example="user@example.com")
    password: str = Field(..., description="사용자 비밀번호", example="password123")


class LoginResponse(BaseModel):
    token: str = Field(..., description="JWT 인증 토큰", example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    expires_in: int = Field(..., description="토큰 만료 시간(초)", example=3600)


class SignUpRequest(BaseModel):
    name: str = Field(..., description="사용자 이름", example="홍길동")
    email: EmailStr = Field(..., description="이메일 주소", example="user@example.com")
    phone: str = Field(..., description="전화번호", example="010-1234-5678")
    password: str = Field(..., min_length=8, description="비밀번호 (8자 이상)", example="password123")
    agreed_marketing_opt_in: bool = Field(..., description="마케팅 수신 동의", example=True)


class RequestEmailVerificationRequest(BaseModel):
    email: EmailStr = Field(..., description="인증받을 이메일 주소", example="user@example.com")


class RequestEmailVerificationResponse(BaseModel):
    message: str = Field(..., description="응답 메시지", example="인증 코드가 이메일로 발송되었습니다.")
    verification_id: int = Field(..., description="인증 ID", example=12345)


class VerifyEmailRequest(BaseModel):
    email: EmailStr = Field(..., description="인증할 이메일 주소", example="user@example.com")
    verification_code: str = Field(..., description="이메일로 받은 인증 코드", example="123456")
    verification_id: int = Field(..., description="인증 요청 ID", example=12345)


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="비밀번호를 재설정할 이메일 주소", example="user@example.com")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="이메일로 받은 재설정 토큰", example="reset_token_abc123")
    new_password: str = Field(..., min_length=8, description="새로운 비밀번호 (8자 이상)", example="newpass123")


class FindMyEmailRequest(BaseModel):
    name: str = Field(..., description="사용자 이름", example="홍길동")
    phone: str = Field(..., description="전화번호", example="010-1234-5678")


class FindMyEmailResponse(BaseModel):
    masked_email: str = Field(..., description="마스킹된 이메일 주소", example="us***@example.com")


class ErrorResponse(BaseModel):
    message: str = Field(..., description="오류 메시지", example="요청 처리 중 오류가 발생했습니다.")
    errors: Optional[List[str]] = Field(None, description="상세 오류 목록", example=["필드 검증 실패"])


class MessageResponse(BaseModel):
    message: str = Field(..., description="응답 메시지")