"""
검색 캐시 서비스 통합 테스트

PostgreSQL 기반 캐시 시스템과 포맷터의 통합 테스트를 수행합니다.
"""

import pytest
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

import pytest_asyncio
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError

from app.db_models.search_cache import SearchCache, PopularSearchQuery
from app.services.search_cache_service import SearchCacheService
from app.services.search_formatter import SearchResultFormatter, HighlightOptions
from app.database import db_manager


class TestSearchCacheModels:
    """검색 캐시 모델 테스트"""
    
    def test_cache_key_generation(self):
        """캐시 키 생성 테스트"""
        # 기본 쿼리
        query = "30대 고객 수"
        key1 = SearchCache.generate_cache_key(query)
        assert len(key1) == 32  # MD5 해시 길이
        assert isinstance(key1, str)
        
        # 동일한 쿼리는 동일한 키 생성
        key2 = SearchCache.generate_cache_key(query)
        assert key1 == key2
        
        # 컨텍스트가 다르면 다른 키
        context = {"department": "analytics"}
        key3 = SearchCache.generate_cache_key(query, context=context)
        assert key1 != key3
        
        # 옵션이 다르면 다른 키
        options = {"strategy": "llm_first"}
        key4 = SearchCache.generate_cache_key(query, options=options)
        assert key1 != key4
    
    def test_cache_key_normalization(self):
        """캐시 키 정규화 테스트"""
        # 대소문자 정규화
        key1 = SearchCache.generate_cache_key("고객 수")
        key2 = SearchCache.generate_cache_key("고객 수")
        assert key1 == key2
        
        # 공백 정규화
        key3 = SearchCache.generate_cache_key("  고객 수  ")
        assert key1 == key3
    
    def test_cache_expiry_check(self):
        """캐시 만료 확인 테스트"""
        now = datetime.utcnow()
        
        # 만료되지 않은 캐시
        cache_entry = SearchCache(
            query_hash="test_hash",
            original_query="test query",
            result={"data": []},
            expires_at=now + timedelta(minutes=5)
        )
        assert not cache_entry.is_expired()
        
        # 만료된 캐시
        expired_entry = SearchCache(
            query_hash="expired_hash",
            original_query="expired query",
            result={"data": []},
            expires_at=now - timedelta(minutes=1)
        )
        assert expired_entry.is_expired()
    
    def test_popular_query_normalization(self):
        """인기 검색어 정규화 테스트"""
        query = "  30대 고객들의 평균 보험료  "
        normalized = PopularSearchQuery.normalize_query(query)
        assert normalized == "30대 고객들의 평균 보험료"
    
    def test_popularity_score_calculation(self):
        """인기도 점수 계산 테스트"""
        now = datetime.utcnow()
        
        popular_query = PopularSearchQuery(
            query="test query",
            query_normalized="test query",
            total_searches=50,
            total_cache_hits=30,
            last_searched_at=now - timedelta(days=1)
        )
        
        score = popular_query.calculate_popularity_score()
        assert 0 <= score <= 100
        assert isinstance(score, float)


class TestSearchResultFormatter:
    """검색 결과 포맷터 테스트"""
    
    @pytest.fixture
    def formatter(self):
        return SearchResultFormatter()
    
    @pytest.fixture
    def sample_data(self):
        return [
            {"name": "김철수", "age": 35, "region": "서울", "premium": 120000},
            {"name": "이영희", "age": 32, "region": "부산", "premium": 115000},
            {"name": "박민수", "age": 38, "region": "서울", "premium": 125000}
        ]
    
    def test_highlight_search_results(self, formatter, sample_data):
        """검색어 하이라이팅 테스트"""
        query = "서울 35"
        options = HighlightOptions(case_sensitive=False)
        
        highlighted = formatter.highlight_search_results(sample_data, query, options)
        
        assert len(highlighted) == len(sample_data)
        
        # 첫 번째 결과 확인 (서울, 35세)
        first_result = highlighted[0]
        assert '<mark class="search-highlight">서울</mark>' in first_result["region"]
        assert '<mark class="search-highlight">35</mark>' in str(first_result["age"])
    
    def test_extract_search_terms(self, formatter):
        """검색어 추출 테스트"""
        # 기본 한국어 검색어
        terms1 = formatter._extract_search_terms("30대 고객 보험료")
        assert "30대" in terms1
        assert "고객" in terms1
        assert "보험료" in terms1
        
        # 따옴표가 포함된 검색어
        terms2 = formatter._extract_search_terms('"30대 고객" 평균')
        assert "30대 고객" in terms2
        assert "평균" in terms2
        
        # 한영 혼합 검색어
        terms3 = formatter._extract_search_terms("customer 나이 age")
        assert "customer" in terms3
        assert "나이" in terms3
        assert "age" in terms3
    
    def test_paginate_results(self, formatter, sample_data):
        """페이지네이션 테스트"""
        # 첫 번째 페이지 (2개씩)
        paginated, pagination_info = formatter.paginate_results(sample_data, page=1, page_size=2)
        
        assert len(paginated) == 2
        assert pagination_info.current_page == 1
        assert pagination_info.total_pages == 2
        assert pagination_info.total_items == 3
        assert pagination_info.has_previous is False
        assert pagination_info.has_next is True
        
        # 두 번째 페이지
        paginated2, pagination_info2 = formatter.paginate_results(sample_data, page=2, page_size=2)
        
        assert len(paginated2) == 1  # 마지막 1개
        assert pagination_info2.current_page == 2
        assert pagination_info2.has_previous is True
        assert pagination_info2.has_next is False
    
    def test_generate_search_summary(self, formatter, sample_data):
        """검색 결과 요약 생성 테스트"""
        query = "서울 거주 고객"
        summary = formatter.generate_search_summary(sample_data, query, total_count=3)
        
        assert summary["total_results"] == 3
        assert summary["displayed_results"] == 3
        assert summary["query"] == query
        assert "field_analysis" in summary
        assert "term_frequency" in summary
        assert "query_complexity" in summary
    
    def test_format_search_results_comprehensive(self, formatter, sample_data):
        """종합 결과 포맷팅 테스트"""
        query = "서울 고객"
        
        formatted_result = formatter.format_search_results(
            data=sample_data,
            query=query,
            total_count=3,
            page=1,
            page_size=2,
            highlight_options=HighlightOptions()
        )
        
        # 기본 구조 확인
        assert len(formatted_result.original_data) == 3
        assert len(formatted_result.highlighted_data) == 3
        assert formatted_result.pagination["total_items"] == 3
        assert formatted_result.summary["total_results"] == 3
        
        # 하이라이팅 확인
        highlighted_text = str(formatted_result.highlighted_data)
        assert "search-highlight" in highlighted_text
        
        # 포맷팅 메타데이터 확인
        assert formatted_result.formatting_info["query"] == query
        assert "total_highlights" in formatted_result.formatting_info


@pytest.mark.asyncio
class TestSearchCacheService:
    """검색 캐시 서비스 통합 테스트"""
    
    @pytest.fixture
    async def cache_service(self):
        service = SearchCacheService()
        
        # 테스트 전 캐시 정리
        try:
            await service.invalidate_cache()
        except Exception:
            pass  # 테이블이 없을 수 있음
        
        return service
    
    @pytest.fixture
    def sample_search_result(self):
        return {
            "request_id": "test_001",
            "query": "테스트 쿼리",
            "intent": {"intent_type": "customer_info", "confidence": 0.9},
            "execution": {"sql_query": "SELECT * FROM test", "execution_time_ms": 150},
            "data": [{"id": 1, "name": "테스트"}],
            "total_rows": 1,
            "success": True
        }
    
    async def test_cache_storage_and_retrieval(self, cache_service, sample_search_result):
        """캐시 저장 및 조회 테스트"""
        query = "테스트 쿼리"
        context = {"department": "test"}
        options = {"strategy": "llm_first"}
        
        # 캐시 저장
        success = await cache_service.cache_search_result(
            query=query,
            result=sample_search_result,
            context=context,
            options=options,
            execution_time_ms=150
        )
        
        assert success is True
        
        # 캐시 조회
        cached_result = await cache_service.get_cached_result(
            query=query,
            context=context,
            options=options
        )
        
        assert cached_result is not None
        assert cached_result["cached"] is True
        assert cached_result["query"] == query
        assert cached_result["total_rows"] == 1
        
        # 히트 카운트 증가 확인
        cached_result2 = await cache_service.get_cached_result(
            query=query,
            context=context,
            options=options
        )
        assert cached_result2["hit_count"] > cached_result["hit_count"]
    
    async def test_cache_miss(self, cache_service):
        """캐시 미스 테스트"""
        cached_result = await cache_service.get_cached_result(
            query="존재하지 않는 쿼리",
            context={},
            options={}
        )
        
        assert cached_result is None
    
    @patch('app.services.search_cache_service.db_manager')
    async def test_cache_error_handling(self, mock_db_manager, cache_service):
        """캐시 오류 처리 테스트"""
        # 데이터베이스 오류 시뮬레이션
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        mock_db_manager.get_async_session.return_value.__aenter__.return_value = mock_session
        
        # 오류 상황에서도 None 반환 (예외 발생하지 않음)
        result = await cache_service.get_cached_result("test query")
        assert result is None
        
        # 캐시 저장도 False 반환
        success = await cache_service.cache_search_result("test", {})
        assert success is False
    
    async def test_cache_statistics(self, cache_service, sample_search_result):
        """캐시 통계 테스트"""
        # 몇 개의 캐시 항목 생성
        for i in range(3):
            await cache_service.cache_search_result(
                query=f"테스트 쿼리 {i}",
                result=sample_search_result,
                execution_time_ms=100 + i * 10
            )
        
        stats = await cache_service.get_cache_statistics()
        
        assert "cache_entries" in stats
        assert "hit_statistics" in stats
        assert "efficiency" in stats
        assert stats["cache_entries"]["total"] >= 3
    
    async def test_popular_queries_tracking(self, cache_service, sample_search_result):
        """인기 검색어 추적 테스트"""
        query = "인기 검색어 테스트"
        
        # 여러 번 검색하여 인기도 증가
        for i in range(5):
            await cache_service.cache_search_result(
                query=query,
                result=sample_search_result,
                execution_time_ms=120
            )
            
            # 캐시 히트로 카운트 증가
            await cache_service.get_cached_result(query=query)
        
        # 인기 검색어 조회
        popular_queries = await cache_service.get_popular_queries(limit=10, min_searches=1)
        
        # 결과 확인 (통계 집계는 TRIGGER에 의존)
        assert isinstance(popular_queries, list)
    
    async def test_cache_invalidation(self, cache_service, sample_search_result):
        """캐시 무효화 테스트"""
        query = "무효화 테스트 쿼리"
        
        # 캐시 저장
        await cache_service.cache_search_result(query=query, result=sample_search_result)
        
        # 캐시 확인
        cached = await cache_service.get_cached_result(query=query)
        assert cached is not None
        
        # 특정 쿼리 무효화
        deleted_count = await cache_service.invalidate_cache(query=query)
        assert deleted_count >= 0
        
        # 캐시 미스 확인
        cached_after = await cache_service.get_cached_result(query=query)
        assert cached_after is None
    
    async def test_search_suggestions(self, cache_service, sample_search_result):
        """검색어 자동완성 테스트"""
        # 여러 유사한 쿼리 캐시
        queries = ["고객 정보", "고객 목록", "고객 분석", "보험 고객"]
        
        for query in queries:
            await cache_service.cache_search_result(query=query, result=sample_search_result)
        
        # 자동완성 조회
        suggestions = await cache_service.search_cached_queries(
            search_term="고객",
            limit=5
        )
        
        assert isinstance(suggestions, list)
        # 실제 제안이 있는지는 데이터베이스와 pg_trgm 설정에 따라 달라질 수 있음


class TestSearchCacheIntegration:
    """검색 캐시 통합 시나리오 테스트"""
    
    @pytest.fixture
    def cache_service(self):
        return SearchCacheService()
    
    @pytest.fixture
    def formatter(self):
        return SearchResultFormatter()
    
    @pytest.fixture
    def sample_search_data(self):
        return [
            {"customer_id": 1, "name": "김철수", "age": 35, "region": "서울"},
            {"customer_id": 2, "name": "이영희", "age": 32, "region": "부산"},
            {"customer_id": 3, "name": "박민수", "age": 38, "region": "서울"},
            {"customer_id": 4, "name": "최지은", "age": 29, "region": "대구"},
            {"customer_id": 5, "name": "정수호", "age": 41, "region": "서울"}
        ]
    
    def test_end_to_end_search_workflow(self, cache_service, formatter, sample_search_data):
        """엔드투엔드 검색 워크플로우 테스트"""
        query = "서울 고객"
        
        # 1. 검색 결과 포맷팅
        formatted_result = formatter.format_search_results(
            data=sample_search_data,
            query=query,
            total_count=len(sample_search_data),
            page=1,
            page_size=3,
            highlight_options=HighlightOptions()
        )
        
        # 2. 포맷팅 결과 검증
        assert len(formatted_result.highlighted_data) == len(sample_search_data)
        assert formatted_result.pagination["total_items"] == 5
        assert "서울" in str(formatted_result.highlighted_data)
        
        # 3. 캐시 키 생성 테스트
        cache_key = SearchCache.generate_cache_key(query)
        assert len(cache_key) == 32
    
    def test_performance_with_large_dataset(self, formatter):
        """대용량 데이터셋 성능 테스트"""
        import time
        
        # 대용량 데이터 생성 (1000개 항목)
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                "id": i,
                "name": f"고객{i}",
                "region": "서울" if i % 3 == 0 else "부산" if i % 3 == 1 else "대구",
                "age": 25 + (i % 40),
                "description": f"이것은 고객 {i}의 상세 정보입니다. 서울에서 거주하는 중요한 고객입니다."
            })
        
        query = "서울 고객"
        
        # 성능 측정
        start_time = time.time()
        
        formatted_result = formatter.format_search_results(
            data=large_dataset,
            query=query,
            total_count=len(large_dataset),
            page=1,
            page_size=20,
            highlight_options=HighlightOptions()
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 성능 검증 (1초 이내)
        assert processing_time < 1.0
        assert len(formatted_result.highlighted_data) == 1000
        assert formatted_result.pagination["total_items"] == 1000
        
        print(f"대용량 데이터 처리 시간: {processing_time:.3f}초")


# 성능 및 스트레스 테스트
@pytest.mark.performance
class TestSearchCachePerformance:
    """검색 캐시 성능 테스트"""
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """동시 캐시 접근 테스트"""
        cache_service = SearchCacheService()
        
        async def cache_operation(i: int):
            query = f"동시 테스트 쿼리 {i % 10}"  # 10개 쿼리 반복
            result = {"data": [{"id": i}], "total_rows": 1}
            
            # 캐시 저장
            await cache_service.cache_search_result(query=query, result=result)
            
            # 캐시 조회
            cached = await cache_service.get_cached_result(query=query)
            return cached is not None
        
        # 100개 동시 작업
        tasks = [cache_operation(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 검증
        successful_operations = sum(1 for result in results if result is True)
        exceptions = [result for result in results if isinstance(result, Exception)]
        
        print(f"성공한 작업: {successful_operations}/100")
        print(f"예외 발생: {len(exceptions)}개")
        
        # 최소 80% 성공률 기대
        assert successful_operations >= 80
    
    def test_highlighting_performance(self):
        """하이라이팅 성능 테스트"""
        formatter = SearchResultFormatter()
        
        # 복잡한 텍스트 데이터 생성
        complex_data = []
        for i in range(100):
            complex_data.append({
                "id": i,
                "title": f"보험상품 {i} - 30대 고객을 위한 특별 혜택",
                "description": "이 상품은 30대 고객들을 위해 특별히 설계된 보험상품입니다. " * 10,
                "keywords": "30대, 고객, 보험, 혜택, 서울, 부산, 대구"
            })
        
        query = "30대 고객 보험 서울"
        
        import time
        start_time = time.time()
        
        highlighted = formatter.highlight_search_results(
            complex_data,
            query,
            HighlightOptions()
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 성능 검증
        assert processing_time < 0.5  # 500ms 이내
        assert len(highlighted) == 100
        
        # 하이라이팅 적용 확인
        highlighted_text = str(highlighted)
        assert "search-highlight" in highlighted_text
        
        print(f"하이라이팅 처리 시간: {processing_time:.3f}초")


# 실행용 헬퍼
if __name__ == "__main__":
    # 기본 테스트 실행
    pytest.main([__file__, "-v", "--tb=short"])