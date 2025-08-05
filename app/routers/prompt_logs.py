from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db_models.prompt_models import PromptTestLog
from app.database import get_db
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/api/prompt-logs", tags=["prompt-logs"])


class PromptTestLogResponse(BaseModel):
    id: str
    prompt_content: str
    memo_content: str  
    llm_response: str
    response_time_ms: Optional[int]
    tokens_used: Optional[int]
    success: bool
    error_message: Optional[str]
    user_session: Optional[str]
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[PromptTestLogResponse])
async def get_prompt_test_logs(
    limit: int = Query(default=50, le=1000, description="조회할 로그 수 (최대 1000)"),
    offset: int = Query(default=0, ge=0, description="건너뛸 로그 수"),
    success_only: Optional[bool] = Query(default=None, description="성공한 테스트만 조회"),
    start_date: Optional[datetime] = Query(default=None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(default=None, description="종료 날짜"),
    db: AsyncSession = Depends(get_db)
):
    """
    프롬프트 테스트 로그를 조회합니다.
    
    SQL 추출에 활용할 수 있는 데이터:
    - 프롬프트 ID (log.id)
    - 프롬프트 내용 (prompt_content) 
    - 메모 내용 (memo_content)
    - LLM 응답 내용 (llm_response)
    - 요청일시 (created_at)
    """
    try:
        # 기본 쿼리
        query = select(PromptTestLog).order_by(desc(PromptTestLog.created_at))
        
        # 성공 여부 필터
        if success_only is not None:
            query = query.where(PromptTestLog.success == success_only)
        
        # 날짜 범위 필터
        if start_date:
            query = query.where(PromptTestLog.created_at >= start_date)
        if end_date:
            query = query.where(PromptTestLog.created_at <= end_date)
        
        # 페이징
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return [
            PromptTestLogResponse(
                id=str(log.id),
                prompt_content=log.prompt_content,
                memo_content=log.memo_content,
                llm_response=log.llm_response,
                response_time_ms=log.response_time_ms,
                tokens_used=log.tokens_used,
                success=log.success,
                error_message=log.error_message,
                user_session=log.user_session,
                source=log.source,
                created_at=log.created_at
            )
            for log in logs
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"프롬프트 테스트 로그 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/sql-query")
async def get_sql_query_template():
    """
    프롬프트 테스트 로그를 추출하기 위한 SQL 쿼리 템플릿을 제공합니다.
    """
    
    sql_templates = {
        "basic_query": """
-- 기본 프롬프트 테스트 로그 조회
SELECT 
    id as prompt_id,
    prompt_content,
    memo_content,
    llm_response,
    created_at as request_datetime
FROM prompt_test_logs 
ORDER BY created_at DESC 
LIMIT 100;
        """,
        
        "success_only": """
-- 성공한 테스트만 조회
SELECT 
    id as prompt_id,
    prompt_content,
    memo_content,
    llm_response,
    response_time_ms,
    created_at as request_datetime
FROM prompt_test_logs 
WHERE success = true 
ORDER BY created_at DESC;
        """,
        
        "with_performance": """
-- 성능 정보 포함 조회
SELECT 
    id as prompt_id,
    prompt_content,
    memo_content,
    llm_response,
    response_time_ms,
    tokens_used,
    success,
    error_message,
    created_at as request_datetime
FROM prompt_test_logs 
ORDER BY response_time_ms DESC NULLS LAST
LIMIT 50;
        """,
        
        "date_range": """
-- 특정 날짜 범위 조회 (예: 최근 7일)
SELECT 
    id as prompt_id,
    prompt_content,
    memo_content,
    llm_response,
    created_at as request_datetime
FROM prompt_test_logs 
WHERE created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
        """,
        
        "aggregate_stats": """
-- 프롬프트 테스트 통계
SELECT 
    COUNT(*) as total_tests,
    COUNT(CASE WHEN success = true THEN 1 END) as successful_tests,
    ROUND(AVG(response_time_ms), 2) as avg_response_time_ms,
    DATE(created_at) as test_date
FROM prompt_test_logs 
GROUP BY DATE(created_at)
ORDER BY test_date DESC;
        """
    }
    
    return {
        "description": "프롬프트 테스트 로그 추출을 위한 SQL 쿼리 템플릿",
        "table_name": "prompt_test_logs",
        "columns": {
            "id": "프롬프트 테스트 ID (UUID)",
            "prompt_content": "테스트한 프롬프트 내용",
            "memo_content": "입력된 메모 내용",
            "llm_response": "LLM 응답 내용",
            "response_time_ms": "응답 시간 (밀리초)",
            "tokens_used": "사용된 토큰 수",
            "success": "성공 여부 (boolean)",
            "error_message": "오류 메시지 (실패시)",
            "user_session": "사용자 세션 ID",
            "source": "테스트 소스 (prompt_manager, api_direct)",
            "created_at": "요청일시"
        },
        "sql_templates": sql_templates
    }


@router.get("/stats")
async def get_prompt_test_stats(db: AsyncSession = Depends(get_db)):
    """프롬프트 테스트 통계를 조회합니다."""
    try:
        # 총 테스트 수
        total_query = select(PromptTestLog.id).count()
        total_result = await db.execute(total_query)
        total_tests = total_result.scalar()
        
        # 성공한 테스트 수
        success_query = select(PromptTestLog.id).where(PromptTestLog.success == True).count()
        success_result = await db.execute(success_query)
        successful_tests = success_result.scalar()
        
        # 평균 응답 시간
        from sqlalchemy import func
        avg_time_query = select(func.avg(PromptTestLog.response_time_ms)).where(
            PromptTestLog.response_time_ms.isnot(None)
        )
        avg_time_result = await db.execute(avg_time_query)
        avg_response_time = avg_time_result.scalar()
        
        return {
            "total_tests": total_tests or 0,
            "successful_tests": successful_tests or 0,
            "success_rate": round((successful_tests / total_tests * 100), 2) if total_tests > 0 else 0,
            "avg_response_time_ms": round(float(avg_response_time), 2) if avg_response_time else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )