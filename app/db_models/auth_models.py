from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)
    email = Column(String(60), nullable=False, unique=True, index=True)
    encrypted_password = Column(String(256), nullable=False)
    phone = Column(String(30), nullable=False)
    sign_up_token = Column(String(50))
    reset_password_token = Column(String(256))
    agreed_marketing_opt_in = Column(Boolean, default=False)
    sign_up_status = Column(String(20), default="IN_PROGRESS")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Relationships
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")
    customers = relationship("Customer", back_populates="user")


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    
    id = Column(BigInteger, primary_key=True, index=True)
    email = Column(String(60), nullable=False, index=True)
    verification_code = Column(String(10), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LoginFailure(Base):
    __tablename__ = "login_failures"
    
    id = Column(BigInteger, primary_key=True, index=True)
    email = Column(String(60), nullable=False, index=True)
    failure_reason = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    token = Column(String(256), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")