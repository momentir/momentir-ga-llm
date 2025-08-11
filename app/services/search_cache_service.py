"""
PostgreSQL 기반 검색 캐시 서비스

MD5 해시 기반 쿼리 키 생성, UPSERT 캐시 저장/업데이트,
인기 검색어 통계 자동 집계를 제공하는 캐시 서비스입니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import json

from sqlalchemy import select, insert, update, delete, func, text, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import db_manager
from app.db_models.search_cache import SearchCache, PopularSearchQuery

logger = logging.getLogger(__name__)


class SearchCacheService:
    """PostgreSQL 기반 검색 캐시 서비스"""
    
    def __init__(self):
        """캐시 서비스 초기화"""
        self.default_ttl_minutes = 5
        self.max_cache_size = 10000  # 최대 캐시 항목 수
        self.cleanup_batch_size = 1000  # 정리 배치 크기
        logger.info("✅ SearchCacheService 초기화 완료")
    
    async def get_cached_result(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        캐시된 검색 결과를 조회합니다.
        
        Args:
            query: 검색 쿼리
            context: 검색 컨텍스트
            options: 검색 옵션
            
        Returns:
            캐시된 결과 또는 None
        """
        try:
            cache_key = SearchCache.generate_cache_key(query, context, options)
            logger.debug(f"캐시 조회: key={cache_key}, query='{query[:50]}...'")
            
            async for session in db_manager.get_session():
                # 캐시 조회 및 만료 확인
                stmt = select(SearchCache).where(
                    SearchCache.query_hash == cache_key,
                    SearchCache.expires_at > datetime.utcnow()
                )
                
                result = await session.execute(stmt)
                cache_entry = result.scalar_one_or_none()
                
                if cache_entry:
                    # 히트 카운트 증가 및 마지막 접근 시간 업데이트
                    await self._update_cache_hit(session, cache_key)
                    
                    logger.info(f"✅ 캐시 히트: key={cache_key}, hits={cache_entry.hit_count + 1}")
                    
                    # 캐시 응답 형태로 변환
                    cached_result = cache_entry.to_cache_response()
                    return cached_result
                
                else:
                    logger.debug(f"❌ 캐시 미스: key={cache_key}")
                    return None
                    
        except Exception as e:
            logger.error(f"캐시 조회 실패: {e}")
            return None
    
    async def cache_search_result(
        self,
        query: str,
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        execution_time_ms: int = 0,
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """
        검색 결과를 캐시에 저장합니다.
        
        Args:
            query: 검색 쿼리
            result: 검색 결과
            context: 검색 컨텍스트
            options: 검색 옵션
            execution_time_ms: 실행 시간 (밀리초)
            ttl_minutes: 캐시 TTL (분)
            
        Returns:
            저장 성공 여부
        """
        try:
            cache_key = SearchCache.generate_cache_key(query, context, options)
            ttl = ttl_minutes or self.default_ttl_minutes
            
            logger.debug(f"캐시 저장: key={cache_key}, query='{query[:50]}...', TTL={ttl}분")
            
            async for session in db_manager.get_session():
                # UPSERT 구현 (PostgreSQL ON CONFLICT 사용)
                now = datetime.utcnow()
                expires_at = now + timedelta(minutes=ttl)
                
                # 결과에서 행 수 추출
                total_rows = 0
                if isinstance(result, dict):
                    total_rows = result.get('total_rows', 0) or len(result.get('data', []))
                
                # UPSERT 쿼리
                stmt = pg_insert(SearchCache).values(
                    query_hash=cache_key,
                    original_query=query,
                    query_context=context,
                    result=result,
                    result_metadata={
                        "cached_at": now.isoformat(),
                        "ttl_minutes": ttl,
                        "execution_time_ms": execution_time_ms
                    },
                    created_at=now,
                    expires_at=expires_at,
                    last_accessed=now,
                    hit_count=1,
                    total_rows=total_rows,
                    execution_time_ms=execution_time_ms
                )
                
                # ON CONFLICT 시 업데이트
                stmt = stmt.on_conflict_do_update(
                    index_elements=['query_hash'],
                    set_={
                        'result': stmt.excluded.result,
                        'result_metadata': stmt.excluded.result_metadata,
                        'expires_at': stmt.excluded.expires_at,
                        'last_accessed': stmt.excluded.last_accessed,
                        'hit_count': SearchCache.hit_count + 1,  # 기존 값에 1 더하기
                        'total_rows': stmt.excluded.total_rows,
                        'execution_time_ms': stmt.excluded.execution_time_ms
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
                
                logger.info(f"✅ 캐시 저장 성공: key={cache_key}")
                return True
                
        except Exception as e:
            logger.error(f"캐시 저장 실패: {e}")
            return False
    
    async def invalidate_cache(
        self,
        query: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> int:
        """
        캐시를 무효화합니다.
        
        Args:
            query: 특정 쿼리 (정확 매치)
            pattern: 쿼리 패턴 (LIKE 매치)
            
        Returns:
            삭제된 항목 수
        """
        try:
            async for session in db_manager.get_session():
                if query:
                    # 특정 쿼리 삭제
                    cache_key = SearchCache.generate_cache_key(query)
                    stmt = delete(SearchCache).where(SearchCache.query_hash == cache_key)
                elif pattern:
                    # 패턴 매치 삭제
                    stmt = delete(SearchCache).where(SearchCache.original_query.like(f"%{pattern}%"))
                else:
                    # 모든 캐시 삭제
                    stmt = delete(SearchCache)
                
                result = await session.execute(stmt)
                deleted_count = result.rowcount
                await session.commit()
                
                logger.info(f"✅ 캐시 무효화: {deleted_count}개 항목 삭제")
                return deleted_count
                
        except Exception as e:
            logger.error(f"캐시 무효화 실패: {e}")
            return 0
    
    async def cleanup_expired_cache(self) -> int:
        """
        만료된 캐시를 정리합니다.
        
        Returns:
            삭제된 항목 수
        """
        try:
            async for session in db_manager.get_session():
                # PostgreSQL 함수 호출
                await session.execute(text("SELECT cleanup_expired_cache()"))
                
                # 삭제된 개수 확인
                count_stmt = select(func.count()).where(
                    SearchCache.expires_at < datetime.utcnow()
                )
                result = await session.execute(count_stmt)
                expired_count = result.scalar()
                
                await session.commit()
                
                logger.info(f"✅ 만료된 캐시 정리 완료: {expired_count}개 확인됨")
                return expired_count
                
        except Exception as e:
            logger.error(f"캐시 정리 실패: {e}")
            return 0
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """
        캐시 통계를 조회합니다.
        
        Returns:
            캐시 통계 정보
        """
        try:
            async for session in db_manager.get_session():
                now = datetime.utcnow()
                
                # 기본 통계
                total_stmt = select(func.count()).select_from(SearchCache)
                active_stmt = select(func.count()).where(SearchCache.expires_at > now)
                expired_stmt = select(func.count()).where(SearchCache.expires_at <= now)
                
                total_result = await session.execute(total_stmt)
                active_result = await session.execute(active_stmt)
                expired_result = await session.execute(expired_stmt)
                
                total_entries = total_result.scalar()
                active_entries = active_result.scalar()
                expired_entries = expired_result.scalar()
                
                # 히트율 통계
                hit_stats_stmt = select(
                    func.avg(SearchCache.hit_count).label('avg_hits'),
                    func.max(SearchCache.hit_count).label('max_hits'),
                    func.sum(SearchCache.hit_count).label('total_hits')
                ).where(SearchCache.expires_at > now)
                
                hit_result = await session.execute(hit_stats_stmt)
                hit_stats = hit_result.first()
                
                # 최근 24시간 통계
                yesterday = now - timedelta(days=1)
                recent_stmt = select(func.count()).where(
                    SearchCache.created_at > yesterday
                )
                recent_result = await session.execute(recent_stmt)
                recent_entries = recent_result.scalar()
                
                statistics = {
                    "cache_entries": {
                        "total": total_entries,
                        "active": active_entries,
                        "expired": expired_entries,
                        "recent_24h": recent_entries
                    },
                    "hit_statistics": {
                        "total_hits": int(hit_stats.total_hits or 0),
                        "average_hits": float(hit_stats.avg_hits or 0),
                        "max_hits": int(hit_stats.max_hits or 0)
                    },
                    "efficiency": {
                        "hit_rate": (
                            hit_stats.total_hits / max(1, active_entries)
                            if hit_stats.total_hits and active_entries else 0
                        ),
                        "cache_utilization": active_entries / max(1, self.max_cache_size)
                    },
                    "timestamp": now.isoformat()
                }
                
                return statistics
                
        except Exception as e:
            logger.error(f"캐시 통계 조회 실패: {e}")
            return {"error": str(e)}
    
    async def get_popular_queries(
        self,
        limit: int = 20,
        min_searches: int = 2,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        인기 검색어를 조회합니다.
        
        Args:
            limit: 반환할 항목 수
            min_searches: 최소 검색 수
            days: 분석 기간 (일)
            
        Returns:
            인기 검색어 목록
        """
        try:
            async for session in db_manager.get_session():
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                stmt = (
                    select(PopularSearchQuery)
                    .where(
                        PopularSearchQuery.total_searches >= min_searches,
                        PopularSearchQuery.last_searched_at > cutoff_date
                    )
                    .order_by(PopularSearchQuery.total_searches.desc())
                    .limit(limit)
                )
                
                result = await session.execute(stmt)
                popular_queries = result.scalars().all()
                
                popular_list = []
                for query_stats in popular_queries:
                    popular_list.append({
                        "query": query_stats.query,
                        "total_searches": query_stats.total_searches,
                        "total_cache_hits": query_stats.total_cache_hits,
                        "cache_hit_rate": (
                            query_stats.total_cache_hits / max(1, query_stats.total_searches)
                        ),
                        "avg_execution_time_ms": query_stats.avg_execution_time_ms,
                        "popularity_score": query_stats.calculate_popularity_score(),
                        "first_searched": query_stats.first_searched_at.isoformat(),
                        "last_searched": query_stats.last_searched_at.isoformat()
                    })
                
                logger.info(f"✅ 인기 검색어 조회: {len(popular_list)}개")
                return popular_list
                
        except Exception as e:
            logger.error(f"인기 검색어 조회 실패: {e}")
            return []
    
    async def search_cached_queries(
        self,
        search_term: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        캐시된 쿼리를 검색합니다 (자동완성용).
        
        Args:
            search_term: 검색할 용어
            limit: 반환할 항목 수
            
        Returns:
            매치되는 쿼리 목록
        """
        try:
            async for session in db_manager.get_session():
                now = datetime.utcnow()
                
                # 유사한 쿼리 검색 (pg_trgm 활용)
                stmt = (
                    select(SearchCache.original_query, SearchCache.hit_count)
                    .where(
                        SearchCache.expires_at > now,
                        or_(
                            SearchCache.original_query.ilike(f"%{search_term}%"),
                            func.similarity(SearchCache.original_query, search_term) > 0.3
                        )
                    )
                    .order_by(SearchCache.hit_count.desc())
                    .limit(limit)
                )
                
                result = await session.execute(stmt)
                matches = result.all()
                
                suggestions = []
                for query, hit_count in matches:
                    suggestions.append({
                        "query": query,
                        "hit_count": hit_count,
                        "similarity": self._calculate_similarity(search_term, query)
                    })
                
                # 유사도 순으로 재정렬
                suggestions.sort(key=lambda x: (-x['similarity'], -x['hit_count']))
                
                logger.debug(f"쿼리 검색: '{search_term}' → {len(suggestions)}개 결과")
                return suggestions
                
        except Exception as e:
            logger.error(f"캐시된 쿼리 검색 실패: {e}")
            return []
    
    async def _update_cache_hit(self, session, cache_key: str):
        """캐시 히트 카운트를 업데이트합니다."""
        try:
            stmt = (
                update(SearchCache)
                .where(SearchCache.query_hash == cache_key)
                .values(
                    hit_count=SearchCache.hit_count + 1,
                    last_accessed=datetime.utcnow()
                )
            )
            await session.execute(stmt)
            await session.commit()
            
        except Exception as e:
            logger.warning(f"캐시 히트 업데이트 실패: {e}")
    
    def _calculate_similarity(self, term1: str, term2: str) -> float:
        """두 문자열의 유사도를 계산합니다 (간단한 구현)."""
        term1_lower = term1.lower()
        term2_lower = term2.lower()
        
        if term1_lower == term2_lower:
            return 1.0
        
        if term1_lower in term2_lower or term2_lower in term1_lower:
            return 0.8
        
        # 단어 단위 비교
        words1 = set(term1_lower.split())
        words2 = set(term2_lower.split())
        
        if words1 and words2:
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            return intersection / union if union > 0 else 0.0
        
        return 0.0


# 싱글톤 인스턴스
search_cache_service = SearchCacheService()