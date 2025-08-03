import uuid
from sqlalchemy import Column, String, Text, DateTime, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class CustomerMemo(Base):
    """고객 메모 테이블 - PROJECT_CONTEXT_NEW.md의 memos 스키마"""
    __tablename__ = "customer_memos"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(), ForeignKey("customers.customer_id"), nullable=True, comment="고객 ID")
    original_memo = Column(Text, nullable=False, comment="원본 고객 메모")
    refined_memo = Column(JSONB, nullable=True, comment="정제된 메모 (JSON 형태)")
    status = Column(String(20), default="draft", comment="메모 상태: draft, refined, confirmed")
    author = Column(String(100), nullable=True, comment="작성자")
    embedding = Column(JSONB, nullable=True, comment="OpenAI embedding vector (stored as JSON array)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    customer = relationship("Customer", back_populates="memos")
    analysis_results = relationship("AnalysisResult", back_populates="memo", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="memo", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CustomerMemo(id={self.id}, created_at={self.created_at})>"


class Customer(Base):
    """고객 테이블 - PROJECT_CONTEXT_NEW.md의 customers 스키마"""
    __tablename__ = "customers"
    
    customer_id = Column(UUID(), primary_key=True, default=uuid.uuid4, comment="고객 ID")
    name = Column(String(100), nullable=True, comment="고객 이름")
    contact = Column(String(50), nullable=True, comment="연락처")
    affiliation = Column(String(200), nullable=True, comment="소속")
    occupation = Column(String(100), nullable=True, comment="직업")
    gender = Column(String(10), nullable=True, comment="성별")
    date_of_birth = Column(DateTime, nullable=True, comment="생년월일")
    interests = Column(JSONB, nullable=True, comment="관심사")
    life_events = Column(JSONB, nullable=True, comment="인생 이벤트")
    insurance_products = Column(JSONB, nullable=True, comment="보험 상품 정보")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="수정 시간")
    
    # 관계 설정
    memos = relationship("CustomerMemo", back_populates="customer", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="customer", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Customer(customer_id={self.customer_id}, name={self.name}, created_at={self.created_at})>"


class Event(Base):
    """이벤트 테이블 - PROJECT_CONTEXT_NEW.md의 events 스키마"""
    __tablename__ = "events"
    
    event_id = Column(UUID(), primary_key=True, default=uuid.uuid4, comment="이벤트 ID")
    customer_id = Column(UUID(), ForeignKey("customers.customer_id"), nullable=False, comment="고객 ID")
    memo_id = Column(UUID(), ForeignKey("customer_memos.id"), nullable=True, comment="관련 메모 ID")
    event_type = Column(String(50), nullable=False, comment="이벤트 타입: call, message, reminder, calendar")
    scheduled_date = Column(DateTime, nullable=True, comment="예정 날짜")
    priority = Column(String(10), default="medium", comment="우선순위: high, medium, low")
    status = Column(String(20), default="pending", comment="상태: pending, completed, cancelled")
    description = Column(Text, nullable=True, comment="이벤트 설명")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    customer = relationship("Customer", back_populates="events")
    memo = relationship("CustomerMemo", back_populates="events")
    
    def __repr__(self):
        return f"<Event(event_id={self.event_id}, event_type={self.event_type}, scheduled_date={self.scheduled_date})>"


class AnalysisResult(Base):
    """분석 결과 테이블 - PROJECT_CONTEXT.md의 analysis_results 스키마"""
    __tablename__ = "analysis_results"
    
    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    memo_id = Column(UUID(), ForeignKey("customer_memos.id"), nullable=False)
    conditions = Column(JSONB, nullable=False, comment="분석 조건 (customer_type, contract_status 등)")
    analysis = Column(Text, nullable=False, comment="LLM 분석 결과")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성 시간")
    
    # 관계 설정
    memo = relationship("CustomerMemo", back_populates="analysis_results")
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, memo_id={self.memo_id}, created_at={self.created_at})>"