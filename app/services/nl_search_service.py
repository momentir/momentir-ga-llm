"""
자연어 검색 서비스 - LangChain을 활용한 NL-to-SQL 변환
"""
import logging
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from sqlalchemy import text

from app.utils.llm_client import LLMClientManager
from app.database import read_only_db_manager
from app.prompts.nl_search_prompts import nl_prompt_manager
from app.services.intent_classifier import korean_intent_classifier, ClassificationResultDict

logger = logging.getLogger(__name__)


class SearchIntent(str, Enum):
    """검색 의도 분류"""
    CUSTOMER_INFO = "customer_info"
    MEMO_SEARCH = "memo_search"
    EVENT_ANALYSIS = "event_analysis"
    ANALYTICS = "analytics"
    UNKNOWN = "unknown"


class SearchType(str, Enum):
    """검색 유형"""
    SIMPLE_FILTER = "simple_filter"
    COMPLEX_JOIN = "complex_join"
    AGGREGATION = "aggregation"
    TIME_SERIES = "time_series"


class NLSearchRequest(BaseModel):
    """자연어 검색 요청 스키마"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    query: str = Field(..., description="자연어 검색 쿼리", min_length=1, max_length=1000)
    context: Optional[Dict[str, Any]] = Field(default=None, description="검색 컨텍스트 정보")
    limit: Optional[int] = Field(default=100, ge=1, le=100, description="결과 제한 수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "지난 달 가입한 고객들의 메모를 보여주세요",
                "context": {"user_id": "123"},
                "limit": 50
            }
        }


class IntentAnalysisResult(BaseModel):
    """의도 분석 결과 스키마"""
    model_config = ConfigDict(use_enum_values=True)
    
    intent: SearchIntent = Field(..., description="검색 의도")
    search_type: SearchType = Field(..., description="검색 유형")
    entities: Dict[str, Any] = Field(default_factory=dict, description="추출된 엔터티")
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도")
    reasoning: str = Field(..., description="분석 근거")


class SQLGenerationResult(BaseModel):
    """SQL 생성 결과 스키마"""
    model_config = ConfigDict()
    
    sql: str = Field(..., description="생성된 SQL 쿼리")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="SQL 파라미터")
    explanation: str = Field(..., description="쿼리 설명")
    estimated_complexity: str = Field(..., description="예상 복잡도 (low/medium/high)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sql": "SELECT * FROM customers WHERE created_at >= :start_date",
                "parameters": {"start_date": "2024-01-01"},
                "explanation": "지난 달 가입한 고객 정보를 조회하는 쿼리",
                "estimated_complexity": "low"
            }
        }


class NLSearchResponse(BaseModel):
    """자연어 검색 응답 스키마"""
    model_config = ConfigDict()
    
    intent_analysis: IntentAnalysisResult
    sql_result: SQLGenerationResult
    data: List[Dict[str, Any]] = Field(default_factory=list)
    total_rows: int = Field(default=0, ge=0)
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "intent_analysis": {
                    "intent": "customer_info",
                    "search_type": "simple_filter",
                    "entities": {"time_range": "last_month"},
                    "confidence": 0.95,
                    "reasoning": "사용자가 특정 기간의 고객 정보를 요청했습니다."
                },
                "sql_result": {
                    "sql": "SELECT * FROM customers WHERE created_at >= :start_date",
                    "parameters": {"start_date": "2024-01-01"},
                    "explanation": "지난 달 가입한 고객 조회",
                    "estimated_complexity": "low"
                },
                "data": [],
                "total_rows": 0,
                "execution_time_ms": 245.5,
                "success": True
            }
        }


class NaturalLanguageSearchService:
    """자연어 검색 서비스 클래스"""
    
    def __init__(self):
        """서비스 초기화"""
        self.llm_manager = LLMClientManager()
        self.chat_client = self.llm_manager.chat_client
        
        # 스키마 정보 (실제 DB 스키마로 업데이트 필요)
        self.database_schema = {
            "customers": ["id", "name", "email", "phone", "created_at", "updated_at"],
            "memos": ["id", "customer_id", "content", "refined_content", "created_at"],
            "events": ["id", "customer_id", "event_type", "priority", "due_date", "created_at"],
        }
        
        # LCEL 체인 초기화
        self._init_chains()
        
        logger.info("✅ NaturalLanguageSearchService 초기화 완료")
    
    def _init_chains(self):
        """LangChain LCEL 체인들 초기화"""
        # 의도 분석 체인
        self.intent_chain = self._create_intent_analysis_chain()
        
        # SQL 생성 체인  
        self.sql_generation_chain = self._create_sql_generation_chain()
        
        # 통합 검색 체인
        self.search_chain = self._create_search_chain()
    
    def _create_intent_analysis_chain(self):
        """의도 분석 체인 생성 (LCEL 패턴)"""
        async def generate_prompt_with_context(inputs):
            query = inputs["query"]
            context = inputs.get("context")
            prompt_text = await nl_prompt_manager.generate_intent_analysis_prompt(query, context)
            return {"messages": [("user", prompt_text)]}
        
        parser = PydanticOutputParser(pydantic_object=IntentAnalysisResult)
        
        return generate_prompt_with_context | ChatPromptTemplate.from_messages([("user", "{messages}")]) | self.chat_client | parser
    
    def _create_sql_generation_chain(self):
        """SQL 생성 체인 생성 (LCEL 패턴)"""
        async def generate_sql_prompt_with_context(inputs):
            query = inputs["query"]
            intent_analysis = inputs["intent_analysis"]
            context = inputs.get("context")
            prompt_text = await nl_prompt_manager.generate_sql_generation_prompt(query, intent_analysis, context)
            return {"messages": [("user", prompt_text)]}
        
        parser = PydanticOutputParser(pydantic_object=SQLGenerationResult)
        
        return generate_sql_prompt_with_context | ChatPromptTemplate.from_messages([("user", "{messages}")]) | self.chat_client | parser
    
    def _create_search_chain(self):
        """통합 검색 체인 생성 (LCEL 패턴)"""
        return RunnableParallel({
            "intent_analysis": self.intent_chain,
            "query": RunnablePassthrough()
        }).assign(
            sql_result=lambda x: self.sql_generation_chain.invoke({
                "query": x["query"],
                "intent_analysis": x["intent_analysis"]
            })
        )
    
    async def analyze_intent(self, query: str) -> IntentAnalysisResult:
        """
        자연어 쿼리의 의도를 분석합니다.
        
        Args:
            query: 자연어 검색 쿼리
            
        Returns:
            IntentAnalysisResult: 의도 분석 결과
        """
        try:
            logger.info(f"의도 분석 시작: {query}")
            
            # 1. 한국어 의도 분류기로 사전 분석
            korean_result: ClassificationResultDict = await korean_intent_classifier.classify(query)
            
            # 2. LangChain 체인으로 세밀한 분석 (선택적)
            try:
                llm_result = await self.intent_chain.ainvoke({
                    "query": query, 
                    "context": {"korean_analysis": korean_result}
                })
                
                # 한국어 분석 결과와 LLM 결과 결합
                combined_entities = {**korean_result["entities"], **llm_result.entities}
                final_confidence = max(korean_result["query_type"]["confidence"], llm_result.confidence)
                
                result = IntentAnalysisResult(
                    intent=llm_result.intent,
                    search_type=llm_result.search_type,
                    entities=combined_entities,
                    confidence=final_confidence,
                    reasoning=f"한국어 분류기: {korean_result['query_type']['reasoning']}, LLM: {llm_result.reasoning}"
                )
                
            except Exception as llm_e:
                logger.warning(f"LLM 의도 분석 실패, 한국어 분류기 결과 사용: {llm_e}")
                
                # 한국어 분류 결과를 IntentAnalysisResult로 변환
                intent_mapping = {
                    "simple_query": SearchIntent.CUSTOMER_INFO,
                    "filtering": SearchIntent.CUSTOMER_INFO,  
                    "aggregation": SearchIntent.ANALYTICS,
                    "join": SearchIntent.MEMO_SEARCH
                }
                
                search_type_mapping = {
                    "simple_query": SearchType.SIMPLE_FILTER,
                    "filtering": SearchType.SIMPLE_FILTER,
                    "aggregation": SearchType.AGGREGATION,
                    "join": SearchType.COMPLEX_JOIN
                }
                
                korean_main_type = korean_result["query_type"]["main_type"]
                
                result = IntentAnalysisResult(
                    intent=intent_mapping.get(korean_main_type, SearchIntent.UNKNOWN),
                    search_type=search_type_mapping.get(korean_main_type, SearchType.SIMPLE_FILTER),
                    entities=korean_result["entities"],
                    confidence=korean_result["query_type"]["confidence"],
                    reasoning=f"한국어 분류기만 사용: {korean_result['query_type']['reasoning']}"
                )
            
            logger.info(f"의도 분석 완료: {result.intent} (신뢰도: {result.confidence:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"의도 분석 완전 실패: {e}")
            # 최후 기본값 반환
            return IntentAnalysisResult(
                intent=SearchIntent.UNKNOWN,
                search_type=SearchType.SIMPLE_FILTER,
                entities={},
                confidence=0.0,
                reasoning=f"전체 분석 실패: {str(e)}"
            )
    
    async def generate_sql(self, query: str, intent_analysis: IntentAnalysisResult) -> SQLGenerationResult:
        """
        자연어 쿼리를 SQL로 변환합니다.
        
        Args:
            query: 자연어 검색 쿼리
            intent_analysis: 의도 분석 결과
            
        Returns:
            SQLGenerationResult: SQL 생성 결과
        """
        try:
            logger.info(f"SQL 생성 시작: {query}")
            
            result = await self.sql_generation_chain.ainvoke({
                "query": query,
                "schema": str(self.database_schema),
                "intent_analysis": intent_analysis.model_dump()
            })
            
            logger.info(f"SQL 생성 완료: {result.sql[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"SQL 생성 실패: {e}")
            # 기본 SQL 반환
            return SQLGenerationResult(
                sql="SELECT 1 as error_occurred",
                parameters={},
                explanation=f"SQL 생성 중 오류 발생: {str(e)}",
                estimated_complexity="low"
            )
    
    async def execute_sql(self, sql_result: SQLGenerationResult, limit: int = 100) -> tuple[List[Dict[str, Any]], int]:
        """
        생성된 SQL을 실행합니다.
        
        Args:
            sql_result: SQL 생성 결과
            limit: 결과 제한 수
            
        Returns:
            tuple[List[Dict[str, Any]], int]: (데이터, 총 행 수)
        """
        try:
            logger.info(f"SQL 실행 시작: {sql_result.sql[:100]}...")
            
            # 읽기 전용 DB 매니저 사용
            results = await read_only_db_manager.execute_query_with_limit(
                sql_result.sql,
                sql_result.parameters,
                limit=min(limit, 100)
            )
            
            # 결과를 딕셔너리 리스트로 변환
            data = []
            if results:
                columns = results[0]._fields if hasattr(results[0], '_fields') else []
                data = [dict(zip(columns, row)) for row in results]
            
            logger.info(f"SQL 실행 완료: {len(data)}행 반환")
            return data, len(data)
            
        except Exception as e:
            logger.error(f"SQL 실행 실패: {e}")
            return [], 0
    
    async def search(self, request: NLSearchRequest) -> NLSearchResponse:
        """
        자연어 검색을 수행합니다.
        
        Args:
            request: 검색 요청
            
        Returns:
            NLSearchResponse: 검색 결과
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"자연어 검색 시작: {request.query}")
            
            # LCEL 체인 실행
            chain_result = await self.search_chain.ainvoke(request.query)
            
            intent_analysis = chain_result["intent_analysis"]
            sql_result = chain_result["sql_result"]
            
            # SQL 실행
            data, total_rows = await self.execute_sql(sql_result, request.limit)
            
            # 실행 시간 계산
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response = NLSearchResponse(
                intent_analysis=intent_analysis,
                sql_result=sql_result,
                data=data,
                total_rows=total_rows,
                execution_time_ms=execution_time,
                success=True
            )
            
            logger.info(f"자연어 검색 완료: {total_rows}행, {execution_time:.1f}ms")
            return response
            
        except Exception as e:
            logger.error(f"자연어 검색 실패: {e}")
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return NLSearchResponse(
                intent_analysis=IntentAnalysisResult(
                    intent=SearchIntent.UNKNOWN,
                    search_type=SearchType.SIMPLE_FILTER,
                    entities={},
                    confidence=0.0,
                    reasoning="검색 실패"
                ),
                sql_result=SQLGenerationResult(
                    sql="SELECT 1",
                    parameters={},
                    explanation="오류로 인한 기본 쿼리",
                    estimated_complexity="low"
                ),
                data=[],
                total_rows=0,
                execution_time_ms=execution_time,
                success=False,
                error_message=str(e)
            )


# 싱글톤 인스턴스
nl_search_service = NaturalLanguageSearchService()