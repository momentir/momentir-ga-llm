"""
검색 분석 관련 Pydantic 모델
API 요청/응답용 데이터 구조 정의
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class SearchHistoryCreate(BaseModel):
    """검색 히스토리 생성 요청"""
    user_id: int = Field(..., description="검색을 수행한 사용자 ID")
    query: str = Field(..., min_length=1, max_length=2000, description="검색 쿼리")
    sql_generated: Optional[str] = Field(None, description="생성된 SQL 쿼리")
    strategy_used: Optional[str] = Field(None, description="사용된 검색 전략")
    success: bool = Field(False, description="쿼리 실행 성공 여부")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    result_count: Optional[int] = Field(None, ge=0, description="결과 개수")
    response_time: Optional[float] = Field(None, ge=0, description="총 응답 시간 (초)")
    sql_generation_time: Optional[float] = Field(None, ge=0, description="SQL 생성 시간 (초)")
    sql_execution_time: Optional[float] = Field(None, ge=0, description="SQL 실행 시간 (초)")
    metadata_info: Optional[Dict[str, Any]] = Field(None, description="메타데이터")
    
    @validator('query')
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('검색 쿼리는 비어있을 수 없습니다.')
        return v.strip()


class SearchHistoryResponse(BaseModel):
    """검색 히스토리 응답"""
    id: str = Field(..., description="히스토리 ID")
    user_id: int = Field(..., description="사용자 ID")
    query: str = Field(..., description="검색 쿼리")
    sql_generated: Optional[str] = Field(None, description="생성된 SQL")
    strategy_used: Optional[str] = Field(None, description="사용된 전략")
    success: bool = Field(..., description="성공 여부")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    result_count: Optional[int] = Field(None, description="결과 개수")
    response_time: Optional[float] = Field(None, description="응답 시간")
    created_at: str = Field(..., description="생성 시각 (ISO 형식)")


class PopularQueryResponse(BaseModel):
    """인기 검색어 응답"""
    query: str = Field(..., description="검색 쿼리")
    search_count: int = Field(..., ge=0, description="검색 횟수")
    avg_response_time: float = Field(..., ge=0, description="평균 응답 시간")
    success_rate: float = Field(..., ge=0, le=1, description="성공률 (0-1)")


class StrategyPerformance(BaseModel):
    """전략별 성능"""
    strategy: str = Field(..., description="검색 전략명")
    count: int = Field(..., ge=0, description="사용 횟수")
    avg_response_time: float = Field(..., ge=0, description="평균 응답 시간")
    success_rate: float = Field(..., ge=0, le=1, description="성공률")


class PerformanceStatsResponse(BaseModel):
    """성능 통계 응답"""
    period_days: int = Field(..., description="분석 기간 (일)")
    total_searches: int = Field(..., ge=0, description="총 검색 횟수")
    successful_searches: int = Field(..., ge=0, description="성공한 검색 횟수")
    success_rate: float = Field(..., ge=0, le=1, description="전체 성공률")
    avg_response_time: float = Field(..., ge=0, description="평균 응답 시간")
    min_response_time: float = Field(..., ge=0, description="최소 응답 시간")
    max_response_time: float = Field(..., ge=0, description="최대 응답 시간")
    avg_sql_generation_time: float = Field(..., ge=0, description="평균 SQL 생성 시간")
    avg_sql_execution_time: float = Field(..., ge=0, description="평균 SQL 실행 시간")
    strategy_performance: List[StrategyPerformance] = Field(
        default_factory=list, 
        description="전략별 성능"
    )


class FailurePatternResponse(BaseModel):
    """실패 패턴 응답"""
    pattern_description: str = Field(..., description="패턴 설명")
    example_query: str = Field(..., description="예시 쿼리")
    failure_count: int = Field(..., ge=0, description="실패 횟수")
    total_attempts: int = Field(..., ge=1, description="총 시도 횟수")
    failure_rate: float = Field(..., ge=0, le=1, description="실패율")
    last_error_message: Optional[str] = Field(None, description="마지막 오류 메시지")
    last_failure_at: str = Field(..., description="마지막 실패 시각")
    detected_at: str = Field(..., description="패턴 감지 시각")


class SearchHistoryListResponse(BaseModel):
    """검색 히스토리 목록 응답"""
    user_id: int = Field(..., description="사용자 ID")
    total_count: int = Field(..., ge=0, description="총 히스토리 수")
    period_days: int = Field(..., description="조회 기간 (일)")
    searches: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="검색 히스토리 목록"
    )


class DashboardResponse(BaseModel):
    """대시보드 응답"""
    period_days: int = Field(..., description="분석 기간")
    performance_stats: Dict[str, Any] = Field(..., description="성능 통계")
    popular_queries: List[Dict[str, Any]] = Field(..., description="인기 검색어")
    failure_patterns: List[Dict[str, Any]] = Field(..., description="실패 패턴")
    generated_at: str = Field(..., description="생성 시각")


class AnalyticsJobResponse(BaseModel):
    """분석 작업 응답"""
    message: str = Field(..., description="작업 메시지")
    target_date: Optional[str] = Field(None, description="대상 날짜")
    status: str = Field(..., description="작업 상태")


# CloudWatch 메트릭용 모델
class CloudWatchMetric(BaseModel):
    """CloudWatch 커스텀 메트릭"""
    metric_name: str = Field(..., description="메트릭 명")
    value: float = Field(..., description="메트릭 값")
    unit: str = Field(default="Count", description="메트릭 단위")
    dimensions: Optional[Dict[str, str]] = Field(None, description="메트릭 차원")
    timestamp: Optional[datetime] = Field(None, description="메트릭 시각")


class SearchPerformanceAlert(BaseModel):
    """성능 알림"""
    alert_type: str = Field(..., description="알림 유형")
    severity: str = Field(..., description="심각도 (low/medium/high)")
    message: str = Field(..., description="알림 메시지")
    metric_value: float = Field(..., description="메트릭 값")
    threshold: float = Field(..., description="임계값")
    occurred_at: datetime = Field(..., description="발생 시각")