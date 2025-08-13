"""
자연어 검색 전용 LangSmith 추적 유틸리티
"""

import os
import logging
from contextlib import contextmanager
from functools import wraps
from typing import Dict, Any, Optional
from datetime import datetime

from app.utils.langsmith_config import langsmith_manager

logger = logging.getLogger(__name__)


@contextmanager
def nl_search_langsmith_context():
    """
    자연어 검색 전용 LangSmith 프로젝트 컨텍스트
    
    이 컨텍스트 매니저는 자연어 검색 요청 처리 중에
    LangSmith 프로젝트를 일시적으로 변경합니다.
    """
    if not langsmith_manager.enabled:
        yield
        return
    
    # 현재 프로젝트명 백업
    original_project = os.environ.get("LANGCHAIN_PROJECT")
    
    # 자연어 검색 프로젝트로 변경
    nl_search_project = langsmith_manager.get_nl_search_project_name()
    
    try:
        os.environ["LANGCHAIN_PROJECT"] = nl_search_project
        logger.debug(f"LangSmith 프로젝트를 자연어 검색용으로 변경: {nl_search_project}")
        yield
        
    finally:
        # 원래 프로젝트로 복원
        if original_project:
            os.environ["LANGCHAIN_PROJECT"] = original_project
        else:
            os.environ.pop("LANGCHAIN_PROJECT", None)
        logger.debug(f"LangSmith 프로젝트 복원: {original_project or '기본값'}")


def trace_nl_search_call(operation_name: str = "nl_search_operation"):
    """
    자연어 검색 전용 LangSmith 추적 데코레이터
    
    Args:
        operation_name: LangSmith에 기록될 작업 이름
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with nl_search_langsmith_context():
                # 추가 메타데이터 수집
                metadata = {
                    "operation": operation_name,
                    "timestamp": datetime.now().isoformat(),
                    "service": "natural_language_search"
                }
                
                # kwargs에서 검색 관련 정보 추출
                if "request_data" in kwargs:
                    request_data = kwargs["request_data"]
                    if hasattr(request_data, 'query'):
                        metadata["query_length"] = len(request_data.query)
                        metadata["query_preview"] = request_data.query[:50] + "..." if len(request_data.query) > 50 else request_data.query
                    if hasattr(request_data, 'options') and hasattr(request_data.options, 'strategy'):
                        metadata["strategy"] = request_data.options.strategy.value if hasattr(request_data.options.strategy, 'value') else str(request_data.options.strategy)
                    if hasattr(request_data, 'limit'):
                        metadata["result_limit"] = request_data.limit
                
                # LangSmith에 메타데이터 기록 (가능한 경우)
                try:
                    if langsmith_manager.client:
                        # 실제 함수 실행
                        result = await func(*args, **kwargs)
                        
                        # 결과에서 추가 메타데이터 수집
                        if hasattr(result, 'total_rows'):
                            metadata["result_rows"] = result.total_rows
                        if hasattr(result, 'execution') and hasattr(result.execution, 'execution_time_ms'):
                            metadata["execution_time_ms"] = result.execution.execution_time_ms
                        if hasattr(result, 'success'):
                            metadata["success"] = result.success
                        
                        logger.info(f"✅ 자연어 검색 추적 완료: {operation_name} - {metadata}")
                        return result
                    else:
                        # LangSmith 클라이언트가 없는 경우 그냥 실행
                        return await func(*args, **kwargs)
                        
                except Exception as e:
                    metadata["error"] = str(e)
                    metadata["success"] = False
                    logger.error(f"❌ 자연어 검색 오류 추적: {operation_name} - {metadata}")
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with nl_search_langsmith_context():
                metadata = {
                    "operation": operation_name,
                    "timestamp": datetime.now().isoformat(),
                    "service": "natural_language_search"
                }
                
                try:
                    result = func(*args, **kwargs)
                    metadata["success"] = True
                    logger.info(f"✅ 자연어 검색 추적 완료: {operation_name}")
                    return result
                except Exception as e:
                    metadata["error"] = str(e)
                    metadata["success"] = False
                    logger.error(f"❌ 자연어 검색 오류 추적: {operation_name} - {metadata}")
                    raise
        
        # 비동기 함수인지 확인
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_nl_search_metrics(query: str, result: Dict[str, Any], execution_time_ms: float, 
                         strategy: str, success: bool = True, error: str = None):
    """
    자연어 검색 메트릭을 LangSmith에 로깅
    
    Args:
        query: 검색 쿼리
        result: 검색 결과
        execution_time_ms: 실행 시간 (밀리초)
        strategy: 사용된 전략
        success: 성공 여부
        error: 에러 메시지 (실패시)
    """
    if not langsmith_manager.enabled:
        return
    
    with nl_search_langsmith_context():
        metrics = {
            "event_type": "nl_search_metrics",
            "query": query[:200],  # 쿼리 길이 제한
            "query_length": len(query),
            "execution_time_ms": execution_time_ms,
            "strategy": strategy,
            "success": success,
            "result_count": result.get("total_rows", 0) if result else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        if error:
            metrics["error"] = error
        
        if result:
            # 결과에서 추가 정보 추출
            if "intent" in result:
                metrics["intent_type"] = result["intent"].get("intent_type")
                metrics["confidence"] = result["intent"].get("confidence")
            
            if "execution" in result:
                metrics["sql_length"] = len(result["execution"].get("sql_query", ""))
                metrics["strategy_used"] = result["execution"].get("strategy_used")
        
        logger.info(f"📊 자연어 검색 메트릭: {metrics}")
        
        # CloudWatch 로거와도 통합
        try:
            from app.utils.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_search_query(
                query=query,
                user_id=1,  # 개발용 더미 사용자 ID
                strategy=strategy,
                response_time=execution_time_ms / 1000.0,
                success=success,
                result_count=result.get("total_rows", 0) if result else 0,
                error_message=error
            )
        except Exception as e:
            logger.warning(f"CloudWatch 로깅 실패: {e}")


def get_nl_search_project_info() -> Dict[str, str]:
    """
    현재 자연어 검색 LangSmith 프로젝트 정보 반환
    
    Returns:
        Dict containing project information
    """
    return {
        "project_name": langsmith_manager.get_nl_search_project_name(),
        "enabled": langsmith_manager.enabled,
        "environment": "production" if langsmith_manager.get_nl_search_project_name().startswith("momentir-cx") else "local"
    }