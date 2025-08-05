"""
프롬프트 관리 시스템을 위한 SQLAlchemy 모델들
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, Float, ForeignKey, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)  # memo_refine, column_mapping, analysis
    template_content = Column(Text, nullable=False)
    variables = Column(JSONB, nullable=True)  # 템플릿 변수 정의
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True)

    # 관계
    versions = relationship("PromptVersion", back_populates="template", cascade="all, delete-orphan")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey('prompt_templates.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    template_content = Column(Text, nullable=False)
    variables = Column(JSONB, nullable=True)
    change_notes = Column(Text, nullable=True)
    is_published = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True)

    # 관계
    template = relationship("PromptTemplate", back_populates="versions")
    test_results = relationship("PromptTestResult", back_populates="version")


class PromptABTest(Base):
    __tablename__ = "prompt_ab_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    version_a_id = Column(UUID(as_uuid=True), ForeignKey('prompt_versions.id'), nullable=False)
    version_b_id = Column(UUID(as_uuid=True), ForeignKey('prompt_versions.id'), nullable=False)
    traffic_split = Column(Float, nullable=False, default=0.5)  # 0.0 ~ 1.0
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    success_metric = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True)

    # 관계
    version_a = relationship("PromptVersion", foreign_keys=[version_a_id])
    version_b = relationship("PromptVersion", foreign_keys=[version_b_id])
    test_results = relationship("PromptTestResult", back_populates="test", cascade="all, delete-orphan")


class PromptTestResult(Base):
    __tablename__ = "prompt_test_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey('prompt_ab_tests.id', ondelete='CASCADE'), nullable=False, index=True)
    version_id = Column(UUID(as_uuid=True), ForeignKey('prompt_versions.id'), nullable=False)
    user_session = Column(String(100), nullable=True)
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=True)
    quality_score = Column(Float, nullable=True)  # 0.0 ~ 1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # 관계
    test = relationship("PromptABTest", back_populates="test_results")
    version = relationship("PromptVersion", back_populates="test_results")


class PromptTestLog(Base):
    """프롬프트 테스트 로그 테이블 - 프롬프트 관리 시스템에서의 테스트 기록"""
    __tablename__ = "prompt_test_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_content = Column(Text, nullable=False, comment="테스트한 프롬프트 내용")
    memo_content = Column(Text, nullable=False, comment="입력된 메모 내용")  
    llm_response = Column(Text, nullable=False, comment="LLM 응답 내용")
    response_time_ms = Column(Integer, nullable=True, comment="응답 시간 (밀리초)")
    tokens_used = Column(Integer, nullable=True, comment="사용된 토큰 수")
    success = Column(Boolean, nullable=False, default=True, comment="성공 여부")
    error_message = Column(Text, nullable=True, comment="오류 메시지 (실패시)")
    user_session = Column(String(100), nullable=True, comment="사용자 세션 ID")
    source = Column(String(50), nullable=False, default="prompt_manager", comment="테스트 소스: prompt_manager, api_direct")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True, comment="요청일시")

    def __repr__(self):
        return f"<PromptTestLog(id={self.id}, created_at={self.created_at}, success={self.success})>"