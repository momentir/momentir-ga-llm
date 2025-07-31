from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import MemoRefineRequest, RefinedMemoResponse, MemoAnalyzeRequest, MemoAnalyzeResponse, ErrorResponse
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


@router.post("/analyze", response_model=MemoAnalyzeResponse)
async def analyze_memo(request: MemoAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """
    기존 메모를 조건에 따라 분석합니다.
    
    - **memo_id**: 분석할 메모의 ID
    - **conditions**: 분석 조건 (customer_type, contract_status 등)
    
    기능:
    - 저장된 메모를 조건에 따라 LLM으로 분석
    - 고객 유형과 계약 상태를 고려한 맞춤형 대응 방안 제시
    - 분석 결과를 데이터베이스에 저장
    """
    try:
        if not request.memo_id or not request.memo_id.strip():
            raise HTTPException(
                status_code=400, 
                detail="메모 ID가 비어있습니다."
            )
        
        if not request.conditions:
            raise HTTPException(
                status_code=400, 
                detail="분석 조건이 비어있습니다."
            )
        
        # 조건부 분석 수행
        result = await memo_refiner.analyze_memo_with_conditions(
            memo_id=request.memo_id,
            conditions=request.conditions,
            db=db
        )
        
        return MemoAnalyzeResponse(
            analysis_id=result["analysis_id"],
            memo_id=result["memo_id"],
            conditions=result["conditions"],
            analysis=result["analysis"],
            original_memo=result["original_memo"],
            refined_memo=result["refined_memo"],
            analyzed_at=datetime.fromisoformat(result["analyzed_at"].replace('Z', '+00:00'))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"메모 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/memo/{memo_id}")
async def get_memo_with_analyses(memo_id: str, db: AsyncSession = Depends(get_db)):
    """
    메모와 관련된 모든 분석 결과를 조회합니다.
    
    - **memo_id**: 조회할 메모의 ID
    
    기능:
    - 원본 메모와 정제된 메모 정보 조회
    - 해당 메모에 대한 모든 분석 결과 조회
    - 분석 조건별 결과 확인
    """
    try:
        if not memo_id or not memo_id.strip():
            raise HTTPException(
                status_code=400, 
                detail="메모 ID가 비어있습니다."
            )
        
        # 메모 및 분석 결과 조회
        result = await memo_refiner.get_memo_with_analyses(memo_id=memo_id, db_session=db)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"메모 조회 중 오류가 발생했습니다: {str(e)}"
        )