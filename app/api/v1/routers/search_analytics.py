"""
검색 분석 API 라우터
FastAPI BackgroundTasks를 사용한 비동기 히스토리 저장
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.core.database import get_db
from app.api.v1.services.search_analytics import search_analytics_service
from app.models.search_models import (
    SearchHistoryCreate, SearchHistoryResponse,
    PopularQueryResponse, PerformanceStatsResponse,
    FailurePatternResponse, SearchHistoryListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/api/search-analytics", tags=["search-analytics"])


@router.post("/record", status_code=201)
async def record_search_history(
    request: SearchHistoryCreate,
    background_tasks: BackgroundTasks,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    검색 히스토리 기록 (백그라운드 작업)
    성능 영향을 최소화하기 위해 비동기로 처리
    """
    try:
        # 클라이언트 정보 추출
        client_ip = req.client.host if req.client else None
        user_agent = req.headers.get("user-agent")
        
        # 백그라운드 작업으로 히스토리 저장
        background_tasks.add_task(
            search_analytics_service.record_search,
            db,
            user_id=request.user_id,
            query=request.query,
            sql_generated=request.sql_generated,
            strategy_used=request.strategy_used,
            success=request.success,
            error_message=request.error_message,
            result_count=request.result_count,
            response_time=request.response_time,
            sql_generation_time=request.sql_generation_time,
            sql_execution_time=request.sql_execution_time,
            metadata_info=request.metadata_info,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        return {"message": "검색 히스토리 기록이 예약되었습니다.", "status": "queued"}
        
    except Exception as e:
        logger.error(f"검색 히스토리 기록 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="검색 히스토리 기록 중 오류가 발생했습니다."
        )


@router.get("/popular-queries", response_model=List[PopularQueryResponse])
async def get_popular_queries(
    limit: int = Query(default=10, le=50, description="조회할 인기 검색어 수"),
    days: int = Query(default=7, le=30, description="분석 기간 (일)"),
    user_id: Optional[int] = Query(None, description="특정 사용자 필터링"),
    db: AsyncSession = Depends(get_db)
):
    """
    인기 검색어 TOP N 조회
    - 최근 N일간의 검색 빈도 기준
    - 사용자별 필터링 가능
    """
    try:
        popular_queries = await search_analytics_service.get_popular_queries(
            db, limit=limit, days=days, user_id=user_id
        )
        
        return [PopularQueryResponse(**query) for query in popular_queries]
        
    except Exception as e:
        logger.error(f"인기 검색어 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="인기 검색어 조회 중 오류가 발생했습니다."
        )


@router.get("/performance-stats", response_model=PerformanceStatsResponse)
async def get_performance_stats(
    days: int = Query(default=7, le=30, description="분석 기간 (일)"),
    user_id: Optional[int] = Query(None, description="특정 사용자 필터링"),
    db: AsyncSession = Depends(get_db)
):
    """
    검색 성능 통계 조회
    - 평균/최소/최대 응답 시간
    - 성공률 및 전략별 성능
    """
    try:
        stats = await search_analytics_service.get_performance_stats(
            db, days=days, user_id=user_id
        )
        
        if not stats:
            return PerformanceStatsResponse(
                period_days=days,
                total_searches=0,
                successful_searches=0,
                success_rate=0.0,
                avg_response_time=0.0,
                min_response_time=0.0,
                max_response_time=0.0,
                avg_sql_generation_time=0.0,
                avg_sql_execution_time=0.0,
                strategy_performance=[]
            )
        
        return PerformanceStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"성능 통계 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="성능 통계 조회 중 오류가 발생했습니다."
        )


@router.get("/failure-patterns", response_model=List[FailurePatternResponse])
async def get_failure_patterns(
    limit: int = Query(default=10, le=50, description="조회할 실패 패턴 수"),
    min_failure_rate: float = Query(default=0.5, ge=0.0, le=1.0, description="최소 실패율"),
    db: AsyncSession = Depends(get_db)
):
    """
    실패율 높은 패턴 조회
    - 자주 실패하는 쿼리 패턴 분석
    - 개선 대상 식별
    """
    try:
        patterns = await search_analytics_service.get_failure_patterns(
            db, limit=limit, min_failure_rate=min_failure_rate
        )
        
        return [FailurePatternResponse(**pattern) for pattern in patterns]
        
    except Exception as e:
        logger.error(f"실패 패턴 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="실패 패턴 조회 중 오류가 발생했습니다."
        )


@router.get("/user/{user_id}/history", response_model=SearchHistoryListResponse)
async def get_user_search_history(
    user_id: int,
    limit: int = Query(default=50, le=200, description="조회할 히스토리 수"),
    days: int = Query(default=30, le=90, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 사용자의 검색 히스토리 조회
    - 최근 검색 내역 및 성능
    - 개인별 사용 패턴 분석
    """
    try:
        history = await search_analytics_service.get_user_search_history(
            db, user_id=user_id, limit=limit, days=days
        )
        
        return SearchHistoryListResponse(
            user_id=user_id,
            total_count=len(history),
            period_days=days,
            searches=history
        )
        
    except Exception as e:
        logger.error(f"사용자 검색 히스토리 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="사용자 검색 히스토리 조회 중 오류가 발생했습니다."
        )


@router.get("/dashboard")
async def get_analytics_dashboard(
    days: int = Query(default=7, le=30, description="분석 기간 (일)"),
    db: AsyncSession = Depends(get_db)
):
    """
    검색 분석 대시보드 데이터
    - 전체 성능 지표
    - 인기 검색어
    - 실패 패턴 요약
    """
    try:
        # 동시에 여러 분석 데이터 수집
        performance_stats = await search_analytics_service.get_performance_stats(
            db, days=days
        )
        
        popular_queries = await search_analytics_service.get_popular_queries(
            db, limit=5, days=days
        )
        
        failure_patterns = await search_analytics_service.get_failure_patterns(
            db, limit=5, min_failure_rate=0.7
        )
        
        dashboard_data = {
            "period_days": days,
            "performance_stats": performance_stats,
            "popular_queries": popular_queries,
            "failure_patterns": failure_patterns,
            "generated_at": datetime.now().isoformat()
        }
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="대시보드 데이터 조회 중 오류가 발생했습니다."
        )


@router.post("/generate-daily-analytics")
async def generate_daily_analytics(
    background_tasks: BackgroundTasks,
    target_date: Optional[str] = Query(None, description="분석 날짜 (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    """
    일별 분석 데이터 생성 (관리자용)
    배치 작업으로 사전 계산된 통계 생성
    """
    try:
        # 날짜 파싱
        parsed_date = None
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
                )
        
        # 백그라운드 작업으로 분석 데이터 생성
        background_tasks.add_task(
            search_analytics_service.generate_daily_analytics,
            db,
            parsed_date
        )
        
        return {
            "message": "일별 분석 데이터 생성이 예약되었습니다.",
            "target_date": target_date or datetime.now().date().isoformat(),
            "status": "queued"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"일별 분석 생성 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="일별 분석 생성 중 오류가 발생했습니다."
        )