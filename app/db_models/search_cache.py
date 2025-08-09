"""
검색 캐시 데이터베이스 모델

PostgreSQL 기반 검색 결과 캐싱 시스템:
- 5분 TTL 자동 삭제 (TRIGGER 활용)
- MD5 해시 기반 쿼리 키
- 인기 검색어 통계 자동 집계
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib

from sqlalchemy import Column, String, Text, DateTime, Integer, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates

from app.database import Base

class SearchCache(Base):
    """
    검색 결과 캐시 테이블
    
    PostgreSQL 특화 기능 활용:
    - JSONB로 결과 저장 (인덱싱 가능)
    - TRIGGER로 TTL 자동 삭제
    - 통계 집계 자동화
    """
    __tablename__ = "search_cache"

    # 기본 필드
    query_hash = Column(String(32), primary_key=True, comment="MD5 해시된 쿼리 키")
    original_query = Column(Text, nullable=False, comment="원본 검색 쿼리")
    query_context = Column(JSONB, nullable=True, comment="쿼리 컨텍스트 (검색 옵션 등)")
    
    # 캐시된 결과
    result = Column(JSONB, nullable=False, comment="검색 결과 (JSON 형태)")
    result_metadata = Column(JSONB, nullable=True, comment="결과 메타데이터")
    
    # 캐시 관리
    created_at = Column(
        DateTime(timezone=True), 
        default=datetime.utcnow,
        nullable=False,
        comment="캐시 생성 시간"
    )
    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow() + timedelta(minutes=5),
        nullable=False,
        comment="캐시 만료 시간 (5분)"
    )
    last_accessed = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="마지막 접근 시간"
    )
    
    # 통계
    hit_count = Column(Integer, default=1, nullable=False, comment="캐시 히트 수")
    total_rows = Column(Integer, default=0, nullable=False, comment="결과 행 수")
    execution_time_ms = Column(Integer, default=0, nullable=False, comment="실행 시간 (ms)")
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_search_cache_expires_at', 'expires_at'),
        Index('idx_search_cache_created_at', 'created_at'),
        Index('idx_search_cache_hit_count', 'hit_count'),
        Index('idx_search_cache_query_gin', 'original_query', postgresql_using='gin', postgresql_ops={'original_query': 'gin_trgm_ops'}),
        {'comment': '검색 결과 캐시 테이블 - 5분 TTL with PostgreSQL TRIGGER'}
    )

    @classmethod
    def generate_cache_key(
        cls, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        쿼리와 컨텍스트를 기반으로 MD5 캐시 키 생성
        
        Args:
            query: 검색 쿼리
            context: 검색 컨텍스트
            options: 검색 옵션
            
        Returns:
            MD5 해시 문자열 (32자)
        """
        # 정규화된 키 생성
        normalized_query = query.strip().lower()
        
        key_components = [normalized_query]
        
        if context:
            # 컨텍스트를 정렬하여 일관된 키 생성
            context_str = str(sorted(context.items()))
            key_components.append(context_str)
            
        if options:
            # 중요한 옵션만 키에 포함 (캐시 효율성 위해)
            important_options = {
                k: v for k, v in options.items() 
                if k in ['strategy', 'limit', 'timeout_seconds']
            }
            if important_options:
                options_str = str(sorted(important_options.items()))
                key_components.append(options_str)
        
        # MD5 해시 생성
        combined_key = "|".join(key_components)
        return hashlib.md5(combined_key.encode('utf-8')).hexdigest()

    @validates('result')
    def validate_result(self, key, result):
        """결과 데이터 검증"""
        if not isinstance(result, dict):
            raise ValueError("결과는 딕셔너리 형태여야 합니다")
        return result

    @validates('hit_count')
    def validate_hit_count(self, key, hit_count):
        """히트 카운트 검증"""
        if hit_count < 0:
            raise ValueError("히트 카운트는 0 이상이어야 합니다")
        return hit_count

    def is_expired(self) -> bool:
        """캐시 만료 여부 확인"""
        return datetime.utcnow() >= self.expires_at

    def extend_ttl(self, minutes: int = 5):
        """캐시 TTL 연장"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        self.last_accessed = datetime.utcnow()

    def increment_hit_count(self):
        """히트 카운트 증가"""
        self.hit_count += 1
        self.last_accessed = datetime.utcnow()

    def to_cache_response(self) -> Dict[str, Any]:
        """캐시 응답 형태로 변환"""
        return {
            "cached": True,
            "cache_key": self.query_hash,
            "hit_count": self.hit_count,
            "cached_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            **self.result
        }

    def __repr__(self):
        return f"<SearchCache(query_hash='{self.query_hash}', hits={self.hit_count}, expires_at='{self.expires_at}')>"


class PopularSearchQuery(Base):
    """
    인기 검색어 통계 테이블
    
    TRIGGER를 통해 search_cache에서 자동으로 집계됩니다.
    """
    __tablename__ = "popular_search_queries"

    # 기본 필드
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(Text, nullable=False, unique=True, comment="검색 쿼리")
    query_normalized = Column(String(1000), nullable=False, comment="정규화된 쿼리")
    
    # 통계 데이터
    total_searches = Column(Integer, default=0, nullable=False, comment="총 검색 수")
    unique_cache_hits = Column(Integer, default=0, nullable=False, comment="고유 캐시 히트 수")
    total_cache_hits = Column(Integer, default=0, nullable=False, comment="총 캐시 히트 수")
    avg_execution_time_ms = Column(Integer, default=0, nullable=False, comment="평균 실행 시간")
    
    # 시간 정보
    first_searched_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        comment="최초 검색 시간"
    )
    last_searched_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="마지막 검색 시간"
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="통계 업데이트 시간"
    )

    # 인덱스
    __table_args__ = (
        Index('idx_popular_queries_total_searches', 'total_searches'),
        Index('idx_popular_queries_last_searched', 'last_searched_at'),
        Index('idx_popular_queries_normalized', 'query_normalized'),
        {'comment': '인기 검색어 통계 - search_cache TRIGGER로 자동 업데이트'}
    )

    @classmethod
    def normalize_query(cls, query: str) -> str:
        """쿼리 정규화 (통계용)"""
        return query.strip().lower()

    def calculate_popularity_score(self) -> float:
        """인기도 점수 계산 (0.0 ~ 100.0)"""
        # 시간 가중치 (최근일수록 높은 점수)
        now = datetime.utcnow()
        days_since_last = (now - self.last_searched_at).days
        time_weight = max(0.1, 1.0 - (days_since_last / 30.0))  # 30일 기준
        
        # 검색 빈도 가중치
        search_weight = min(1.0, self.total_searches / 100.0)  # 100회 기준 정규화
        
        # 캐시 효율성 가중치
        cache_efficiency = (
            self.total_cache_hits / max(1, self.total_searches) 
            if self.total_searches > 0 else 0
        )
        
        # 종합 점수
        popularity_score = (
            time_weight * 0.4 +
            search_weight * 0.4 +
            cache_efficiency * 0.2
        ) * 100.0
        
        return round(popularity_score, 2)

    def __repr__(self):
        return f"<PopularSearchQuery(query='{self.query[:50]}...', searches={self.total_searches})>"