from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import MemoRefineRequest, RefinedMemoResponse, ErrorResponse
from app.services.memo_refiner import MemoRefinerService
from app.database import get_db
from datetime import datetime

router = APIRouter(prefix="/api/memo", tags=["memo"])
memo_refiner = MemoRefinerService()


@router.post("/refine", response_model=RefinedMemoResponse)
async def refine_memo(request: MemoRefineRequest, db: AsyncSession = Depends(get_db)):
    """
    고객 메모를 구조화된 형태로 정제하고 데이터베이스에 저장합니다.
    
    - **memo**: 정제할 원본 고객 메모
    
    기능:
    - LLM을 통한 메모 정제
    - PostgreSQL + pgvector를 통한 메모 저장
    - 임베딩 벡터 생성 및 저장
    - 유사한 메모 검색
    """
    try:
        if not request.memo or not request.memo.strip():
            raise HTTPException(
                status_code=400, 
                detail="메모 내용이 비어있습니다."
            )
        
        # 메모 정제 및 데이터베이스 저장
        result = await memo_refiner.refine_and_save_memo(request.memo, db)
        
        refined_data = result["refined_data"]
        
        return RefinedMemoResponse(
            memo_id=result["memo_id"],
            summary=refined_data.get("summary", ""),
            keywords=refined_data.get("keywords", []),
            customer_status=refined_data.get("customer_status", ""),
            required_actions=refined_data.get("required_actions", []),
            original_memo=request.memo,
            similar_memos_count=result["similar_memos_count"],
            processed_at=datetime.fromisoformat(result["created_at"].replace('Z', '+00:00'))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"메모 정제 중 오류가 발생했습니다: {str(e)}"
        )