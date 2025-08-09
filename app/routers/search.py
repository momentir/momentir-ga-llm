"""
자연어 검색 API 라우터

FastAPI 0.104+ 의존성 주입 패턴과 Pydantic v2를 사용한
자연어 검색 엔드포인트 및 WebSocket 실시간 검색을 제공합니다.
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Union, Annotated, AsyncGenerator
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import (
    APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect,
    Query, Path, Body, BackgroundTasks, Request, Response, status
)
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field
from pydantic.types import StringConstraints
from pydantic_core import ValidationError

from app.services.lcel_sql_pipeline import (
    lcel_sql_pipeline,
    EnhancedSQLGenerationRequest,
    EnhancedSQLPipelineResponse,
    ExecutionStrategy,
    RetryConfig
)
from app.services.nl_search_service import (
    nl_search_service,
    NLSearchRequest,
    NLSearchResponse
)
from app.services.search_cache_service import search_cache_service
from app.services.search_formatter import search_formatter, HighlightOptions
from app.utils.langsmith_config import trace_llm_call
from app.database import read_only_db_manager

logger = logging.getLogger(__name__)

# FastAPI 0.104+ 스타일 라우터 생성
router = APIRouter(
    prefix="/api/search",
    tags=["Natural Language Search"],
    responses={
        404: {"description": "검색 결과를 찾을 수 없습니다"},
        422: {"description": "입력 데이터 검증 오류"},
        500: {"description": "내부 서버 오류"}
    }
)

# 보안 스키마 정의 (선택적)
security = HTTPBearer(auto_error=False)

# Pydantic v2 스타일 타입 정의
QueryString = Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]
ContextData = Annotated[Dict[str, Any], Field(default_factory=dict)]
LimitValue = Annotated[int, Field(ge=1, le=1000, default=100)]


# Request/Response 모델들 (Pydantic v2)
class SearchIntent(BaseModel):
    """검색 의도 정보"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    intent_type: str = Field(..., description="검색 의도 타입", examples=["customer_search", "data_analysis"])
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도 점수")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    entities: Dict[str, List[str]] = Field(default_factory=dict, description="추출된 엔티티")


class SearchOptions(BaseModel):
    """검색 옵션"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    strategy: ExecutionStrategy = Field(
        default=ExecutionStrategy.LLM_FIRST,
        description="SQL 생성 전략",
        examples=["llm_first", "rule_first", "hybrid"]
    )
    enable_streaming: bool = Field(
        default=False,
        description="스트리밍 응답 활성화"
    )
    include_explanation: bool = Field(
        default=True,
        description="쿼리 설명 포함 여부"
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="타임아웃 (초)"
    )
    
    @field_validator('strategy', mode='before')
    @classmethod
    def validate_strategy(cls, v):
        """전략 값 검증"""
        if isinstance(v, str):
            try:
                return ExecutionStrategy(v)
            except ValueError:
                raise ValueError(f"유효하지 않은 전략: {v}")
        return v


class NaturalLanguageSearchRequest(BaseModel):
    """자연어 검색 요청"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "query": "30대 고객들의 평균 보험료를 지역별로 분석해주세요",
                "context": {"department": "analytics", "user_level": "advanced"},
                "options": {
                    "strategy": "hybrid",
                    "include_explanation": True,
                    "timeout_seconds": 45.0
                },
                "limit": 100
            }
        }
    )
    
    query: QueryString = Field(
        ..., 
        description="자연어 검색 쿼리",
        examples=["30대 고객 목록", "지난달 가입한 고객 수"]
    )
    context: ContextData = Field(
        default_factory=dict,
        description="검색 컨텍스트 정보",
        examples=[{"department": "sales", "region": "seoul"}]
    )
    options: SearchOptions = Field(
        default_factory=SearchOptions,
        description="검색 옵션"
    )
    limit: LimitValue = Field(
        default=100,
        description="결과 제한 수"
    )
    
    @field_validator('context')
    @classmethod
    def validate_context(cls, v):
        """컨텍스트 검증"""
        if v and len(json.dumps(v)) > 10000:  # 10KB 제한
            raise ValueError("컨텍스트 데이터가 너무 큽니다")
        return v


class SearchExecution(BaseModel):
    """검색 실행 정보"""
    model_config = ConfigDict(validate_assignment=True)
    
    sql_query: str = Field(..., description="실행된 SQL 쿼리")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="SQL 파라미터")
    execution_time_ms: float = Field(..., ge=0, description="실행 시간 (밀리초)")
    rows_affected: int = Field(..., ge=0, description="영향받은 행 수")
    strategy_used: str = Field(..., description="사용된 전략")


class NaturalLanguageSearchResponse(BaseModel):
    """자연어 검색 응답"""
    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "request_id": "req_123456789",
                "query": "30대 고객들의 평균 보험료",
                "intent": {
                    "intent_type": "data_analysis",
                    "confidence": 0.92,
                    "keywords": ["30대", "고객", "평균", "보험료"],
                    "entities": {"age_group": ["30대"], "metric": ["평균", "보험료"]}
                },
                "execution": {
                    "sql_query": "SELECT AVG(premium) FROM customers WHERE age BETWEEN 30 AND 39",
                    "parameters": {},
                    "execution_time_ms": 156.7,
                    "rows_affected": 1,
                    "strategy_used": "llm_first"
                },
                "data": [{"avg_premium": 125000}],
                "total_rows": 1,
                "success": True,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    request_id: str = Field(..., description="요청 고유 ID")
    query: str = Field(..., description="원본 쿼리")
    intent: SearchIntent = Field(..., description="분석된 검색 의도")
    execution: SearchExecution = Field(..., description="검색 실행 정보")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="검색 결과 데이터")
    total_rows: int = Field(..., ge=0, description="총 결과 행 수")
    success: bool = Field(..., description="검색 성공 여부")
    error_message: Optional[str] = Field(None, description="오류 메시지 (실패시)")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")
    
    @computed_field
    @property
    def has_data(self) -> bool:
        """데이터 존재 여부"""
        return len(self.data) > 0
    
    @computed_field
    @property
    def execution_summary(self) -> str:
        """실행 요약"""
        return f"{self.execution.strategy_used} 전략으로 {self.execution.execution_time_ms:.1f}ms에 {self.total_rows}행 검색"


class StreamingSearchEvent(BaseModel):
    """스트리밍 검색 이벤트"""
    model_config = ConfigDict(validate_assignment=True)
    
    event_type: str = Field(..., description="이벤트 타입")
    timestamp: datetime = Field(default_factory=datetime.now, description="이벤트 시간")
    data: Dict[str, Any] = Field(default_factory=dict, description="이벤트 데이터")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="진행률 (0-1)")


# 의존성 주입 함수들 (FastAPI 0.104+ 패턴)
async def get_search_context(
    request: Request,
    user_agent: Annotated[Optional[str], Depends(lambda r: r.headers.get("user-agent"))] = None,
    x_request_id: Annotated[Optional[str], Depends(lambda r: r.headers.get("x-request-id"))] = None
) -> Dict[str, Any]:
    """검색 컨텍스트 추출"""
    return {
        "client_ip": getattr(request.client, 'host', 'unknown'),
        "user_agent": user_agent,
        "request_id": x_request_id or f"req_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "timestamp": datetime.now().isoformat()
    }


async def get_auth_info(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)] = None
) -> Dict[str, Any]:
    """인증 정보 추출 (선택적)"""
    if credentials:
        # 여기서 실제 토큰 검증 로직을 구현할 수 있습니다
        return {"authenticated": True, "token": credentials.credentials}
    return {"authenticated": False}


async def validate_search_permissions(
    auth_info: Annotated[Dict[str, Any], Depends(get_auth_info)],
    request_data: Optional[Dict[str, Any]] = None
) -> bool:
    """검색 권한 검증"""
    # 실제 권한 검증 로직을 구현할 수 있습니다
    # 현재는 모든 요청을 허용
    return True


# WebSocket 연결 관리자
class WebSocketManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str, metadata: Dict[str, Any] = None):
        """WebSocket 연결 수락"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = metadata or {}
        logger.info(f"WebSocket 클라이언트 연결: {client_id}")
    
    def disconnect(self, client_id: str):
        """WebSocket 연결 해제"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
        logger.info(f"WebSocket 클라이언트 해제: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str):
        """개별 클라이언트에게 메시지 전송"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.error(f"WebSocket 메시지 전송 실패 ({client_id}): {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """모든 연결된 클라이언트에게 브로드캐스트"""
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.error(f"브로드캐스트 실패 ({client_id}): {e}")
                disconnected_clients.append(client_id)
        
        # 연결 실패한 클라이언트 제거
        for client_id in disconnected_clients:
            self.disconnect(client_id)


# 전역 WebSocket 관리자
websocket_manager = WebSocketManager()


# API 엔드포인트들
@router.post(
    "/natural-language",
    response_model=NaturalLanguageSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="자연어 검색",
    description="""
    자연어 쿼리를 SQL로 변환하여 데이터베이스를 검색합니다.
    
    ## 주요 기능
    - 한국어 자연어 쿼리 지원
    - 다양한 SQL 생성 전략
    - 실시간 성능 모니터링
    - 자동 쿼리 최적화
    
    ## 전략 설명
    - **llm_first**: LLM 우선, 실패시 규칙 기반 (기본값)
    - **rule_first**: 규칙 기반 우선, 실패시 LLM
    - **hybrid**: 병렬 실행 후 최적 결과 선택
    - **llm_only**: LLM만 사용
    - **rule_only**: 규칙 기반만 사용
    """,
    response_description="검색 결과 및 실행 정보"
)
@trace_llm_call("natural_language_search_api")
async def natural_language_search(
    request_data: Annotated[NaturalLanguageSearchRequest, Body(
        ...,
        examples=[
            {
                "query": "30대 고객들의 평균 보험료를 지역별로 보여주세요",
                "context": {"department": "analytics"},
                "options": {"strategy": "llm_first", "timeout_seconds": 30.0},
                "limit": 100
            },
            {
                "query": "최근 1개월간 가입한 고객 수",
                "options": {"strategy": "rule_first", "include_explanation": False},
                "limit": 50
            }
        ]
    )],
    search_context: Annotated[Dict[str, Any], Depends(get_search_context)],
    auth_info: Annotated[Dict[str, Any], Depends(get_auth_info)],
    has_permission: Annotated[bool, Depends(validate_search_permissions)],
    background_tasks: BackgroundTasks,
    use_cache: Annotated[bool, Query(description="캐시 사용 여부")] = True,
    enable_highlighting: Annotated[bool, Query(description="검색어 하이라이팅 활성화")] = True
) -> NaturalLanguageSearchResponse:
    """자연어 검색 메인 엔드포인트"""
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="검색 권한이 없습니다"
        )
    
    request_id = search_context["request_id"]
    start_time = datetime.now()
    
    try:
        logger.info(f"🔍 자연어 검색 시작 [{request_id}]: {request_data.query} (캐시={use_cache}, 하이라이팅={enable_highlighting})")
        
        # 1. 캐시 조회 (사용 설정 시)
        if use_cache:
            cache_context = {
                "context": request_data.context,
                "auth_info": {k: v for k, v in auth_info.items() if k != "token"},  # 토큰은 캐시 키에서 제외
                "limit": request_data.limit
            }
            
            cached_result = await search_cache_service.get_cached_result(
                query=request_data.query,
                context=cache_context,
                options=request_data.options.model_dump()
            )
            
            if cached_result:
                logger.info(f"✅ 캐시 히트 [{request_id}]: 캐시된 결과 반환")
                
                # 캐시된 응답에 요청 ID 업데이트
                cached_result.update({
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 하이라이팅 처리 (캐시된 결과에도 적용)
                if enable_highlighting and cached_result.get("data"):
                    highlight_options = HighlightOptions(case_sensitive=False, whole_words_only=False)
                    cached_result["data"] = search_formatter.highlight_search_results(
                        cached_result["data"], 
                        request_data.query,
                        highlight_options
                    )
                
                return NaturalLanguageSearchResponse(**cached_result)
        
        # 2. 캐시 미스 - 실제 검색 수행
        logger.info(f"❌ 캐시 미스 [{request_id}]: 새로운 검색 수행")
        
        # LCEL 파이프라인 요청 생성
        pipeline_request = EnhancedSQLGenerationRequest(
            query=request_data.query,
            context={**request_data.context, **search_context, **auth_info},
            strategy=request_data.options.strategy,
            enable_streaming=request_data.options.enable_streaming,
            timeout_seconds=request_data.options.timeout_seconds
        )
        
        # SQL 생성 및 실행
        pipeline_result = await lcel_sql_pipeline.generate_sql(pipeline_request)
        
        if not pipeline_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SQL 생성 실패: {pipeline_result.error_message}"
            )
        
        # 데이터베이스 실행
        try:
            execution_start = datetime.now()
            db_results = await read_only_db_manager.execute_query_with_limit(
                pipeline_result.sql_result.sql,
                pipeline_result.sql_result.parameters,
                limit=request_data.limit
            )
            execution_time = (datetime.now() - execution_start).total_seconds() * 1000
            
            # 결과를 딕셔너리 리스트로 변환
            data = []
            if db_results:
                columns = db_results[0]._fields if hasattr(db_results[0], '_fields') else []
                data = [dict(zip(columns, row)) for row in db_results]
            
            logger.info(f"✅ 검색 완료 [{request_id}]: {len(data)}행")
            
        except Exception as db_error:
            logger.error(f"❌ DB 실행 실패 [{request_id}]: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"데이터베이스 실행 오류: {str(db_error)}"
            )
        
        # 3. 결과 포맷팅 (하이라이팅)
        formatted_data = data
        if enable_highlighting and data:
            highlight_options = HighlightOptions(case_sensitive=False, whole_words_only=False)
            formatted_data = search_formatter.highlight_search_results(
                data, 
                request_data.query,
                highlight_options
            )
            logger.debug(f"하이라이팅 처리 완료 [{request_id}]: {len(formatted_data)}행")
        
        # 4. 응답 생성
        response_data = {
            "request_id": request_id,
            "query": request_data.query,
            "intent": {
                "intent_type": pipeline_result.intent_analysis.get("query_type", {}).get("main_type", "unknown"),
                "confidence": pipeline_result.intent_analysis.get("query_type", {}).get("confidence", 0.0),
                "keywords": pipeline_result.intent_analysis.get("intent_keywords", []),
                "entities": pipeline_result.intent_analysis.get("entities", {})
            },
            "execution": {
                "sql_query": pipeline_result.sql_result.sql,
                "parameters": pipeline_result.sql_result.parameters,
                "execution_time_ms": execution_time,
                "rows_affected": len(data),
                "strategy_used": pipeline_result.sql_result.generation_method
            },
            "data": formatted_data,
            "total_rows": len(data),
            "success": True,
            "formatting_applied": enable_highlighting,
            "cache_info": {
                "cached": False,
                "cache_enabled": use_cache
            }
        }
        
        response = NaturalLanguageSearchResponse(**response_data)
        
        # 5. 캐시 저장 (백그라운드)
        if use_cache:
            cache_context = {
                "context": request_data.context,
                "auth_info": {k: v for k, v in auth_info.items() if k != "token"},
                "limit": request_data.limit
            }
            background_tasks.add_task(
                _cache_search_result,
                request_data.query,
                response_data,
                cache_context,
                request_data.options.model_dump(),
                int(execution_time)
            )
        
        # 6. 백그라운드에서 메트릭 저장
        background_tasks.add_task(
            _log_search_metrics,
            request_id,
            request_data.query,
            response.execution.strategy_used,
            response.total_rows,
            (datetime.now() - start_time).total_seconds()
        )
        
        return response
        
    except HTTPException:
        raise
    except ValidationError as ve:
        logger.error(f"❌ 입력 검증 실패 [{request_id}]: {ve}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"입력 데이터 검증 실패: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"❌ 검색 실패 [{request_id}]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"내부 서버 오류: {str(e)}"
        )


@router.get(
    "/strategies",
    response_model=Dict[str, Any],
    summary="검색 전략 목록",
    description="사용 가능한 자연어 검색 전략들과 각각의 특징을 반환합니다."
)
async def get_search_strategies() -> Dict[str, Any]:
    """검색 전략 목록 조회"""
    
    strategies = {
        "llm_first": {
            "name": "LLM 우선",
            "description": "LLM을 우선 사용하고, 실패시 규칙 기반으로 Fallback",
            "accuracy": "높음",
            "speed": "중간",
            "cost": "중간",
            "recommended_for": ["복잡한 쿼리", "높은 정확도가 필요한 경우", "일반적인 사용"]
        },
        "rule_first": {
            "name": "규칙 우선",
            "description": "규칙 기반을 우선 사용하고, 실패시 LLM으로 Fallback",
            "accuracy": "중간",
            "speed": "빠름",
            "cost": "낮음",
            "recommended_for": ["간단한 쿼리", "빠른 응답이 필요한 경우", "정형화된 패턴"]
        },
        "hybrid": {
            "name": "하이브리드",
            "description": "LLM과 규칙 기반을 병렬 실행 후 최적 결과 선택",
            "accuracy": "최고",
            "speed": "느림",
            "cost": "높음",
            "recommended_for": ["중요한 쿼리", "최고 품질이 필요한 경우", "정확도 우선"]
        },
        "llm_only": {
            "name": "LLM 전용",
            "description": "LLM만 사용, Fallback 없음",
            "accuracy": "높음",
            "speed": "중간",
            "cost": "중간",
            "recommended_for": ["창의적 쿼리", "LLM 성능 테스트", "새로운 패턴 탐색"]
        },
        "rule_only": {
            "name": "규칙 전용",
            "description": "규칙 기반만 사용, LLM 사용 안함",
            "accuracy": "낮음",
            "speed": "최고",
            "cost": "없음",
            "recommended_for": ["대량 배치 처리", "비용 최적화", "정해진 패턴만"]
        }
    }
    
    return {
        "strategies": strategies,
        "default": "llm_first",
        "total_count": len(strategies),
        "recommendation": {
            "general_use": "llm_first",
            "high_performance": "rule_first",
            "best_quality": "hybrid",
            "cost_effective": "rule_only"
        }
    }


@router.get(
    "/health",
    response_model=Dict[str, Any],
    summary="검색 서비스 상태",
    description="자연어 검색 서비스의 상태와 의존성을 확인합니다."
)
async def search_health_check() -> Dict[str, Any]:
    """검색 서비스 헬스체크"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "natural_language_search",
        "version": "2.0.0",
        "components": {}
    }
    
    try:
        # LCEL 파이프라인 상태 확인
        try:
            test_request = EnhancedSQLGenerationRequest(
                query="테스트",
                strategy=ExecutionStrategy.RULE_ONLY,
                timeout_seconds=5.0
            )
            await lcel_sql_pipeline.generate_sql(test_request)
            health_status["components"]["lcel_pipeline"] = "healthy"
        except Exception as e:
            health_status["components"]["lcel_pipeline"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # 데이터베이스 연결 상태 확인
        try:
            await read_only_db_manager.execute_query_with_limit("SELECT 1", {}, limit=1)
            health_status["components"]["database"] = "healthy"
        except Exception as e:
            health_status["components"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # WebSocket 관리자 상태
        health_status["components"]["websocket_manager"] = {
            "status": "healthy",
            "active_connections": len(websocket_manager.active_connections)
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"헬스체크 중 오류: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# WebSocket 엔드포인트
@router.websocket("/stream")
async def websocket_search_stream(
    websocket: WebSocket,
    client_id: Annotated[str, Query(description="클라이언트 고유 ID")] = None
):
    """실시간 검색 스트리밍 WebSocket"""
    
    if not client_id:
        client_id = f"client_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    await websocket_manager.connect(websocket, client_id, {
        "connected_at": datetime.now().isoformat(),
        "type": "search_stream"
    })
    
    try:
        # 연결 성공 메시지 전송
        await websocket_manager.send_personal_message({
            "event_type": "connection_established",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat(),
            "message": "실시간 검색 스트림에 연결되었습니다."
        }, client_id)
        
        while True:
            try:
                # 클라이언트에서 메시지 수신
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "search_request":
                    # 검색 요청 처리
                    await _handle_streaming_search(message, client_id)
                elif message.get("type") == "ping":
                    # 연결 상태 확인
                    await websocket_manager.send_personal_message({
                        "event_type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, client_id)
                else:
                    # 알 수 없는 메시지 타입
                    await websocket_manager.send_personal_message({
                        "event_type": "error",
                        "message": f"알 수 없는 메시지 타입: {message.get('type')}",
                        "timestamp": datetime.now().isoformat()
                    }, client_id)
                    
            except json.JSONDecodeError:
                await websocket_manager.send_personal_message({
                    "event_type": "error",
                    "message": "잘못된 JSON 형식입니다.",
                    "timestamp": datetime.now().isoformat()
                }, client_id)
            except Exception as e:
                logger.error(f"WebSocket 메시지 처리 오류 ({client_id}): {e}")
                await websocket_manager.send_personal_message({
                    "event_type": "error",
                    "message": f"메시지 처리 중 오류: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }, client_id)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket 클라이언트 연결 해제: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket 연결 오류 ({client_id}): {e}")
    finally:
        websocket_manager.disconnect(client_id)


# 헬퍼 함수들
async def _handle_streaming_search(message: Dict[str, Any], client_id: str):
    """스트리밍 검색 처리"""
    try:
        query = message.get("query", "")
        if not query:
            await websocket_manager.send_personal_message({
                "event_type": "error",
                "message": "검색 쿼리가 필요합니다.",
                "timestamp": datetime.now().isoformat()
            }, client_id)
            return
        
        # 검색 시작 알림
        await websocket_manager.send_personal_message({
            "event_type": "search_started",
            "query": query,
            "timestamp": datetime.now().isoformat()
        }, client_id)
        
        # LCEL 파이프라인 스트리밍 실행
        options = message.get("options", {})
        request = EnhancedSQLGenerationRequest(
            query=query,
            context=message.get("context", {}),
            strategy=ExecutionStrategy(options.get("strategy", "llm_first")),
            enable_streaming=True,
            timeout_seconds=options.get("timeout_seconds", 30.0)
        )
        
        # 스트리밍 이벤트 처리
        async for event in lcel_sql_pipeline.generate_sql_streaming(request):
            streaming_event = StreamingSearchEvent(
                event_type=event.get("type", "update"),
                data=event,
                progress=event.get("progress")
            )
            
            await websocket_manager.send_personal_message(
                streaming_event.model_dump(mode='json'),
                client_id
            )
        
        # 검색 완료 알림
        await websocket_manager.send_personal_message({
            "event_type": "search_completed",
            "query": query,
            "timestamp": datetime.now().isoformat()
        }, client_id)
        
    except Exception as e:
        logger.error(f"스트리밍 검색 처리 오류: {e}")
        await websocket_manager.send_personal_message({
            "event_type": "error",
            "message": f"검색 처리 중 오류: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, client_id)


async def _cache_search_result(
    query: str,
    result: Dict[str, Any],
    context: Dict[str, Any],
    options: Dict[str, Any],
    execution_time_ms: int
):
    """검색 결과 캐시 저장 (백그라운드 작업)"""
    try:
        success = await search_cache_service.cache_search_result(
            query=query,
            result=result,
            context=context,
            options=options,
            execution_time_ms=execution_time_ms,
            ttl_minutes=5  # 5분 TTL
        )
        
        if success:
            logger.debug(f"✅ 검색 결과 캐시 저장 성공: {query[:50]}...")
        else:
            logger.warning(f"❌ 검색 결과 캐시 저장 실패: {query[:50]}...")
            
    except Exception as e:
        logger.error(f"캐시 저장 백그라운드 작업 실패: {e}")


async def _log_search_metrics(
    request_id: str,
    query: str,
    strategy: str,
    result_count: int,
    duration_seconds: float
):
    """검색 메트릭 로깅 (백그라운드 작업)"""
    try:
        metrics = {
            "request_id": request_id,
            "query_length": len(query),
            "strategy_used": strategy,
            "result_count": result_count,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now().isoformat()
        }
        
        # 실제 메트릭 저장소에 저장 (예: 데이터베이스, 로그 파일 등)
        logger.info(f"📊 검색 메트릭: {metrics}")
        
    except Exception as e:
        logger.error(f"메트릭 로깅 실패: {e}")


# 캐시 관련 추가 엔드포인트들
@router.get(
    "/cache/statistics",
    response_model=Dict[str, Any],
    summary="캐시 통계",
    description="PostgreSQL 기반 검색 캐시의 상세 통계를 반환합니다."
)
async def get_cache_statistics() -> Dict[str, Any]:
    """캐시 통계 조회"""
    try:
        stats = await search_cache_service.get_cache_statistics()
        logger.info("캐시 통계 조회 완료")
        return stats
    except Exception as e:
        logger.error(f"캐시 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐시 통계 조회 중 오류: {str(e)}"
        )


@router.get(
    "/popular-queries",
    response_model=List[Dict[str, Any]],
    summary="인기 검색어",
    description="사용자들이 자주 검색하는 인기 검색어 목록을 반환합니다."
)
async def get_popular_queries(
    limit: Annotated[int, Query(ge=1, le=100, description="반환할 항목 수")] = 20,
    min_searches: Annotated[int, Query(ge=1, description="최소 검색 수")] = 2,
    days: Annotated[int, Query(ge=1, le=365, description="분석 기간 (일)")] = 30
) -> List[Dict[str, Any]]:
    """인기 검색어 조회"""
    try:
        popular_queries = await search_cache_service.get_popular_queries(
            limit=limit,
            min_searches=min_searches,
            days=days
        )
        
        logger.info(f"인기 검색어 조회: {len(popular_queries)}개 반환")
        return popular_queries
        
    except Exception as e:
        logger.error(f"인기 검색어 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인기 검색어 조회 중 오류: {str(e)}"
        )


@router.get(
    "/cache/suggest",
    response_model=List[Dict[str, Any]],
    summary="검색어 자동완성",
    description="입력한 검색어와 유사한 캐시된 검색어들을 제안합니다."
)
async def search_suggestion(
    q: Annotated[str, Query(..., min_length=1, max_length=100, description="검색할 용어")],
    limit: Annotated[int, Query(ge=1, le=20, description="반환할 제안 수")] = 10
) -> List[Dict[str, Any]]:
    """검색어 자동완성"""
    try:
        suggestions = await search_cache_service.search_cached_queries(
            search_term=q,
            limit=limit
        )
        
        logger.debug(f"검색어 자동완성: '{q}' → {len(suggestions)}개 제안")
        return suggestions
        
    except Exception as e:
        logger.error(f"검색어 자동완성 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"자동완성 조회 중 오류: {str(e)}"
        )


@router.delete(
    "/cache/invalidate",
    response_model=Dict[str, Any],
    summary="캐시 무효화",
    description="특정 패턴이나 전체 검색 캐시를 무효화합니다."
)
async def invalidate_cache(
    query: Annotated[Optional[str], Query(description="특정 쿼리 (정확 매치)")] = None,
    pattern: Annotated[Optional[str], Query(description="쿼리 패턴 (부분 매치)")] = None,
    all_cache: Annotated[bool, Query(description="전체 캐시 무효화")] = False
) -> Dict[str, Any]:
    """캐시 무효화"""
    try:
        if all_cache:
            deleted_count = await search_cache_service.invalidate_cache()
        elif query:
            deleted_count = await search_cache_service.invalidate_cache(query=query)
        elif pattern:
            deleted_count = await search_cache_service.invalidate_cache(pattern=pattern)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="query, pattern, 또는 all_cache=true 중 하나를 지정해야 합니다"
            )
        
        logger.info(f"캐시 무효화 완료: {deleted_count}개 항목 삭제")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개의 캐시 항목이 삭제되었습니다.",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"캐시 무효화 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐시 무효화 중 오류: {str(e)}"
        )


@router.post(
    "/cache/cleanup",
    response_model=Dict[str, Any],
    summary="만료된 캐시 정리",
    description="만료된 캐시 항목들을 정리합니다. (일반적으로 자동 실행됨)"
)
async def cleanup_expired_cache() -> Dict[str, Any]:
    """만료된 캐시 정리"""
    try:
        cleaned_count = await search_cache_service.cleanup_expired_cache()
        
        logger.info(f"만료된 캐시 정리 완료: {cleaned_count}개 확인")
        
        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "message": f"만료된 캐시 정리 완료 ({cleaned_count}개 확인됨)",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"캐시 정리 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캐시 정리 중 오류: {str(e)}"
        )


# 라우터에 추가 메타데이터 설정
router.tags = ["Natural Language Search"]
router.responses.update({
    200: {"description": "성공"},
    400: {"description": "잘못된 요청"},
    401: {"description": "인증 실패"},
    403: {"description": "권한 없음"},
    404: {"description": "리소스 없음"},
    422: {"description": "입력 검증 실패"},
    500: {"description": "서버 오류"}
})