import uuid
from sqlalchemy import Column, String, Text, DateTime, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class CustomerMemo(Base):
    """고객 메모 테이블 - PROJECT_CONTEXT.md의 customer_memos 스키마"""
    __tablename__ = "customer_memos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_memo = Column(Text, nullable=False, comment="원본 고객 메모")
    refined_memo = Column(JSONB, nullable=False, comment="정제된 메모 (JSON 형태)")
    embedding = Column(Vector(1536), nullable=True, comment="OpenAI embedding vector")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    analysis_results = relationship("AnalysisResult", back_populates="memo", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CustomerMemo(id={self.id}, created_at={self.created_at})>"


class AnalysisResult(Base):
    """분석 결과 테이블 - PROJECT_CONTEXT.md의 analysis_results 스키마"""
    __tablename__ = "analysis_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memo_id = Column(UUID(as_uuid=True), ForeignKey("customer_memos.id"), nullable=False)
    conditions = Column(JSONB, nullable=False, comment="분석 조건 (customer_type, contract_status 등)")
    analysis = Column(Text, nullable=False, comment="LLM 분석 결과")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    memo = relationship("CustomerMemo", back_populates="analysis_results")
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, memo_id={self.memo_id}, created_at={self.created_at})>"