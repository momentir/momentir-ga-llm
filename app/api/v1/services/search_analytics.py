"""
검색 분석 서비스
PostgreSQL 기반 검색 히스토리 분석 및 성능 모니터링
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text, Integer
from sqlalchemy.orm import selectinload

from app.db_models.search_history import SearchHistory, SearchAnalytics, FrequentFailurePattern
from app.db_models.auth_models import User

logger = logging.getLogger(__name__)


class SearchAnalyticsService:
    """검색 분석 서비스 클래스"""
    
    def __init__(self):
        self.failure_rate_threshold = 0.7  # 70% 이상 실패율은 패턴으로 감지
        self.minimum_attempts = 3  # 최소 3번 시도 후 패턴 감지
    
    async def record_search(
        self,
        db_session: AsyncSession,
        user_id: int,
        query: str,
        sql_generated: Optional[str] = None,
        strategy_used: Optional[str] = None,
        success: bool = False,
        error_message: Optional[str] = None,
        result_count: Optional[int] = None,
        response_time: Optional[float] = None,
        sql_generation_time: Optional[float] = None,
        sql_execution_time: Optional[float] = None,
        metadata_info: Optional[Dict] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SearchHistory:
        """
        검색 기록을 데이터베이스에 저장
        백그라운드 작업으로 비동기 처리
        """
        try:
            # 쿼리 해시 생성 (중복 감지용)
            query_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()
            
            # 검색 기록 생성
            search_record = SearchHistory(
                user_id=user_id,
                query=query,
                query_hash=query_hash,
                sql_generated=sql_generated,
                strategy_used=strategy_used,
                success=success,
                error_message=error_message,
                result_count=result_count,
                response_time=response_time,
                sql_generation_time=sql_generation_time,
                sql_execution_time=sql_execution_time,
                metadata_info=metadata_info,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            db_session.add(search_record)
            await db_session.commit()
            
            # 실패한 검색의 경우 패턴 감지 수행
            if not success and error_message:
                await self._detect_failure_pattern(
                    db_session, query, error_message
                )
            
            logger.info(f"검색 기록 저장 완료: user_id={user_id}, success={success}")
            return search_record
            
        except Exception as e:
            logger.error(f"검색 기록 저장 실패: {str(e)}")
            await db_session.rollback()
            raise
    
    async def get_popular_queries(
        self,
        db_session: AsyncSession,
        limit: int = 10,
        days: int = 7,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        인기 검색어 TOP N 조회
        """
        try:
            # 기간 설정
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # 기본 쿼리 구성
            query = select(
                SearchHistory.query,
                func.count().label('search_count'),
                func.avg(SearchHistory.response_time).label('avg_response_time'),
                func.sum(func.cast(SearchHistory.success, Integer)).label('success_count')
            ).where(
                SearchHistory.created_at >= start_date
            ).group_by(SearchHistory.query)
            
            # 사용자별 필터링
            if user_id:
                query = query.where(SearchHistory.user_id == user_id)
            
            # 정렬 및 제한
            query = query.order_by(desc('search_count')).limit(limit)
            
            result = await db_session.execute(query)
            rows = result.fetchall()
            
            popular_queries = []
            for row in rows:
                popular_queries.append({
                    'query': row.query,
                    'search_count': row.search_count,
                    'avg_response_time': round(row.avg_response_time or 0, 3),
                    'success_rate': round((row.success_count or 0) / row.search_count, 2)
                })
            
            logger.info(f"인기 검색어 조회 완료: {len(popular_queries)}개")
            return popular_queries
            
        except Exception as e:
            logger.error(f"인기 검색어 조회 실패: {str(e)}")
            return []
    
    async def get_performance_stats(
        self,
        db_session: AsyncSession,
        days: int = 7,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        성능 통계 조회
        - 평균/최소/최대 응답 시간
        - 성공률
        - 전략별 성능
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # 기본 통계 쿼리
            base_query = select(SearchHistory).where(
                SearchHistory.created_at >= start_date
            )
            
            if user_id:
                base_query = base_query.where(SearchHistory.user_id == user_id)
            
            # 전체 통계
            stats_query = select(
                func.count().label('total_searches'),
                func.sum(func.cast(SearchHistory.success, Integer)).label('successful_searches'),
                func.avg(SearchHistory.response_time).label('avg_response_time'),
                func.min(SearchHistory.response_time).label('min_response_time'),
                func.max(SearchHistory.response_time).label('max_response_time'),
                func.avg(SearchHistory.sql_generation_time).label('avg_sql_generation_time'),
                func.avg(SearchHistory.sql_execution_time).label('avg_sql_execution_time')
            ).where(SearchHistory.created_at >= start_date)
            
            if user_id:
                stats_query = stats_query.where(SearchHistory.user_id == user_id)
            
            stats_result = await db_session.execute(stats_query)
            stats_row = stats_result.fetchone()
            
            # 전략별 성능 통계
            strategy_query = select(
                SearchHistory.strategy_used,
                func.count().label('count'),
                func.avg(SearchHistory.response_time).label('avg_response_time'),
                func.sum(func.cast(SearchHistory.success, Integer)).label('success_count')
            ).where(
                and_(
                    SearchHistory.created_at >= start_date,
                    SearchHistory.strategy_used.is_not(None)
                )
            ).group_by(SearchHistory.strategy_used)
            
            if user_id:
                strategy_query = strategy_query.where(SearchHistory.user_id == user_id)
            
            strategy_result = await db_session.execute(strategy_query)
            strategy_rows = strategy_result.fetchall()
            
            # 전략별 성능 데이터 구성
            strategy_performance = []
            for row in strategy_rows:
                strategy_performance.append({
                    'strategy': row.strategy_used,
                    'count': row.count,
                    'avg_response_time': round(row.avg_response_time or 0, 3),
                    'success_rate': round((row.success_count or 0) / row.count, 2)
                })
            
            # 결과 구성
            performance_stats = {
                'period_days': days,
                'total_searches': stats_row.total_searches or 0,
                'successful_searches': stats_row.successful_searches or 0,
                'success_rate': round((stats_row.successful_searches or 0) / max(stats_row.total_searches or 1, 1), 2),
                'avg_response_time': round(stats_row.avg_response_time or 0, 3),
                'min_response_time': round(stats_row.min_response_time or 0, 3),
                'max_response_time': round(stats_row.max_response_time or 0, 3),
                'avg_sql_generation_time': round(stats_row.avg_sql_generation_time or 0, 3),
                'avg_sql_execution_time': round(stats_row.avg_sql_execution_time or 0, 3),
                'strategy_performance': strategy_performance
            }
            
            logger.info(f"성능 통계 조회 완료: {performance_stats['total_searches']}건")
            return performance_stats
            
        except Exception as e:
            import traceback
            logger.error(f"성능 통계 조회 실패: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}
    
    async def get_failure_patterns(
        self,
        db_session: AsyncSession,
        limit: int = 10,
        min_failure_rate: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        실패율 높은 패턴 조회
        """
        try:
            query = select(FrequentFailurePattern).where(
                and_(
                    FrequentFailurePattern.is_active == True,
                    FrequentFailurePattern.failure_rate >= min_failure_rate
                )
            ).order_by(desc(FrequentFailurePattern.failure_rate)).limit(limit)
            
            result = await db_session.execute(query)
            patterns = result.scalars().all()
            
            failure_patterns = []
            for pattern in patterns:
                failure_patterns.append({
                    'pattern_description': pattern.pattern_description,
                    'example_query': pattern.example_query,
                    'failure_count': pattern.failure_count,
                    'total_attempts': pattern.total_attempts,
                    'failure_rate': round(pattern.failure_rate, 2),
                    'last_error_message': pattern.last_error_message,
                    'last_failure_at': pattern.last_failure_at.isoformat(),
                    'detected_at': pattern.detected_at.isoformat()
                })
            
            logger.info(f"실패 패턴 조회 완료: {len(failure_patterns)}개")
            return failure_patterns
            
        except Exception as e:
            logger.error(f"실패 패턴 조회 실패: {str(e)}")
            return []
    
    async def get_user_search_history(
        self,
        db_session: AsyncSession,
        user_id: int,
        limit: int = 50,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        특정 사용자의 검색 히스토리 조회
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = select(SearchHistory).where(
                and_(
                    SearchHistory.user_id == user_id,
                    SearchHistory.created_at >= start_date
                )
            ).order_by(desc(SearchHistory.created_at)).limit(limit)
            
            result = await db_session.execute(query)
            histories = result.scalars().all()
            
            search_history = []
            for history in histories:
                search_history.append({
                    'id': str(history.id),
                    'query': history.query,
                    'sql_generated': history.sql_generated,
                    'strategy_used': history.strategy_used,
                    'success': history.success,
                    'error_message': history.error_message,
                    'result_count': history.result_count,
                    'response_time': history.response_time,
                    'created_at': history.created_at.isoformat()
                })
            
            logger.info(f"사용자 검색 히스토리 조회 완료: user_id={user_id}, {len(search_history)}건")
            return search_history
            
        except Exception as e:
            logger.error(f"사용자 검색 히스토리 조회 실패: {str(e)}")
            return []
    
    async def _detect_failure_pattern(
        self,
        db_session: AsyncSession,
        query: str,
        error_message: str
    ):
        """
        실패 패턴 자동 감지 및 저장
        """
        try:
            # 패턴 해시 생성 (에러 메시지 기반)
            pattern_hash = hashlib.sha256(
                error_message.lower().strip().encode()
            ).hexdigest()[:64]
            
            # 기존 패턴 조회
            existing_pattern = await db_session.execute(
                select(FrequentFailurePattern).where(
                    FrequentFailurePattern.pattern_hash == pattern_hash
                )
            )
            pattern = existing_pattern.scalar_one_or_none()
            
            if pattern:
                # 기존 패턴 업데이트
                pattern.failure_count += 1
                pattern.total_attempts += 1
                pattern.failure_rate = pattern.failure_count / pattern.total_attempts
                pattern.last_error_message = error_message
                pattern.last_failure_at = datetime.now()
                pattern.updated_at = datetime.now()
            else:
                # 새 패턴 생성
                pattern = FrequentFailurePattern(
                    pattern_hash=pattern_hash,
                    pattern_description=f"Error pattern: {error_message[:100]}...",
                    example_query=query,
                    failure_count=1,
                    total_attempts=1,
                    failure_rate=1.0,
                    last_error_message=error_message,
                    last_failure_at=datetime.now()
                )
                db_session.add(pattern)
            
            await db_session.commit()
            
            # 패턴 임계치 확인
            if (pattern.failure_rate >= self.failure_rate_threshold and 
                pattern.total_attempts >= self.minimum_attempts):
                logger.warning(f"높은 실패율 패턴 감지: {pattern.pattern_description}")
            
        except Exception as e:
            logger.error(f"실패 패턴 감지 중 오류: {str(e)}")
            await db_session.rollback()
    
    async def generate_daily_analytics(
        self,
        db_session: AsyncSession,
        target_date: Optional[datetime] = None
    ) -> SearchAnalytics:
        """
        일별 분석 데이터 생성 (배치 작업용)
        """
        if not target_date:
            target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            start_date = target_date
            end_date = target_date + timedelta(days=1)
            
            # 일별 통계 계산
            stats_query = select(
                func.count().label('total_searches'),
                func.sum(func.cast(SearchHistory.success, Integer)).label('successful_searches'),
                func.avg(SearchHistory.response_time).label('avg_response_time'),
                func.min(SearchHistory.response_time).label('min_response_time'),
                func.max(SearchHistory.response_time).label('max_response_time')
            ).where(
                and_(
                    SearchHistory.created_at >= start_date,
                    SearchHistory.created_at < end_date
                )
            )
            
            stats_result = await db_session.execute(stats_query)
            stats_row = stats_result.fetchone()
            
            # 인기 쿼리 집계
            popular_queries_result = await self.get_popular_queries(
                db_session, limit=10, days=1
            )
            
            # 분석 데이터 저장
            analytics = SearchAnalytics(
                analytics_date=target_date,
                analytics_type='daily',
                total_searches=stats_row.total_searches or 0,
                successful_searches=stats_row.successful_searches or 0,
                failed_searches=(stats_row.total_searches or 0) - (stats_row.successful_searches or 0),
                avg_response_time=stats_row.avg_response_time,
                min_response_time=stats_row.min_response_time,
                max_response_time=stats_row.max_response_time,
                popular_queries=popular_queries_result
            )
            
            db_session.add(analytics)
            await db_session.commit()
            
            logger.info(f"일별 분석 데이터 생성 완료: {target_date.date()}")
            return analytics
            
        except Exception as e:
            logger.error(f"일별 분석 데이터 생성 실패: {str(e)}")
            await db_session.rollback()
            raise


# 싱글톤 인스턴스
search_analytics_service = SearchAnalyticsService()