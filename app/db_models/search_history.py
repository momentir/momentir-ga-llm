"""
검색 히스토리 데이터베이스 모델
PostgreSQL과 pgvector를 사용한 검색 분석 기능
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func as sql_func
from datetime import datetime
import uuid

from app.database import Base


class SearchHistory(Base):
    """
    검색 히스토리 테이블
    - 사용자의 모든 검색 쿼리 추적
    - SQL 생성 및 실행 결과 저장
    - 성능 메트릭 기록
    """
    __tablename__ = "search_history"
    
    # 기본 필드
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, nullable=False, comment="검색을 수행한 사용자 ID")
    
    # 검색 쿼리 정보
    query = Column(Text, nullable=False, comment="사용자가 입력한 자연어 검색 쿼리")
    query_hash = Column(String(64), nullable=False, comment="쿼리 중복 제거용 해시")
    
    # SQL 생성 결과
    sql_generated = Column(Text, nullable=True, comment="LLM이 생성한 SQL 쿼리")
    strategy_used = Column(String(50), nullable=True, comment="사용된 검색 전략")
    
    # 실행 결과
    success = Column(Boolean, default=False, nullable=False, comment="쿼리 실행 성공 여부")
    error_message = Column(Text, nullable=True, comment="실패 시 오류 메시지")
    result_count = Column(Integer, nullable=True, comment="반환된 결과 개수")
    
    # 성능 메트릭
    response_time = Column(Float, nullable=True, comment="총 응답 시간 (초)")
    sql_generation_time = Column(Float, nullable=True, comment="SQL 생성 시간 (초)")
    sql_execution_time = Column(Float, nullable=True, comment="SQL 실행 시간 (초)")
    
    # 메타데이터
    metadata_info = Column(JSONB, nullable=True, comment="추가 메타데이터 (JSON)")
    client_ip = Column(String(45), nullable=True, comment="클라이언트 IP 주소")
    user_agent = Column(Text, nullable=True, comment="사용자 에이전트")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), 
                       default=sql_func.now(), 
                       nullable=False,
                       comment="검색 수행 시각")
    updated_at = Column(DateTime(timezone=True), 
                       default=sql_func.now(), 
                       onupdate=sql_func.now(),
                       nullable=False,
                       comment="마지막 업데이트 시각")

    # 인덱스 설정 (성능 최적화)
    __table_args__ = (
        Index('idx_search_history_user_created', 'user_id', 'created_at'),
        Index('idx_search_history_query_hash', 'query_hash'),
        Index('idx_search_history_success_created', 'success', 'created_at'),
        Index('idx_search_history_response_time', 'response_time'),
        Index('idx_search_history_strategy', 'strategy_used'),
    )

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, user_id={self.user_id}, query='{self.query[:50]}...', success={self.success})>"


class SearchAnalytics(Base):
    """
    검색 분석 집계 테이블 (일별/시간별 통계)
    - 성능 최적화를 위한 사전 계산된 통계
    - 배치 작업으로 주기적 업데이트
    """
    __tablename__ = "search_analytics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 집계 기준
    analytics_date = Column(DateTime(timezone=True), nullable=False, comment="집계 날짜")
    analytics_type = Column(String(20), nullable=False, comment="집계 유형: daily, hourly")
    
    # 집계 통계
    total_searches = Column(Integer, default=0, comment="총 검색 횟수")
    successful_searches = Column(Integer, default=0, comment="성공한 검색 횟수")
    failed_searches = Column(Integer, default=0, comment="실패한 검색 횟수")
    
    # 성능 통계
    avg_response_time = Column(Float, nullable=True, comment="평균 응답 시간")
    min_response_time = Column(Float, nullable=True, comment="최소 응답 시간")
    max_response_time = Column(Float, nullable=True, comment="최대 응답 시간")
    
    # 인기 쿼리 (JSON 배열)
    popular_queries = Column(JSONB, nullable=True, comment="인기 검색어 목록")
    
    # 실패 패턴
    common_errors = Column(JSONB, nullable=True, comment="공통 오류 패턴")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), default=sql_func.now())
    updated_at = Column(DateTime(timezone=True), default=sql_func.now(), onupdate=sql_func.now())
    
    __table_args__ = (
        Index('idx_search_analytics_date_type', 'analytics_date', 'analytics_type'),
    )

    def __repr__(self):
        return f"<SearchAnalytics(date={self.analytics_date}, type={self.analytics_type}, total={self.total_searches})>"


class FrequentFailurePattern(Base):
    """
    자주 실패하는 쿼리 패턴 추적
    - 실패율이 높은 쿼리 패턴 자동 감지
    - 개선 제안을 위한 데이터
    """
    __tablename__ = "frequent_failure_patterns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 패턴 정보
    pattern_hash = Column(String(64), nullable=False, unique=True, comment="패턴 식별 해시")
    pattern_description = Column(Text, nullable=False, comment="실패 패턴 설명")
    example_query = Column(Text, nullable=False, comment="예시 쿼리")
    
    # 통계 정보
    failure_count = Column(Integer, default=1, comment="실패 횟수")
    total_attempts = Column(Integer, default=1, comment="총 시도 횟수")
    failure_rate = Column(Float, nullable=False, comment="실패율 (0.0-1.0)")
    
    # 최근 오류 정보
    last_error_message = Column(Text, nullable=True, comment="마지막 오류 메시지")
    last_failure_at = Column(DateTime(timezone=True), nullable=False, comment="마지막 실패 시각")
    
    # 자동 감지 정보
    detected_at = Column(DateTime(timezone=True), default=sql_func.now(), comment="패턴 최초 감지 시각")
    is_active = Column(Boolean, default=True, comment="활성 패턴 여부")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), default=sql_func.now())
    updated_at = Column(DateTime(timezone=True), default=sql_func.now(), onupdate=sql_func.now())
    
    __table_args__ = (
        Index('idx_frequent_failures_rate', 'failure_rate'),
        Index('idx_frequent_failures_active', 'is_active'),
    )

    def __repr__(self):
        return f"<FrequentFailurePattern(pattern='{self.pattern_description[:50]}...', failure_rate={self.failure_rate:.2f})>"