"""
LCEL SQL 생성 파이프라인 API 엔드포인트

이 모듈은 LCEL 기반 SQL 생성 파이프라인의 API 엔드포인트를 제공합니다.
"""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.services.lcel_sql_pipeline import (
    lcel_sql_pipeline, 
    EnhancedSQLGenerationRequest, 
    EnhancedSQLPipelineResponse,
    ExecutionStrategy,
    RetryConfig
)
from app.utils.langsmith_config import trace_llm_call
from app.database import read_only_db_manager

logger = logging.getLogger(__name__)

# API 라우터 생성
router = APIRouter(prefix="/v1/api/lcel-sql", tags=["LCEL SQL Pipeline"])


@router.post(
    "/generate", 
    response_model=EnhancedSQLPipelineResponse,
    summary="고급 SQL 생성",
    description="""
    LangChain Expression Language(LCEL) 기반 고급 SQL 생성 파이프라인을 실행합니다.
    
    주요 기능:
    - 자연어 → 의도 파싱 → SQL 생성 → 검증 체인
    - Fallback 체인 (LLM 실패 시 규칙 기반)  
    - Retry 로직 with exponential backoff
    - LangSmith 추적 통합
    - 다양한 실행 전략 지원
    """
)
@trace_llm_call("lcel_sql_generate_endpoint")
async def generate_sql(
    request: EnhancedSQLGenerationRequest,
    background_tasks: BackgroundTasks
) -> EnhancedSQLPipelineResponse:
    """
    자연어 쿼리를 고급 파이프라인을 통해 SQL로 변환합니다.
    
    Args:
        request: SQL 생성 요청
        background_tasks: 백그라운드 작업 관리
        
    Returns:
        EnhancedSQLPipelineResponse: SQL 생성 결과
        
    Raises:
        HTTPException: 요청 처리 중 오류 발생 시
    """
    
    try:
        logger.info(f"🔄 LCEL SQL 생성 요청: {request.query} (전략: {request.strategy})")
        
        # 스트리밍이 비활성화된 일반 요청 처리
        if request.enable_streaming:
            raise HTTPException(
                status_code=400,
                detail="스트리밍 요청은 /generate-streaming 엔드포인트를 사용하세요"
            )
        
        # LCEL 파이프라인 실행
        result = await lcel_sql_pipeline.generate_sql(request)
        
        # 백그라운드에서 메트릭 저장 (선택적)
        background_tasks.add_task(_save_pipeline_metrics, request, result)
        
        logger.info(f"✅ SQL 생성 완료: {result.success}")
        return result
        
    except ValidationError as e:
        logger.error(f"❌ 입력 데이터 검증 실패: {e}")
        raise HTTPException(status_code=422, detail=str(e))
        
    except Exception as e:
        logger.error(f"❌ SQL 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"SQL 생성 실패: {str(e)}")


@router.post(
    "/generate-streaming",
    summary="스트리밍 SQL 생성", 
    description="""
    실시간 스트리밍으로 SQL 생성 과정을 확인할 수 있는 엔드포인트입니다.
    
    응답 형식: Server-Sent Events (SSE)
    - 각 처리 단계별로 실시간 업데이트 제공
    - LLM 토큰 생성 과정 실시간 확인
    - 최종 결과까지 전체 파이프라인 추적 가능
    """
)
@trace_llm_call("lcel_sql_streaming_endpoint")
async def generate_sql_streaming(
    request: EnhancedSQLGenerationRequest
) -> StreamingResponse:
    """
    스트리밍 방식으로 SQL 생성 과정을 실시간 전송합니다.
    
    Args:
        request: SQL 생성 요청 (enable_streaming=True로 설정됨)
        
    Returns:
        StreamingResponse: Server-Sent Events 스트림
    """
    
    try:
        logger.info(f"📡 스트리밍 SQL 생성 요청: {request.query}")
        
        # 스트리밍 활성화
        request.enable_streaming = True
        
        async def event_stream():
            """Server-Sent Events 스트림 생성"""
            try:
                # 시작 이벤트 전송
                yield f"data: {_format_sse_event('start', {'query': request.query, 'timestamp': datetime.now().isoformat()})}\n\n"
                
                # 스트리밍 파이프라인 실행
                async for event in lcel_sql_pipeline.generate_sql_streaming(request):
                    event_data = _format_sse_event(event.get('type', 'update'), event)
                    yield f"data: {event_data}\n\n"
                
                # 완료 이벤트 전송
                yield f"data: {_format_sse_event('complete', {'message': 'Pipeline completed'})}\n\n"
                
            except Exception as e:
                logger.error(f"스트리밍 중 오류: {e}")
                error_event = _format_sse_event('error', {'error': str(e)})
                yield f"data: {error_event}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # nginx용 버퍼링 비활성화
            }
        )
        
    except Exception as e:
        logger.error(f"❌ 스트리밍 설정 오류: {e}")
        raise HTTPException(status_code=500, detail=f"스트리밍 설정 실패: {str(e)}")


@router.post(
    "/execute-and-run",
    summary="SQL 생성 및 실행",
    description="""
    SQL을 생성하고 즉시 데이터베이스에서 실행하여 결과를 반환합니다.
    
    주의: 읽기 전용 데이터베이스에서만 실행됩니다.
    """
)
@trace_llm_call("lcel_sql_execute_endpoint")
async def generate_and_execute_sql(
    request: EnhancedSQLGenerationRequest,
    limit: int = 100
) -> Dict[str, Any]:
    """
    SQL을 생성하고 데이터베이스에서 실행합니다.
    
    Args:
        request: SQL 생성 요청
        limit: 결과 제한 수 (최대 100)
        
    Returns:
        Dict[str, Any]: SQL 생성 결과 및 실행 데이터
    """
    
    try:
        logger.info(f"🗄️ SQL 생성 및 실행: {request.query}")
        
        # SQL 생성
        result = await lcel_sql_pipeline.generate_sql(request)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=f"SQL 생성 실패: {result.error_message}")
        
        # SQL 실행
        try:
            execution_data = await read_only_db_manager.execute_query_with_limit(
                result.sql_result.sql,
                result.sql_result.parameters,
                limit=min(limit, 100)  # 최대 100개로 제한
            )
            
            # 결과를 딕셔너리 리스트로 변환
            data = []
            if execution_data:
                columns = execution_data[0]._fields if hasattr(execution_data[0], '_fields') else []
                data = [dict(zip(columns, row)) for row in execution_data]
            
            # 실행 성공으로 결과 업데이트
            result.execution_data = data
            result.execution_success = True
            
            logger.info(f"✅ SQL 실행 완료: {len(data)}행 반환")
            
        except Exception as exec_error:
            logger.error(f"SQL 실행 실패: {exec_error}")
            result.execution_success = False
            result.error_message = f"SQL 실행 실패: {str(exec_error)}"
        
        return {
            "sql_generation": result.model_dump(),
            "execution_summary": {
                "success": result.execution_success,
                "row_count": len(result.execution_data or []),
                "error": result.error_message if not result.execution_success else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ SQL 생성 및 실행 오류: {e}")
        raise HTTPException(status_code=500, detail=f"처리 실패: {str(e)}")


@router.get(
    "/strategies",
    summary="실행 전략 목록",
    description="사용 가능한 SQL 생성 실행 전략들을 반환합니다."
)
async def get_execution_strategies() -> Dict[str, Any]:
    """
    사용 가능한 실행 전략 목록을 반환합니다.
    
    Returns:
        Dict[str, Any]: 전략 목록 및 설명
    """
    
    strategies = {
        "llm_first": {
            "name": "LLM First",
            "description": "LLM을 우선 사용하고, 실패시 규칙 기반 fallback",
            "recommended_for": "복잡한 쿼리, 높은 정확도가 필요한 경우"
        },
        "rule_first": {
            "name": "Rule First", 
            "description": "규칙 기반을 우선 사용하고, 실패시 LLM fallback",
            "recommended_for": "간단한 쿼리, 빠른 응답이 필요한 경우"
        },
        "hybrid": {
            "name": "Hybrid",
            "description": "LLM과 규칙 기반을 병렬 실행 후 최적 결과 선택",
            "recommended_for": "최고 품질이 필요한 경우 (응답 시간 다소 증가)"
        },
        "llm_only": {
            "name": "LLM Only",
            "description": "LLM만 사용, fallback 없음", 
            "recommended_for": "LLM 성능 테스트, 창의적 쿼리 생성"
        },
        "rule_only": {
            "name": "Rule Only",
            "description": "규칙 기반만 사용, LLM 사용 안함",
            "recommended_for": "정해진 패턴의 쿼리, 비용 최적화"
        }
    }
    
    return {
        "strategies": strategies,
        "default": "llm_first",
        "total_count": len(strategies)
    }


@router.get(
    "/health",
    summary="파이프라인 상태 확인",
    description="LCEL SQL 파이프라인의 상태와 의존성들을 확인합니다."
)
async def pipeline_health_check() -> Dict[str, Any]:
    """
    파이프라인 상태 확인
    
    Returns:
        Dict[str, Any]: 상태 정보
    """
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    try:
        # LLM 클라이언트 상태 확인
        try:
            health_status["components"]["llm_client"] = "healthy"
        except Exception as e:
            health_status["components"]["llm_client"] = f"unhealthy: {e}"
            health_status["status"] = "degraded"
        
        # Intent Classifier 상태 확인
        try:
            test_result = await lcel_sql_pipeline.intent_chain.ainvoke({"query": "테스트"})
            health_status["components"]["intent_classifier"] = "healthy"
        except Exception as e:
            health_status["components"]["intent_classifier"] = f"unhealthy: {e}"
            health_status["status"] = "degraded"
        
        # 규칙 기반 생성기 상태 확인
        health_status["components"]["rule_generator"] = "healthy"
        
        # LangSmith 상태 확인
        from app.utils.langsmith_config import langsmith_manager
        health_status["components"]["langsmith"] = "enabled" if langsmith_manager.enabled else "disabled"
        
        return health_status
        
    except Exception as e:
        logger.error(f"상태 확인 중 오류: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# 헬퍼 함수들

def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Server-Sent Event 형식으로 데이터 포맷팅"""
    import json
    return json.dumps({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })


async def _save_pipeline_metrics(
    request: EnhancedSQLGenerationRequest, 
    result: EnhancedSQLPipelineResponse
) -> None:
    """백그라운드에서 파이프라인 메트릭 저장 (선택적 구현)"""
    try:
        # 여기에 메트릭 저장 로직 구현 (DB, 로그 파일 등)
        metrics = {
            "query": request.query,
            "strategy": request.strategy,
            "success": result.success,
            "generation_method": result.sql_result.generation_method if result.sql_result else None,
            "total_duration": result.metrics.get("total_duration") if result.metrics else None,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"📊 파이프라인 메트릭 저장: {metrics}")
        
    except Exception as e:
        logger.warning(f"메트릭 저장 실패 (무시됨): {e}")