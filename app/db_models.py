import uuid
import os
from sqlalchemy import Column, String, Text, DateTime, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR
from app.database import Base

# Mock 모드 체크
USE_MOCK_MODE = os.getenv("USE_MOCK_MODE", "false").lower() == "true"

if not USE_MOCK_MODE:
    from pgvector.sqlalchemy import Vector
else:
    # SQLite용 Mock Vector 타입
    class Vector(TypeDecorator):
        impl = Text
        def process_bind_param(self, value, dialect):
            if value is None:
                return value
            return str(value)
        def process_result_value(self, value, dialect):
            if value is None:
                return value
            return eval(value)

# UUID 타입을 SQLite와 호환되도록 수정
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


# JSON 타입을 데이터베이스에 따라 동적으로 설정
if USE_MOCK_MODE:
    from sqlalchemy import JSON as JsonType
else:
    JsonType = JSONB


class CustomerMemo(Base):
    """고객 메모 테이블 - PROJECT_CONTEXT_NEW.md의 memos 스키마"""
    __tablename__ = "customer_memos"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(String(255), nullable=True, comment="고객 ID")
    original_memo = Column(Text, nullable=False, comment="원본 고객 메모")
    refined_memo = Column(JsonType, nullable=True, comment="정제된 메모 (JSON 형태)")
    status = Column(String(20), default="draft", comment="메모 상태: draft, refined, confirmed")
    author = Column(String(100), nullable=True, comment="작성자")
    embedding = Column(Vector(1536), nullable=True, comment="OpenAI embedding vector")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    analysis_results = relationship("AnalysisResult", back_populates="memo", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CustomerMemo(id={self.id}, created_at={self.created_at})>"


class AnalysisResult(Base):
    """분석 결과 테이블 - PROJECT_CONTEXT.md의 analysis_results 스키마"""
    __tablename__ = "analysis_results"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    memo_id = Column(GUID(), ForeignKey("customer_memos.id"), nullable=False)
    conditions = Column(JsonType, nullable=False, comment="분석 조건 (customer_type, contract_status 등)")
    analysis = Column(Text, nullable=False, comment="LLM 분석 결과")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    memo = relationship("CustomerMemo", back_populates="analysis_results")
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, memo_id={self.memo_id}, created_at={self.created_at})>"