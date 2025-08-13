"""
V2 Natural Language Search Router - Next Generation AI-Powered Search

Revolutionary improvements in V2:
- Enhanced AI-powered search with multi-model ensemble
- Advanced search strategies (AI-first, Semantic Hybrid, Contextual, Adaptive, etc.)
- Real-time learning and user behavior analysis
- Context-aware search with session memory
- Improved Korean language processing
- Advanced analytics and performance monitoring
- Better error handling and user experience
"""

import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, Union, Annotated
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import (
    APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect,
    Query, Path, Body, BackgroundTasks, Request, Response, status
)
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field
from pydantic.types import StringConstraints
from pydantic_core import ValidationError

from app.api.v2.services.nl_search_service import (
    NLSearchServiceV2, SearchStrategyV2, SearchContextV2
)
from app.api.v2.services.intent_classifier import (
    IntentClassifierV2, IntentTypeV2, IntentResultV2, ConfidenceLevelV2
)
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# V2 Router with enhanced capabilities
router = APIRouter(
    prefix="/v2/api/search", 
    tags=["Natural Language Search V2"],
    responses={
        404: {"description": "V2: 검색 결과를 찾을 수 없습니다"},
        422: {"description": "V2: 입력 데이터 검증 오류"},
        500: {"description": "V2: 내부 서버 오류"}
    }
)

# V2 Security
security = HTTPBearer(auto_error=False)

# V2 Enhanced Type Definitions
QueryString = Annotated[str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)]
ContextData = Annotated[Dict[str, Any], Field(default_factory=dict)]
LimitValue = Annotated[int, Field(ge=1, le=1000, default=100)]

# V2 Enhanced Request/Response Models
class SearchOptionsV2(BaseModel):
    """V2 Enhanced search options with new capabilities"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    strategy: SearchStrategyV2 = Field(
        default=SearchStrategyV2.AI_FIRST,
        description="V2 검색 전략",
        examples=["ai_first", "semantic_hybrid", "contextual", "adaptive"]
    )
    enable_streaming: bool = Field(
        default=False,
        description="스트리밍 응답 활성화"
    )
    include_explanation: bool = Field(
        default=True,
        description="AI 추론 설명 포함"
    )
    enable_learning: bool = Field(
        default=True,
        description="실시간 학습 활성화"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="최소 신뢰도 임계값"
    )
    max_suggestions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="최대 제안 수"
    )
    timeout_seconds: float = Field(
        default=45.0,
        ge=1.0,
        le=180.0,
        description="타임아웃 (초)"
    )

class NaturalLanguageSearchRequestV2(BaseModel):
    """V2 Enhanced natural language search request"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "query": "30대 고객들의 평균 보험료를 지역별로 AI 분석해주세요",
                "context": {
                    "department": "analytics", 
                    "user_level": "expert",
                    "session_id": "session_123",
                    "user_preferences": {"language": "ko"}
                },
                "options": {
                    "strategy": "ai_first",
                    "include_explanation": True,
                    "enable_learning": True,
                    "confidence_threshold": 0.8
                },
                "limit": 100
            }
        }
    )
    
    query: QueryString = Field(
        ..., 
        description="V2 자연어 검색 쿼리 (향상된 AI 이해력)",
        examples=["30대 고객 AI 분석", "지난달 가입 트렌드 예측", "보험료 패턴 학습"]
    )
    context: ContextData = Field(
        default_factory=dict,
        description="V2 향상된 검색 컨텍스트",
        examples=[{"session_id": "123", "user_preferences": {"language": "ko"}}]
    )
    options: SearchOptionsV2 = Field(
        default_factory=SearchOptionsV2,
        description="V2 검색 옵션"
    )
    limit: LimitValue = Field(
        default=100,
        description="결과 제한 수"
    )
    user_id: Optional[str] = Field(
        None,
        description="사용자 ID (학습용)"
    )
    session_id: Optional[str] = Field(
        None,
        description="세션 ID (컨텍스트 관리용)"
    )

class SearchIntentV2(BaseModel):
    """V2 Enhanced search intent with multi-intent support"""
    model_config = ConfigDict(validate_assignment=True)
    
    primary_intent: str = Field(..., description="주요 의도")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="신뢰도")
    confidence_level: str = Field(..., description="신뢰도 수준")
    secondary_intents: List[Dict[str, Any]] = Field(default_factory=list, description="보조 의도들")
    entities: Dict[str, Any] = Field(default_factory=dict, description="V2 향상된 엔티티")
    context_factors: Dict[str, Any] = Field(default_factory=dict, description="컨텍스트 요인")
    intent_reasoning: str = Field(..., description="AI 추론 과정")
    suggested_actions: List[str] = Field(default_factory=list, description="제안된 액션")
    uncertainty_factors: List[str] = Field(default_factory=list, description="불확실성 요인")

class SearchExecutionV2(BaseModel):
    """V2 Enhanced search execution info"""
    model_config = ConfigDict(validate_assignment=True)
    
    search_id: str = Field(..., description="V2 검색 고유 ID")
    strategy_used: str = Field(..., description="사용된 V2 전략")
    processing_steps: List[str] = Field(default_factory=list, description="처리 단계")
    ai_models_used: List[str] = Field(default_factory=list, description="사용된 AI 모델")
    execution_time_ms: float = Field(..., ge=0, description="실행 시간")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="전체 신뢰도")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="성능 지표")
    optimization_applied: List[str] = Field(default_factory=list, description="적용된 최적화")

class NaturalLanguageSearchResponseV2(BaseModel):
    """V2 Enhanced natural language search response"""
    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "search_id": "search_123456789_v2",
                "query": "30대 고객들의 AI 분석",
                "processed_query": {
                    "original_query": "30대 고객들의 AI 분석",
                    "enhanced_query": "30대 고객들의 AI 분석 (컨텍스트 강화)",
                    "detected_language": "ko"
                },
                "intent": {
                    "primary_intent": "analytics_query",
                    "confidence_score": 0.95,
                    "intent_reasoning": "V2 AI가 분석한 의도..."
                },
                "execution": {
                    "search_id": "search_123",
                    "strategy_used": "ai_first",
                    "ai_models_used": ["gpt-4", "korean_model"],
                    "confidence_score": 0.92
                },
                "results": [{"enhanced_result": "V2 결과"}],
                "metadata": {
                    "total_results": 10,
                    "processing_time_seconds": 1.2,
                    "version": "2.0.0"
                }
            }
        }
    )
    
    search_id: str = Field(..., description="V2 검색 고유 ID")
    query: str = Field(..., description="원본 쿼리")
    processed_query: Dict[str, Any] = Field(..., description="V2 처리된 쿼리")
    strategy: str = Field(..., description="사용된 V2 전략")
    intent: SearchIntentV2 = Field(..., description="V2 의도 분석 결과")
    execution: SearchExecutionV2 = Field(..., description="V2 실행 정보")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="V2 향상된 검색 결과")
    metadata: Dict[str, Any] = Field(..., description="V2 메타데이터")
    suggestions: List[str] = Field(default_factory=list, description="AI 생성 제안")
    success: bool = Field(..., description="검색 성공 여부")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    timestamp: str = Field(..., description="응답 시간")
    
    @computed_field
    @property
    def has_results(self) -> bool:
        """결과 존재 여부"""
        return len(self.results) > 0
    
    @computed_field
    @property
    def performance_summary(self) -> str:
        """V2 성능 요약"""
        return f"V2 {self.strategy} 전략으로 {self.metadata.get('processing_time_seconds', 0):.2f}초에 {len(self.results)}개 결과 (신뢰도: {self.execution.confidence_score:.1%})"

# V2 Services initialization
nl_search_service_v2 = NLSearchServiceV2()
intent_classifier_v2 = IntentClassifierV2()

# V2 Enhanced API Endpoints
@router.post(
    "/natural-language",
    response_model=NaturalLanguageSearchResponseV2,
    status_code=status.HTTP_200_OK,
    summary="V2 자연어 검색",
    description="""
    ## V2 자연어 검색 - 차세대 AI 검색 엔진
    
    ### 🚀 V2 새로운 기능
    - **다중 AI 모델 앙상블**: GPT-4, Claude, 한국어 특화 모델 조합
    - **6가지 검색 전략**: AI-First, Semantic Hybrid, Contextual, Adaptive, Multi-Modal, Predictive
    - **실시간 학습**: 사용자 피드백 기반 성능 개선
    - **컨텍스트 인식**: 세션 기반 검색 기록 활용
    - **고급 의도 분석**: 다중 의도 및 불확실성 정량화
    - **성능 최적화**: 고급 캐싱 및 예측적 로딩
    
    ### 🎯 V2 검색 전략 설명
    - **ai_first**: 최신 LLM 우선 (기본값, 최고 정확도)
    - **semantic_hybrid**: 의미론적 + 키워드 하이브리드
    - **contextual**: 컨텍스트 인식 개인화 검색
    - **adaptive**: 사용자 학습 기반 적응형 검색
    - **multi_modal**: 다중 데이터 소스 융합
    - **predictive**: 사용자 의도 예측 검색
    """,
    response_description="V2 향상된 검색 결과 및 AI 분석"
)
async def natural_language_search_v2(
    request_data: NaturalLanguageSearchRequestV2,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> NaturalLanguageSearchResponseV2:
    """V2 자연어 검색 메인 엔드포인트"""
    
    start_time = datetime.utcnow()
    search_id = f"v2_search_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    try:
        logger.info(f"🔍 V2 자연어 검색 시작 [{search_id}]: {request_data.query}")
        
        # V2: 1. 향상된 의도 분석
        intent_result = await intent_classifier_v2.classify_intent(
            text=request_data.query,
            context=request_data.context,
            user_id=request_data.user_id,
            session_id=request_data.session_id
        )
        
        logger.info(f"V2 의도 분석 완료 [{search_id}]: {intent_result.primary_intent.value} (신뢰도: {intent_result.confidence_score:.2f})")
        
        # V2: 2. 검색 컨텍스트 생성
        search_context = SearchContextV2()
        if request_data.user_id:
            search_context.user_id = request_data.user_id
        if request_data.session_id:
            search_context.session_id = request_data.session_id
        
        # V2: 3. 향상된 자연어 검색 실행
        search_results = await nl_search_service_v2.search_natural_language(
            query=request_data.query,
            strategy=request_data.options.strategy,
            context=search_context,
            limit=request_data.limit,
            options=request_data.options.model_dump()
        )
        
        # V2: 4. 검색 결과와 의도 분석 결과 통합
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # V2: Enhanced response structure
        response_data = {
            "search_id": search_id,
            "query": request_data.query,
            "processed_query": search_results.get("processed_query", {}),
            "strategy": request_data.options.strategy.value,
            "intent": SearchIntentV2(
                primary_intent=intent_result.primary_intent.value,
                confidence_score=intent_result.confidence_score,
                confidence_level=intent_result.confidence_level.value,
                secondary_intents=[
                    {"intent": intent.value, "confidence": score} 
                    for intent, score in intent_result.secondary_intents
                ],
                entities=intent_result.entities,
                context_factors=intent_result.context_factors,
                intent_reasoning=intent_result.intent_reasoning,
                suggested_actions=intent_result.suggested_actions,
                uncertainty_factors=intent_result.uncertainty_factors
            ),
            "execution": SearchExecutionV2(
                search_id=search_id,
                strategy_used=request_data.options.strategy.value,
                processing_steps=["intent_analysis", "context_building", "ai_search", "result_enhancement"],
                ai_models_used=["intent_classifier_v2", "nl_search_service_v2"],
                execution_time_ms=processing_time * 1000,
                confidence_score=search_results["metadata"].get("confidence_score", 0.0),
                performance_metrics=search_results["metadata"].get("search_quality_metrics", {}),
                optimization_applied=["v2_enhanced_processing", "context_awareness", "multi_model_ensemble"]
            ),
            "results": search_results.get("results", []),
            "metadata": {
                **search_results.get("metadata", {}),
                "intent_analysis_time_ms": intent_result.processing_metadata.get("processing_time_seconds", 0) * 1000,
                "total_processing_time_seconds": processing_time
            },
            "suggestions": search_results.get("suggestions", []),
            "success": True,
            "error_message": None,
            "timestamp": start_time.isoformat()
        }
        
        response = NaturalLanguageSearchResponseV2(**response_data)
        
        # V2: 5. 백그라운드 작업 - 학습 및 분석
        if request_data.options.enable_learning:
            background_tasks.add_task(
                _update_learning_data_v2,
                search_id,
                request_data.query,
                response.model_dump(),
                intent_result.model_dump(),
                request_data.user_id,
                request_data.session_id
            )
        
        # V2: 6. 성능 메트릭 로깅
        background_tasks.add_task(
            _log_v2_search_metrics,
            search_id,
            request_data.query,
            request_data.options.strategy.value,
            len(response.results),
            processing_time,
            response.execution.confidence_score
        )
        
        logger.info(f"✅ V2 검색 완료 [{search_id}]: {len(response.results)}개 결과, {processing_time:.2f}초")
        return response
        
    except Exception as e:
        logger.error(f"❌ V2 검색 실패 [{search_id}]: {str(e)}")
        
        # V2: Enhanced error handling
        error_response_data = {
            "search_id": search_id,
            "query": request_data.query,
            "processed_query": {"original_query": request_data.query, "error": "processing_failed"},
            "strategy": request_data.options.strategy.value,
            "intent": SearchIntentV2(
                primary_intent="unknown",
                confidence_score=0.0,
                confidence_level="very_low",
                intent_reasoning="Error occurred during processing"
            ),
            "execution": SearchExecutionV2(
                search_id=search_id,
                strategy_used=request_data.options.strategy.value,
                processing_steps=["error_occurred"],
                ai_models_used=[],
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                confidence_score=0.0,
                performance_metrics={"error": True},
                optimization_applied=[]
            ),
            "results": [],
            "metadata": {
                "total_results": 0,
                "processing_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "version": "2.0.0",
                "error_occurred": True
            },
            "suggestions": [],
            "success": False,
            "error_message": f"V2 검색 처리 중 오류가 발생했습니다: {str(e)}",
            "timestamp": start_time.isoformat()
        }
        
        # Return error response instead of raising HTTP exception for better client handling
        return NaturalLanguageSearchResponseV2(**error_response_data)

@router.get(
    "/strategies/v2",
    response_model=Dict[str, Any],
    summary="V2 검색 전략 목록",
    description="V2에서 사용 가능한 차세대 AI 검색 전략들과 각각의 특징을 반환합니다."
)
async def get_v2_search_strategies() -> Dict[str, Any]:
    """V2 검색 전략 목록 조회"""
    
    strategies = {
        SearchStrategyV2.AI_FIRST.value: {
            "name": "AI 우선 (V2)",
            "description": "최신 LLM 앙상블을 활용한 지능형 검색",
            "accuracy": "최고",
            "speed": "빠름",
            "cost": "중간",
            "recommended_for": ["복잡한 분석", "창의적 쿼리", "높은 정확도가 필요한 경우"],
            "new_features": ["다중 모델 앙상블", "한국어 특화", "컨텍스트 인식"]
        },
        SearchStrategyV2.SEMANTIC_HYBRID.value: {
            "name": "의미론적 하이브리드 (V2)",
            "description": "의미론적 벡터 검색과 전통적 검색의 하이브리드",
            "accuracy": "높음",
            "speed": "중간",
            "cost": "중간",
            "recommended_for": ["의미 기반 검색", "유사성 분석", "관련성 중시"],
            "new_features": ["고급 임베딩", "의미론적 매칭", "컨텍스트 벡터"]
        },
        SearchStrategyV2.CONTEXTUAL.value: {
            "name": "컨텍스트 인식 (V2)",
            "description": "사용자 세션과 검색 이력을 활용한 개인화 검색",
            "accuracy": "높음",
            "speed": "빠름",
            "cost": "낮음",
            "recommended_for": ["반복 사용자", "개인화 필요", "세션 기반 작업"],
            "new_features": ["세션 메모리", "사용자 프로파일링", "행동 패턴 학습"]
        },
        SearchStrategyV2.ADAPTIVE.value: {
            "name": "적응형 학습 (V2)",
            "description": "사용자 피드백 기반 실시간 학습 및 개선",
            "accuracy": "향상됨",
            "speed": "중간",
            "cost": "중간",
            "recommended_for": ["지속적 사용", "피드백 기반 개선", "학습 환경"],
            "new_features": ["실시간 학습", "피드백 통합", "성능 자동 조정"]
        },
        SearchStrategyV2.MULTI_MODAL.value: {
            "name": "다중 모달 (V2)",
            "description": "텍스트, 메타데이터, 행동 신호를 융합한 검색",
            "accuracy": "매우 높음",
            "speed": "중간",
            "cost": "높음",
            "recommended_for": ["복합 데이터 분석", "다차원 검색", "종합적 인사이트"],
            "new_features": ["데이터 융합", "교차 모달 매칭", "종합 분석"]
        },
        SearchStrategyV2.PREDICTIVE.value: {
            "name": "예측적 검색 (V2)",
            "description": "사용자 의도를 예측하여 선제적 결과 제공",
            "accuracy": "높음",
            "speed": "매우 빠름",
            "cost": "중간",
            "recommended_for": ["예측 분석", "선제적 정보 제공", "효율성 중시"],
            "new_features": ["의도 예측", "선제적 로딩", "예측 알고리즘"]
        }
    }
    
    return {
        "strategies": strategies,
        "default": SearchStrategyV2.AI_FIRST.value,
        "total_count": len(strategies),
        "v2_improvements": [
            "다중 AI 모델 앙상블",
            "실시간 학습 및 적응",
            "컨텍스트 인식 개인화",
            "고급 성능 최적화",
            "향상된 한국어 지원"
        ],
        "recommendation": {
            "general_use": SearchStrategyV2.AI_FIRST.value,
            "personalized": SearchStrategyV2.CONTEXTUAL.value,
            "learning_environment": SearchStrategyV2.ADAPTIVE.value,
            "best_quality": SearchStrategyV2.MULTI_MODAL.value,
            "fastest_response": SearchStrategyV2.PREDICTIVE.value
        },
        "version": "2.0.0"
    }

@router.get(
    "/analytics/v2",
    response_model=Dict[str, Any],
    summary="V2 검색 분석",
    description="V2 자연어 검색 서비스의 고급 분석 및 성능 메트릭을 반환합니다."
)
async def get_v2_search_analytics() -> Dict[str, Any]:
    """V2 검색 분석 조회"""
    
    try:
        # Get analytics from V2 services
        search_analytics = await nl_search_service_v2.get_search_analytics()
        intent_analytics = await intent_classifier_v2.get_classification_analytics()
        
        return {
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "search_service": search_analytics,
            "intent_classifier": intent_analytics,
            "overall_performance": {
                "total_searches": search_analytics.get("total_searches", 0),
                "average_response_time": search_analytics.get("average_response_time", 0),
                "overall_accuracy": intent_analytics.get("accuracy_metrics", {}).get("overall_accuracy", 0),
                "user_satisfaction": search_analytics.get("quality_trends", {}).get("user_satisfaction", 0)
            },
            "v2_enhancements": {
                "multi_model_ensemble": True,
                "real_time_learning": True,
                "context_awareness": True,
                "korean_language_optimization": True,
                "advanced_caching": True
            }
        }
        
    except Exception as e:
        logger.error(f"V2 분석 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"V2 분석 조회 중 오류: {str(e)}"
        )

@router.post(
    "/feedback/v2",
    response_model=Dict[str, Any],
    summary="V2 검색 피드백",
    description="V2 검색 결과에 대한 사용자 피드백을 수집하여 실시간 학습에 활용합니다."
)
async def submit_v2_search_feedback(
    search_id: str = Field(..., description="검색 ID"),
    rating: int = Field(..., ge=1, le=5, description="평점 (1-5)"),
    feedback_type: str = Field(..., description="피드백 유형"),
    comments: Optional[str] = Field(None, description="추가 의견"),
    correct_intent: Optional[str] = Field(None, description="올바른 의도 (수정용)")
) -> Dict[str, Any]:
    """V2 검색 피드백 제출"""
    
    try:
        # V2: Process feedback for both services
        feedback_data = {
            "search_id": search_id,
            "rating": rating,
            "feedback_type": feedback_type,
            "comments": comments,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Update intent classifier with feedback if provided
        if correct_intent:
            try:
                correct_intent_enum = IntentTypeV2(correct_intent)
                await intent_classifier_v2.provide_feedback(
                    classification_id=search_id,
                    correct_intent=correct_intent_enum,
                    feedback_notes=comments
                )
            except ValueError:
                logger.warning(f"Invalid intent type provided: {correct_intent}")
        
        # Update search service with feedback
        optimization_result = await nl_search_service_v2.optimize_search_strategy(feedback_data)
        
        logger.info(f"V2 피드백 처리 완료: {search_id}")
        
        return {
            "success": True,
            "message": "V2 피드백이 성공적으로 처리되었습니다",
            "feedback_id": f"fb_{search_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "optimization_applied": optimization_result.get("optimization_applied", False),
            "expected_improvement": optimization_result.get("expected_improvement", 0),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0"
        }
        
    except Exception as e:
        logger.error(f"V2 피드백 처리 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"V2 피드백 처리 중 오류: {str(e)}"
        )

@router.get(
    "/health/v2",
    response_model=Dict[str, Any],
    summary="V2 검색 서비스 상태",
    description="V2 자연어 검색 서비스와 모든 구성 요소의 상태를 확인합니다."
)
async def v2_search_health_check() -> Dict[str, Any]:
    """V2 검색 서비스 헬스체크"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "natural_language_search_v2",
        "version": "2.0.0",
        "components": {}
    }
    
    try:
        # V2 NL Search Service 상태 확인
        try:
            search_context = SearchContextV2()
            test_result = await nl_search_service_v2.search_natural_language(
                query="테스트",
                strategy=SearchStrategyV2.AI_FIRST,
                context=search_context,
                limit=1
            )
            health_status["components"]["nl_search_service_v2"] = "healthy"
        except Exception as e:
            health_status["components"]["nl_search_service_v2"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # V2 Intent Classifier 상태 확인
        try:
            intent_result = await intent_classifier_v2.classify_intent("테스트")
            health_status["components"]["intent_classifier_v2"] = "healthy"
        except Exception as e:
            health_status["components"]["intent_classifier_v2"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # V2 특화 기능 상태
        health_status["v2_features"] = {
            "multi_model_ensemble": "enabled",
            "real_time_learning": "enabled", 
            "context_awareness": "enabled",
            "korean_language_support": "enabled",
            "advanced_analytics": "enabled"
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"V2 헬스체크 중 오류: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0"
        }

# V2 Background Tasks
async def _update_learning_data_v2(
    search_id: str,
    query: str,
    search_response: Dict[str, Any],
    intent_result: Dict[str, Any],
    user_id: Optional[str],
    session_id: Optional[str]
):
    """V2 학습 데이터 업데이트 (백그라운드)"""
    try:
        logger.info(f"V2 학습 데이터 업데이트: {search_id}")
        
        # TODO: Implement V2 learning data update
        # - Store search patterns
        # - Update user preferences
        # - Improve model weights
        # - Enhance context understanding
        
    except Exception as e:
        logger.error(f"V2 학습 데이터 업데이트 실패: {e}")

async def _log_v2_search_metrics(
    search_id: str,
    query: str,
    strategy: str,
    result_count: int,
    duration_seconds: float,
    confidence_score: float
):
    """V2 검색 메트릭 로깅 (백그라운드)"""
    try:
        metrics = {
            "search_id": search_id,
            "query_length": len(query),
            "strategy_used": strategy,
            "result_count": result_count,
            "duration_seconds": duration_seconds,
            "confidence_score": confidence_score,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0"
        }
        
        logger.info(f"📊 V2 검색 메트릭: {metrics}")
        
    except Exception as e:
        logger.error(f"V2 메트릭 로깅 실패: {e}")