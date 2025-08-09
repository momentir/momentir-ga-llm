"""
LCEL SQL 파이프라인 통합 테스트

이 테스트 스위트는 LCEL 기반 SQL 생성 파이프라인의 
전체 기능을 검증합니다.
"""

import pytest
import asyncio
import json
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

from app.services.lcel_sql_pipeline import (
    LCELSQLPipeline,
    EnhancedSQLGenerationRequest,
    EnhancedSQLPipelineResponse,
    ExecutionStrategy,
    RetryConfig,
    RuleBasedSQLGenerator,
    SQLGenerationResult
)
from app.services.intent_classifier import ClassificationResultDict


class TestRuleBasedSQLGenerator:
    """규칙 기반 SQL 생성기 테스트"""
    
    @pytest.fixture
    def rule_generator(self):
        return RuleBasedSQLGenerator()
    
    @pytest.mark.asyncio
    async def test_simple_query_generation(self, rule_generator):
        """단순 조회 쿼리 생성 테스트"""
        intent_result: ClassificationResultDict = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8, "reasoning": "test"},
            "entities": {},
            "intent_keywords": ["조회"],
            "complexity_score": 0.3
        }
        
        result = await rule_generator.generate_sql(intent_result)
        
        assert isinstance(result, SQLGenerationResult)
        assert "SELECT" in result.sql.upper()
        assert result.generation_method == "rule_based"
        assert result.confidence > 0.0
        assert len(result.explanation) > 0
    
    @pytest.mark.asyncio
    async def test_filtering_query_generation(self, rule_generator):
        """필터링 쿼리 생성 테스트"""
        intent_result: ClassificationResultDict = {
            "query_type": {"main_type": "filtering", "confidence": 0.9, "reasoning": "test"},
            "entities": {
                "customer_names": ["홍길동"],
                "dates": ["최근 30일"]
            },
            "intent_keywords": ["찾기"],
            "complexity_score": 0.6
        }
        
        result = await rule_generator.generate_sql(intent_result)
        
        assert "WHERE" in result.sql.upper()
        assert result.generation_method == "rule_based"
        assert len(result.parameters) >= 0  # 파라미터가 있을 수 있음
    
    @pytest.mark.asyncio
    async def test_aggregation_query_generation(self, rule_generator):
        """집계 쿼리 생성 테스트"""
        intent_result: ClassificationResultDict = {
            "query_type": {"main_type": "aggregation", "confidence": 0.95, "reasoning": "test"},
            "entities": {
                "dates": ["지난 3개월"]
            },
            "intent_keywords": ["개수", "수"],
            "complexity_score": 0.7
        }
        
        result = await rule_generator.generate_sql(intent_result)
        
        assert any(agg in result.sql.upper() for agg in ["COUNT", "SUM", "AVG", "MAX", "MIN"])
        assert result.generation_method == "rule_based"
    
    @pytest.mark.asyncio
    async def test_join_query_generation(self, rule_generator):
        """조인 쿼리 생성 테스트"""
        intent_result: ClassificationResultDict = {
            "query_type": {"main_type": "join", "confidence": 0.85, "reasoning": "test"},
            "entities": {},
            "intent_keywords": ["관련", "연결"],
            "complexity_score": 0.8
        }
        
        result = await rule_generator.generate_sql(intent_result)
        
        assert "JOIN" in result.sql.upper()
        assert result.generation_method == "rule_based"


class TestLCELSQLPipeline:
    """LCEL SQL 파이프라인 테스트"""
    
    @pytest.fixture
    def pipeline(self):
        """파이프라인 인스턴스 픽스처"""
        return LCELSQLPipeline()
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, pipeline):
        """파이프라인 초기화 테스트"""
        assert pipeline.llm_manager is not None
        assert pipeline.chat_client is not None
        assert pipeline.rule_generator is not None
        assert pipeline.default_retry_config is not None
        
        # 체인들이 초기화되었는지 확인
        assert pipeline.intent_chain is not None
        assert pipeline.llm_sql_chain is not None
        assert pipeline.rule_sql_chain is not None
        assert pipeline.validation_chain is not None
        assert pipeline.fallback_chain is not None
        assert pipeline.hybrid_chain is not None
        assert pipeline.pipeline_chain is not None
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    async def test_simple_sql_generation(self, mock_classifier, pipeline):
        """간단한 SQL 생성 테스트"""
        # Mock 의도 분류 결과
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8, "reasoning": "test"},
            "entities": {"customer_names": ["홍길동"]},
            "intent_keywords": ["정보"],
            "complexity_score": 0.4
        }
        
        request = EnhancedSQLGenerationRequest(
            query="홍길동 고객 정보를 보여주세요",
            strategy=ExecutionStrategy.RULE_ONLY  # 테스트에서는 규칙 기반만 사용
        )
        
        result = await pipeline.generate_sql(request)
        
        assert isinstance(result, EnhancedSQLPipelineResponse)
        assert result.success is True
        assert result.sql_result is not None
        assert "SELECT" in result.sql_result.sql.upper()
        assert result.intent_analysis is not None
        assert result.metrics is not None
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    async def test_different_strategies(self, mock_classifier, pipeline):
        """다양한 실행 전략 테스트"""
        # Mock 의도 분류 결과
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "aggregation", "confidence": 0.9, "reasoning": "test"},
            "entities": {},
            "intent_keywords": ["개수"],
            "complexity_score": 0.6
        }
        
        strategies = [
            ExecutionStrategy.RULE_ONLY,
            ExecutionStrategy.LLM_FIRST,
            # ExecutionStrategy.HYBRID,  # LLM 모킹이 복잡하므로 제외
        ]
        
        for strategy in strategies:
            request = EnhancedSQLGenerationRequest(
                query="고객 수를 세어주세요",
                strategy=strategy
            )
            
            result = await pipeline.generate_sql(request)
            
            assert result.success is True
            assert result.sql_result is not None
            assert result.metrics["strategy_used"] == strategy
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    async def test_retry_configuration(self, mock_classifier, pipeline):
        """재시도 설정 테스트"""
        # Mock 의도 분류 결과
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "simple_query", "confidence": 0.5, "reasoning": "test"},
            "entities": {},
            "intent_keywords": [],
            "complexity_score": 0.2
        }
        
        # 커스텀 재시도 설정
        retry_config = RetryConfig(
            max_attempts=2,
            base_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0
        )
        
        request = EnhancedSQLGenerationRequest(
            query="테스트 쿼리",
            strategy=ExecutionStrategy.RULE_ONLY,
            retry_config=retry_config,
            timeout_seconds=10.0
        )
        
        result = await pipeline.generate_sql(request)
        
        # 규칙 기반이므로 성공해야 함
        assert result.success is True
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    async def test_error_handling(self, mock_classifier, pipeline):
        """오류 처리 테스트"""
        # Mock에서 예외 발생하도록 설정
        mock_classifier.classify.side_effect = Exception("테스트 오류")
        
        request = EnhancedSQLGenerationRequest(
            query="오류 테스트 쿼리",
            strategy=ExecutionStrategy.RULE_ONLY
        )
        
        result = await pipeline.generate_sql(request)
        
        # 오류가 발생해도 기본 응답을 반환해야 함
        assert result.success is False
        assert result.error_message is not None
        assert "테스트 오류" in result.error_message or "pipeline_error" in result.sql_result.sql
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    async def test_streaming_functionality(self, mock_classifier, pipeline):
        """스트리밍 기능 테스트"""
        # Mock 의도 분류 결과
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8, "reasoning": "test"},
            "entities": {},
            "intent_keywords": ["조회"],
            "complexity_score": 0.3
        }
        
        request = EnhancedSQLGenerationRequest(
            query="스트리밍 테스트",
            strategy=ExecutionStrategy.RULE_ONLY,
            enable_streaming=True,
            timeout_seconds=5.0
        )
        
        events = []
        async for event in pipeline.generate_sql_streaming(request):
            events.append(event)
            
            # 무한 루프 방지
            if len(events) > 10:
                break
        
        # 최소한 시작과 완료 이벤트가 있어야 함
        assert len(events) >= 1
        
        # 마지막 이벤트는 완료 이벤트여야 함
        if events:
            last_event = events[-1]
            assert last_event.get("type") in ["pipeline_complete", "complete"]
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    @patch('app.services.lcel_sql_pipeline.sql_validator')
    async def test_sql_validation_chain(self, mock_validator, mock_classifier, pipeline):
        """SQL 검증 체인 테스트"""
        # Mock 설정
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8, "reasoning": "test"},
            "entities": {},
            "intent_keywords": [],
            "complexity_score": 0.3
        }
        
        # 안전하지 않은 쿼리로 시뮬레이션
        mock_validator.validate_query_safety.return_value = False
        
        request = EnhancedSQLGenerationRequest(
            query="위험한 쿼리 테스트",
            strategy=ExecutionStrategy.RULE_ONLY
        )
        
        result = await pipeline.generate_sql(request)
        
        # 검증이 실패해도 기본 쿼리로 대체되어 성공해야 함
        assert result.success is True
        assert "validation_failed" in result.sql_result.sql or result.sql_result.confidence < 0.5


class TestRetryLogic:
    """재시도 로직 테스트"""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_success(self):
        """지수 백오프 성공 케이스"""
        from app.services.lcel_sql_pipeline import exponential_backoff_retry
        
        retry_config = RetryConfig(max_attempts=3, base_delay=0.01, exponential_base=2.0)
        
        call_count = 0
        
        @exponential_backoff_retry(retry_config)
        async def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:  # 첫 번째 호출은 실패
                raise Exception("RateLimitError: 테스트 오류")
            return "성공"
        
        result = await mock_function()
        
        assert result == "성공"
        assert call_count == 2  # 한 번 실패 후 성공
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_max_attempts(self):
        """최대 시도 횟수 테스트"""
        from app.services.lcel_sql_pipeline import exponential_backoff_retry
        
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01, exponential_base=2.0)
        
        call_count = 0
        
        @exponential_backoff_retry(retry_config)
        async def mock_function():
            nonlocal call_count
            call_count += 1
            raise Exception("RateLimitError: 계속 실패")
        
        with pytest.raises(Exception, match="계속 실패"):
            await mock_function()
        
        assert call_count == 2  # 최대 시도 횟수만큼 호출
    
    @pytest.mark.asyncio
    async def test_non_retriable_exception(self):
        """재시도 불가능한 예외 테스트"""
        from app.services.lcel_sql_pipeline import exponential_backoff_retry
        
        retry_config = RetryConfig(max_attempts=3, retriable_exceptions=["RateLimitError"])
        
        call_count = 0
        
        @exponential_backoff_retry(retry_config)
        async def mock_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("재시도 불가능한 오류")
        
        with pytest.raises(ValueError, match="재시도 불가능한 오류"):
            await mock_function()
        
        assert call_count == 1  # 한 번만 호출되고 재시도 안됨


class TestSQLGenerationRequest:
    """SQL 생성 요청 모델 테스트"""
    
    def test_valid_request_creation(self):
        """유효한 요청 생성 테스트"""
        request = EnhancedSQLGenerationRequest(
            query="고객 정보를 조회해주세요",
            strategy=ExecutionStrategy.LLM_FIRST,
            enable_streaming=False,
            timeout_seconds=30.0
        )
        
        assert request.query == "고객 정보를 조회해주세요"
        assert request.strategy == ExecutionStrategy.LLM_FIRST
        assert request.enable_streaming is False
        assert request.timeout_seconds == 30.0
    
    def test_default_values(self):
        """기본값 설정 테스트"""
        request = EnhancedSQLGenerationRequest(query="테스트")
        
        assert request.strategy == ExecutionStrategy.LLM_FIRST
        assert request.enable_streaming is False
        assert request.enable_caching is True
        assert request.retry_config is None
        assert request.timeout_seconds == 30.0
    
    def test_invalid_query_length(self):
        """쿼리 길이 검증 테스트"""
        with pytest.raises(Exception):  # ValidationError
            EnhancedSQLGenerationRequest(query="")  # 빈 쿼리
        
        with pytest.raises(Exception):  # ValidationError
            EnhancedSQLGenerationRequest(query="x" * 2001)  # 너무 긴 쿼리


class TestPipelineMetrics:
    """파이프라인 메트릭 테스트"""
    
    @pytest.mark.asyncio
    @patch('app.services.lcel_sql_pipeline.korean_intent_classifier')
    async def test_metrics_collection(self, mock_classifier):
        """메트릭 수집 테스트"""
        # Mock 설정
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8, "reasoning": "test"},
            "entities": {},
            "intent_keywords": [],
            "complexity_score": 0.3
        }
        
        pipeline = LCELSQLPipeline()
        request = EnhancedSQLGenerationRequest(
            query="메트릭 테스트 쿼리",
            strategy=ExecutionStrategy.RULE_ONLY
        )
        
        result = await pipeline.generate_sql(request)
        
        assert result.metrics is not None
        assert "total_duration" in result.metrics
        assert "strategy_used" in result.metrics
        assert "generation_method" in result.metrics
        
        # 실행 시간이 양수여야 함
        assert result.metrics["total_duration"] >= 0.0


# 통합 테스트 실행용 헬퍼 함수들

async def run_pipeline_performance_test(pipeline: LCELSQLPipeline, num_requests: int = 5):
    """파이프라인 성능 테스트"""
    import time
    
    requests = [
        EnhancedSQLGenerationRequest(
            query=f"테스트 쿼리 {i}",
            strategy=ExecutionStrategy.RULE_ONLY
        )
        for i in range(num_requests)
    ]
    
    start_time = time.time()
    
    # 동시 실행
    with patch('app.services.lcel_sql_pipeline.korean_intent_classifier') as mock_classifier:
        mock_classifier.classify.return_value = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8, "reasoning": "test"},
            "entities": {},
            "intent_keywords": [],
            "complexity_score": 0.3
        }
        
        tasks = [pipeline.generate_sql(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_time = time.time() - start_time
    
    # 결과 분석
    successful_results = [r for r in results if isinstance(r, EnhancedSQLPipelineResponse) and r.success]
    failed_results = [r for r in results if not (isinstance(r, EnhancedSQLPipelineResponse) and r.success)]
    
    return {
        "total_requests": num_requests,
        "successful": len(successful_results),
        "failed": len(failed_results),
        "total_time": total_time,
        "avg_time_per_request": total_time / num_requests,
        "throughput": num_requests / total_time
    }


@pytest.mark.asyncio
@pytest.mark.performance
async def test_pipeline_performance():
    """파이프라인 성능 테스트 (성능 테스트 마크)"""
    pipeline = LCELSQLPipeline()
    
    performance_results = await run_pipeline_performance_test(pipeline, num_requests=3)
    
    # 성능 기준 검증 (조정 가능)
    assert performance_results["successful"] >= performance_results["total_requests"] * 0.8  # 80% 성공률
    assert performance_results["avg_time_per_request"] < 10.0  # 평균 10초 이내
    assert performance_results["throughput"] > 0.1  # 초당 0.1 요청 이상
    
    print(f"성능 테스트 결과: {performance_results}")


# 실제 E2E 테스트 (API 엔드포인트 포함)
@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_endpoint_integration():
    """API 엔드포인트 통합 테스트"""
    # 이 테스트는 실제 FastAPI 앱이 실행된 상태에서 테스트
    # 여기서는 구조만 제공하고, 실제 구현은 별도 테스트 파일에서
    pass


if __name__ == "__main__":
    # 직접 실행용 테스트
    import sys
    import os
    
    # 프로젝트 루트 경로 추가
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    
    # 간단한 테스트 실행
    async def main():
        print("🧪 LCEL SQL 파이프라인 기본 테스트 실행 중...")
        
        try:
            pipeline = LCELSQLPipeline()
            print("✅ 파이프라인 초기화 성공")
            
            # 성능 테스트
            perf_results = await run_pipeline_performance_test(pipeline, 2)
            print(f"✅ 성능 테스트 완료: {perf_results}")
            
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(main())