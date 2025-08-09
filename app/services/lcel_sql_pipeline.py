"""
LangChain Expression Language (LCEL) 기반 고급 SQL 생성 파이프라인

이 모듈은 자연어를 SQL로 변환하는 고급 파이프라인을 제공합니다:
- 자연어 → 의도 파싱 → SQL 생성 → 검증 체인
- Fallback 체인 (LLM 실패 시 규칙 기반)
- Retry 로직 with exponential backoff 
- LangSmith 추적 통합
- 스트리밍 응답 지원
"""

import logging
import asyncio
import time
import json
from typing import List, Dict, Any, Optional, Union, AsyncIterator, Tuple
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
from functools import wraps
import random

from pydantic import BaseModel, Field, ConfigDict
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import (
    RunnableParallel, RunnablePassthrough, RunnableLambda, 
    RunnableBranch, RunnableConfig, RunnableWithFallbacks
)
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.exceptions import OutputParserException
from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler
from langchain_core.tracers.langchain import LangChainTracer

from app.utils.langsmith_config import langsmith_manager, trace_llm_call
from app.services.intent_classifier import korean_intent_classifier, ClassificationResultDict
from app.services.sql_validator import sql_validator
from app.prompts.nl_search_prompts import nl_prompt_manager
from app.utils.llm_client import LLMClientManager
from app.database import read_only_db_manager

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """파이프라인 처리 단계"""
    INPUT_VALIDATION = "input_validation"
    INTENT_PARSING = "intent_parsing"
    SQL_GENERATION = "sql_generation"
    SQL_VALIDATION = "sql_validation"
    SQL_EXECUTION = "sql_execution"
    RESULT_FORMATTING = "result_formatting"
    ERROR_HANDLING = "error_handling"


class ExecutionStrategy(str, Enum):
    """실행 전략"""
    LLM_FIRST = "llm_first"      # LLM 우선, 실패시 규칙 기반
    RULE_FIRST = "rule_first"    # 규칙 기반 우선, 실패시 LLM
    HYBRID = "hybrid"            # 병렬 실행 후 결과 비교
    LLM_ONLY = "llm_only"        # LLM만 사용
    RULE_ONLY = "rule_only"      # 규칙 기반만 사용


class RetryConfig(BaseModel):
    """재시도 설정"""
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay: float = Field(default=1.0, gt=0)
    max_delay: float = Field(default=60.0, gt=0)
    exponential_base: float = Field(default=2.0, gt=1)
    jitter: bool = Field(default=True)
    retriable_exceptions: List[str] = Field(default_factory=lambda: [
        "RateLimitError", "APITimeoutError", "APIConnectionError", 
        "InternalServerError", "ServiceUnavailableError"
    ])


@dataclass
class PipelineMetrics:
    """파이프라인 실행 메트릭"""
    stage_timings: Dict[str, float]
    total_duration: float
    retry_counts: Dict[str, int]
    fallback_used: bool
    llm_calls_count: int
    cache_hits: int
    success: bool
    error_message: Optional[str] = None


class StreamingCallbackHandler(AsyncCallbackHandler):
    """스트리밍 응답을 위한 콜백 핸들러"""
    
    def __init__(self, stream_queue: asyncio.Queue):
        self.stream_queue = stream_queue
        self.current_stage = ""
        
    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        await self.stream_queue.put({
            "type": "llm_start",
            "stage": self.current_stage,
            "timestamp": time.time()
        })
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        await self.stream_queue.put({
            "type": "token",
            "content": token,
            "stage": self.current_stage,
            "timestamp": time.time()
        })
    
    async def on_llm_end(self, response, **kwargs) -> None:
        await self.stream_queue.put({
            "type": "llm_end",
            "stage": self.current_stage,
            "timestamp": time.time()
        })
    
    async def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        chain_name = serialized.get("name", "unknown")
        self.current_stage = chain_name
        await self.stream_queue.put({
            "type": "stage_start",
            "stage": chain_name,
            "timestamp": time.time()
        })
    
    async def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        await self.stream_queue.put({
            "type": "stage_end",
            "stage": self.current_stage,
            "timestamp": time.time()
        })


class EnhancedSQLGenerationRequest(BaseModel):
    """향상된 SQL 생성 요청"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    query: str = Field(..., description="자연어 쿼리", min_length=1, max_length=2000)
    context: Optional[Dict[str, Any]] = Field(default=None, description="추가 컨텍스트")
    strategy: ExecutionStrategy = Field(default=ExecutionStrategy.LLM_FIRST)
    enable_streaming: bool = Field(default=False)
    enable_caching: bool = Field(default=True)
    retry_config: Optional[RetryConfig] = Field(default=None)
    timeout_seconds: float = Field(default=30.0, gt=0)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "지난 3개월간 가입한 30대 고객들의 평균 보험료",
                "context": {"user_id": "123", "department": "sales"},
                "strategy": "llm_first",
                "enable_streaming": False,
                "timeout_seconds": 30.0
            }
        }
    )


class SQLGenerationResult(BaseModel):
    """SQL 생성 결과"""
    model_config = ConfigDict()
    
    sql: str = Field(..., description="생성된 SQL")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(..., description="쿼리 설명")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    complexity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_rows: Optional[int] = Field(default=None)
    estimated_execution_time: Optional[float] = Field(default=None)
    
    # 메타데이터
    generation_method: str = Field(default="llm")  # "llm", "rule_based", "hybrid"
    fallback_used: bool = Field(default=False)
    cache_hit: bool = Field(default=False)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sql": "SELECT AVG(premium_amount) FROM customers WHERE age_range = '30-39' AND created_at >= '2024-05-01'",
                "parameters": {"age_range": "30-39", "start_date": "2024-05-01"},
                "explanation": "30대 고객들의 평균 보험료를 계산하는 쿼리입니다.",
                "confidence": 0.92,
                "complexity_score": 0.6,
                "generation_method": "llm"
            }
        }
    )


class EnhancedSQLPipelineResponse(BaseModel):
    """향상된 SQL 파이프라인 응답"""
    model_config = ConfigDict()
    
    # 의도 분석 결과
    intent_analysis: ClassificationResultDict
    
    # SQL 생성 결과
    sql_result: SQLGenerationResult
    
    # 실행 결과 (선택적)
    execution_data: Optional[List[Dict[str, Any]]] = Field(default=None)
    execution_success: bool = Field(default=False)
    
    # 메트릭
    metrics: Optional[Dict[str, Any]] = Field(default=None)
    
    # 전체 성공 여부
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_analysis": {
                    "query_type": {"main_type": "aggregation", "confidence": 0.9},
                    "entities": {"dates": ["지난 3개월"], "amounts": ["평균"]},
                    "complexity_score": 0.7
                },
                "sql_result": {
                    "sql": "SELECT AVG(premium_amount) FROM customers WHERE created_at >= '2024-05-01'",
                    "explanation": "지난 3개월간 가입 고객들의 평균 보험료",
                    "confidence": 0.92,
                    "generation_method": "llm"
                },
                "success": True
            }
        }
    )


def exponential_backoff_retry(retry_config: RetryConfig):
    """지수 백오프 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 재시도 가능한 예외인지 확인
                    if not any(exc_type in str(type(e).__name__) for exc_type in retry_config.retriable_exceptions):
                        logger.info(f"재시도 불가능한 예외 발생: {type(e).__name__}")
                        raise
                    
                    # 마지막 시도인 경우 예외 발생
                    if attempt == retry_config.max_attempts - 1:
                        break
                    
                    # 지수 백오프 계산
                    delay = min(
                        retry_config.base_delay * (retry_config.exponential_base ** attempt),
                        retry_config.max_delay
                    )
                    
                    # 지터 추가
                    if retry_config.jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(f"재시도 {attempt + 1}/{retry_config.max_attempts}: {delay:.2f}초 후 재시도 - {e}")
                    await asyncio.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator


class RuleBasedSQLGenerator:
    """규칙 기반 SQL 생성기"""
    
    def __init__(self):
        self.query_templates = {
            "simple_query": "SELECT * FROM {table} WHERE 1=1 {conditions} LIMIT {limit}",
            "filtering": "SELECT * FROM {table} WHERE {conditions} LIMIT {limit}",
            "aggregation": "SELECT {aggregation} FROM {table} WHERE {conditions}",
            "join": "SELECT * FROM {main_table} JOIN {join_table} ON {join_condition} WHERE {conditions} LIMIT {limit}"
        }
        
        self.entity_to_column_mapping = {
            "customer_names": "name",
            "dates": "created_at", 
            "product_names": "product_type",
            "amounts": "amount",
            "locations": "location"
        }
    
    async def generate_sql(self, intent_result: ClassificationResultDict) -> SQLGenerationResult:
        """규칙 기반 SQL 생성"""
        try:
            query_type = intent_result["query_type"]["main_type"]
            entities = intent_result["entities"]
            
            # 기본 테이블 결정
            main_table = "customers"  # 기본값
            
            # 쿼리 타입별 SQL 생성
            if query_type == "aggregation":
                sql, params = self._generate_aggregation_sql(entities)
            elif query_type == "filtering":
                sql, params = self._generate_filtering_sql(entities)
            elif query_type == "join":
                sql, params = self._generate_join_sql(entities)
            else:  # simple_query
                sql, params = self._generate_simple_sql(entities)
            
            return SQLGenerationResult(
                sql=sql,
                parameters=params,
                explanation=f"규칙 기반으로 생성된 {query_type} 쿼리",
                confidence=0.7,
                complexity_score=0.5,
                generation_method="rule_based"
            )
            
        except Exception as e:
            logger.error(f"규칙 기반 SQL 생성 실패: {e}")
            raise
    
    def _generate_aggregation_sql(self, entities: Dict[str, List[str]]) -> Tuple[str, Dict[str, Any]]:
        """집계 쿼리 생성"""
        aggregation = "COUNT(*)"
        table = "customers"
        conditions = []
        params = {}
        
        # 엔티티에서 조건 추출
        for entity_type, values in entities.items():
            if entity_type == "dates" and values:
                conditions.append("created_at >= %(start_date)s")
                params["start_date"] = "2024-05-01"  # 간단한 예시
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT {aggregation} FROM {table} WHERE {where_clause}"
        
        return sql, params
    
    def _generate_filtering_sql(self, entities: Dict[str, List[str]]) -> Tuple[str, Dict[str, Any]]:
        """필터링 쿼리 생성"""
        table = "customers"
        conditions = []
        params = {}
        
        # 엔티티에서 조건 추출
        for entity_type, values in entities.items():
            if entity_type == "customer_names" and values:
                conditions.append("name = %(customer_name)s")
                params["customer_name"] = values[0]
            elif entity_type == "dates" and values:
                conditions.append("created_at >= %(start_date)s")
                params["start_date"] = "2024-05-01"
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM {table} WHERE {where_clause} LIMIT 100"
        
        return sql, params
    
    def _generate_simple_sql(self, entities: Dict[str, List[str]]) -> Tuple[str, Dict[str, Any]]:
        """단순 조회 쿼리 생성"""
        return "SELECT * FROM customers LIMIT 100", {}
    
    def _generate_join_sql(self, entities: Dict[str, List[str]]) -> Tuple[str, Dict[str, Any]]:
        """조인 쿼리 생성"""
        sql = """
        SELECT c.*, m.content 
        FROM customers c 
        LEFT JOIN memos m ON c.id = m.customer_id 
        WHERE 1=1 
        LIMIT 100
        """
        return sql.strip(), {}


class LCELSQLPipeline:
    """LCEL 기반 고급 SQL 생성 파이프라인"""
    
    def __init__(self):
        """파이프라인 초기화"""
        self.llm_manager = LLMClientManager()
        self.chat_client = self.llm_manager.chat_client
        self.rule_generator = RuleBasedSQLGenerator()
        self.metrics_cache: Dict[str, PipelineMetrics] = {}
        
        # 기본 재시도 설정
        self.default_retry_config = RetryConfig()
        
        # LCEL 체인들 초기화
        self._init_chains()
        
        logger.info("✅ LCELSQLPipeline 초기화 완료")
    
    def _init_chains(self):
        """LCEL 체인들 초기화"""
        
        # 1. 의도 분석 체인
        self.intent_chain = self._create_intent_chain()
        
        # 2. LLM SQL 생성 체인
        self.llm_sql_chain = self._create_llm_sql_chain()
        
        # 3. 규칙 기반 SQL 생성 체인
        self.rule_sql_chain = self._create_rule_sql_chain()
        
        # 4. SQL 검증 체인
        self.validation_chain = self._create_validation_chain()
        
        # 5. Fallback 체인 (LLM 실패 시 규칙 기반)
        self.fallback_chain = RunnableWithFallbacks(
            runnable=self.llm_sql_chain,
            fallbacks=[self.rule_sql_chain]
        )
        
        # 6. 하이브리드 체인 (병렬 실행)
        self.hybrid_chain = self._create_hybrid_chain()
        
        # 7. 전체 파이프라인 체인
        self.pipeline_chain = self._create_pipeline_chain()
    
    def _create_intent_chain(self):
        """의도 분석 체인 생성"""
        async def analyze_intent(inputs: Dict[str, Any]) -> Dict[str, Any]:
            query = inputs["query"]
            
            # 한국어 의도 분류기 실행
            intent_result = await korean_intent_classifier.classify(query)
            
            return {
                **inputs,
                "intent_analysis": intent_result
            }
        
        return RunnableLambda(analyze_intent).with_config(
            RunnableConfig(run_name="intent_analysis")
        )
    
    def _create_llm_sql_chain(self):
        """LLM SQL 생성 체인"""
        
        # 프롬프트 생성 함수
        async def create_sql_prompt(inputs: Dict[str, Any]) -> Dict[str, Any]:
            query = inputs["query"]
            intent_analysis = inputs["intent_analysis"]
            context = inputs.get("context", {})
            
            # 프롬프트 생성
            prompt_text = await nl_prompt_manager.generate_sql_generation_prompt(
                query, intent_analysis, context
            )
            
            return {"prompt": prompt_text}
        
        # 결과 파싱 함수
        def parse_sql_result(response: str) -> SQLGenerationResult:
            try:
                # JSON 파싱 시도
                import json
                parsed = json.loads(response)
                return SQLGenerationResult(**parsed)
            except (json.JSONDecodeError, ValueError):
                # 간단한 텍스트 파싱
                return SQLGenerationResult(
                    sql=response.strip(),
                    explanation="LLM에서 생성된 SQL 쿼리",
                    confidence=0.8,
                    generation_method="llm"
                )
        
        # LLM 호출 체인
        llm_chain = (
            RunnableLambda(create_sql_prompt)
            | RunnableLambda(lambda x: x["prompt"])
            | self.chat_client 
            | StrOutputParser()
            | RunnableLambda(parse_sql_result)
        )
        
        return llm_chain.with_config(
            RunnableConfig(run_name="llm_sql_generation")
        )
    
    def _create_rule_sql_chain(self):
        """규칙 기반 SQL 생성 체인"""
        async def generate_rule_sql(inputs: Dict[str, Any]) -> SQLGenerationResult:
            intent_analysis = inputs["intent_analysis"]
            result = await self.rule_generator.generate_sql(intent_analysis)
            result.generation_method = "rule_based"
            return result
        
        return RunnableLambda(generate_rule_sql).with_config(
            RunnableConfig(run_name="rule_sql_generation")
        )
    
    def _create_validation_chain(self):
        """SQL 검증 체인"""
        async def validate_sql(sql_result: SQLGenerationResult) -> SQLGenerationResult:
            try:
                # SQL 보안 검증
                is_safe = await sql_validator.validate_query_safety(sql_result.sql)
                
                if not is_safe:
                    logger.warning(f"안전하지 않은 SQL 감지: {sql_result.sql}")
                    # 안전하지 않은 쿼리는 기본 쿼리로 대체
                    sql_result.sql = "SELECT 1 as validation_failed"
                    sql_result.explanation = "보안상 안전하지 않은 쿼리로 인해 기본 쿼리로 대체됨"
                    sql_result.confidence = 0.1
                
                return sql_result
                
            except Exception as e:
                logger.error(f"SQL 검증 실패: {e}")
                return sql_result
        
        return RunnableLambda(validate_sql).with_config(
            RunnableConfig(run_name="sql_validation")
        )
    
    def _create_hybrid_chain(self):
        """하이브리드 체인 (LLM과 규칙 기반 병렬 실행)"""
        return RunnableParallel({
            "llm_result": self.llm_sql_chain,
            "rule_result": self.rule_sql_chain
        }).with_config(
            RunnableConfig(run_name="hybrid_generation")
        )
    
    def _create_pipeline_chain(self):
        """전체 파이프라인 체인"""
        
        # 전략별 SQL 생성 분기
        def select_generation_strategy(inputs: Dict[str, Any]):
            strategy = inputs.get("strategy", ExecutionStrategy.LLM_FIRST)
            
            if strategy == ExecutionStrategy.LLM_ONLY:
                return self.llm_sql_chain
            elif strategy == ExecutionStrategy.RULE_ONLY:
                return self.rule_sql_chain  
            elif strategy == ExecutionStrategy.HYBRID:
                return self.hybrid_chain
            else:  # LLM_FIRST 또는 RULE_FIRST
                return self.fallback_chain
        
        # 파이프라인 구성
        pipeline = (
            self.intent_chain
            | RunnableBranch(
                (lambda x: x.get("strategy") == ExecutionStrategy.LLM_ONLY, self.llm_sql_chain),
                (lambda x: x.get("strategy") == ExecutionStrategy.RULE_ONLY, self.rule_sql_chain),
                (lambda x: x.get("strategy") == ExecutionStrategy.HYBRID, self.hybrid_chain),
                self.fallback_chain  # 기본값
            )
            | self.validation_chain
        )
        
        return pipeline.with_config(
            RunnableConfig(run_name="full_pipeline")
        )
    
    @trace_llm_call("lcel_sql_pipeline_generate", metadata={"version": "2.0"})
    async def generate_sql(
        self, 
        request: EnhancedSQLGenerationRequest,
        stream_queue: Optional[asyncio.Queue] = None
    ) -> EnhancedSQLPipelineResponse:
        """
        고급 SQL 생성 파이프라인 실행
        
        Args:
            request: SQL 생성 요청
            stream_queue: 스트리밍용 큐 (선택적)
            
        Returns:
            EnhancedSQLPipelineResponse: 파이프라인 실행 결과
        """
        
        start_time = time.time()
        metrics = PipelineMetrics(
            stage_timings={},
            total_duration=0.0,
            retry_counts={},
            fallback_used=False,
            llm_calls_count=0,
            cache_hits=0,
            success=False
        )
        
        try:
            logger.info(f"🚀 LCEL SQL 파이프라인 시작: {request.query} (전략: {request.strategy})")
            
            # 재시도 설정
            retry_config = request.retry_config or self.default_retry_config
            
            # 스트리밍 콜백 설정
            callbacks = []
            if request.enable_streaming and stream_queue:
                streaming_callback = StreamingCallbackHandler(stream_queue)
                callbacks.append(streaming_callback)
            
            # LangSmith 콜백 추가
            langsmith_callbacks = langsmith_manager.get_callbacks("lcel-sql-pipeline")
            callbacks.extend(langsmith_callbacks)
            
            # 파이프라인 입력 준비
            pipeline_input = {
                "query": request.query,
                "context": request.context or {},
                "strategy": request.strategy
            }
            
            # 재시도 로직과 함께 파이프라인 실행
            @exponential_backoff_retry(retry_config)
            async def execute_with_retry():
                config = RunnableConfig(callbacks=callbacks)
                return await self.pipeline_chain.ainvoke(pipeline_input, config)
            
            # 타임아웃과 함께 실행
            try:
                result = await asyncio.wait_for(
                    execute_with_retry(),
                    timeout=request.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise Exception(f"파이프라인 실행 시간 초과: {request.timeout_seconds}초")
            
            # 결과 처리
            if request.strategy == ExecutionStrategy.HYBRID:
                # 하이브리드 전략의 경우 최적 결과 선택
                llm_result = result["llm_result"]
                rule_result = result["rule_result"]
                
                # 신뢰도 기반 선택
                sql_result = llm_result if llm_result.confidence > rule_result.confidence else rule_result
                sql_result.generation_method = "hybrid"
                
            else:
                sql_result = result
            
            # 의도 분석 결과는 별도로 추출해야 함
            # (실제 구현에서는 체인의 중간 결과를 저장하는 로직 필요)
            intent_analysis = await korean_intent_classifier.classify(request.query)
            
            # 메트릭 계산
            metrics.total_duration = time.time() - start_time
            metrics.success = True
            
            response = EnhancedSQLPipelineResponse(
                intent_analysis=intent_analysis,
                sql_result=sql_result,
                success=True,
                metrics={
                    "total_duration": metrics.total_duration,
                    "strategy_used": request.strategy,
                    "generation_method": sql_result.generation_method
                }
            )
            
            logger.info(f"✅ LCEL SQL 파이프라인 완료: {metrics.total_duration:.2f}초")
            return response
            
        except Exception as e:
            metrics.total_duration = time.time() - start_time
            metrics.success = False
            metrics.error_message = str(e)
            
            logger.error(f"❌ LCEL SQL 파이프라인 실패: {e}")
            
            # 기본 응답 반환
            return EnhancedSQLPipelineResponse(
                intent_analysis={"query_type": {"main_type": "simple_query", "confidence": 0.1}, "entities": {}, "intent_keywords": [], "complexity_score": 0.0},
                sql_result=SQLGenerationResult(
                    sql="SELECT 1 as pipeline_error", 
                    explanation=f"파이프라인 실행 실패: {str(e)}",
                    generation_method="error_fallback"
                ),
                success=False,
                error_message=str(e),
                metrics={
                    "total_duration": metrics.total_duration,
                    "error": str(e)
                }
            )
    
    async def generate_sql_streaming(
        self, 
        request: EnhancedSQLGenerationRequest
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        스트리밍 SQL 생성
        
        Args:
            request: SQL 생성 요청 (enable_streaming=True 설정)
            
        Yields:
            Dict[str, Any]: 스트리밍 이벤트들
        """
        
        # 스트리밍 큐 생성
        stream_queue = asyncio.Queue()
        
        # 백그라운드에서 파이프라인 실행
        pipeline_task = asyncio.create_task(
            self.generate_sql(request, stream_queue)
        )
        
        try:
            # 스트리밍 이벤트 전송
            while True:
                try:
                    # 큐에서 이벤트 대기 (타임아웃 설정)
                    event = await asyncio.wait_for(stream_queue.get(), timeout=1.0)
                    yield event
                    
                    # 파이프라인 완료 확인
                    if event.get("type") == "pipeline_complete":
                        break
                        
                except asyncio.TimeoutError:
                    # 파이프라인 작업이 완료되었는지 확인
                    if pipeline_task.done():
                        break
                    continue
            
            # 최종 결과 전송
            final_result = await pipeline_task
            yield {
                "type": "pipeline_complete",
                "result": final_result.model_dump(),
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"스트리밍 중 오류 발생: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": time.time()
            }
        finally:
            # 백그라운드 작업 정리
            if not pipeline_task.done():
                pipeline_task.cancel()
                try:
                    await pipeline_task
                except asyncio.CancelledError:
                    pass


# 싱글톤 인스턴스
lcel_sql_pipeline = LCELSQLPipeline()