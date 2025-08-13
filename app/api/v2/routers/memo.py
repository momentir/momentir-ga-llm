from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import MemoRefineRequest, RefinedMemoResponse, MemoAnalyzeRequest, MemoAnalyzeResponse, QuickSaveRequest, QuickSaveResponse, ErrorResponse, TimeExpressionResponse, InsuranceInfoResponse
from app.api.v2.services.memo_refiner import MemoRefinerServiceV2
from app.core.database import get_db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/api/memo", tags=["memo-v2"])
memo_refiner = MemoRefinerServiceV2()


@router.post("/quick-save", response_model=QuickSaveResponse)
async def quick_save_memo(request: QuickSaveRequest, db: AsyncSession = Depends(get_db)):
    """
    V2: Enhanced memo quick save with improved processing
    
    New features in V2:
    - Enhanced validation
    - Better error handling
    - Improved performance
    """
    try:
        if not request.content or not request.content.strip():
            raise HTTPException(
                status_code=400, 
                detail="메모 내용이 비어있습니다."
            )
            
        if not request.customer_id or not request.customer_id.strip():
            raise HTTPException(
                status_code=400, 
                detail="고객 ID가 비어있습니다."
            )
        
        # V2: Use new memo refiner service with enhanced logic
        result = await memo_refiner.quick_save_memo(
            customer_id=request.customer_id,
            content=request.content,
            db_session=db
        )
        
        return QuickSaveResponse(
            memo_id=result["memo_id"],
            customer_id=str(result["customer_id"]),
            content=result["content"],
            status=result["status"],
            saved_at=datetime.fromisoformat(result["saved_at"].replace('Z', '+00:00'))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"메모 저장 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/refine", response_model=RefinedMemoResponse)
async def refine_memo(request: MemoRefineRequest, db: AsyncSession = Depends(get_db)):
    """
    V2: Enhanced memo refinement with advanced AI processing
    
    New features in V2:
    - Better LLM integration
    - Improved accuracy
    - Enhanced metadata extraction
    """
    try:
        if not request.memo or not request.memo.strip():
            raise HTTPException(
                status_code=400, 
                detail="메모 내용이 비어있습니다."
            )
        
        # V2: Use new refinement logic
        custom_prompt = getattr(request, 'custom_prompt', None)
        result = await memo_refiner.refine_and_save_memo(request.memo, db, custom_prompt=custom_prompt)
        refined_data = result["refined_data"]
        
        # Enhanced processing for V2
        time_expressions = []
        for expr in refined_data.get("time_expressions", []):
            if isinstance(expr, dict):
                time_expressions.append(TimeExpressionResponse(
                    expression=expr.get("expression", ""),
                    parsed_date=expr.get("parsed_date")
                ))
            elif isinstance(expr, str):
                time_expressions.append(TimeExpressionResponse(
                    expression=expr,
                    parsed_date=None
                ))
        
        insurance_data = refined_data.get("insurance_info", {})
        insurance_info = InsuranceInfoResponse(
            products=insurance_data.get("products") or [],
            premium_amount=insurance_data.get("premium_amount"),
            interest_products=insurance_data.get("interest_products") or [],
            policy_changes=insurance_data.get("policy_changes") or []
        )
        
        return RefinedMemoResponse(
            memo_id=result["memo_id"],
            summary=refined_data.get("summary", ""),
            status=refined_data.get("status", ""),
            keywords=refined_data.get("keywords") or [],
            time_expressions=time_expressions,
            required_actions=refined_data.get("required_actions") or [],
            insurance_info=insurance_info,
            original_memo=request.memo,
            similar_memos_count=result["similar_memos_count"],
            processed_at=datetime.fromisoformat(result["created_at"].replace('Z', '+00:00')),
            raw_response=refined_data.get("raw_response")
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
    V2: Advanced memo analysis with enhanced context awareness
    
    New features in V2:
    - Better context understanding
    - Enhanced analysis accuracy
    - Improved recommendation engine
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
        
        # V2: Enhanced analysis logic
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
    V2: Enhanced memo retrieval with advanced analytics
    
    New features in V2:
    - Enhanced metadata
    - Better performance
    - Additional context
    """
    try:
        if not memo_id or not memo_id.strip():
            raise HTTPException(
                status_code=400, 
                detail="메모 ID가 비어있습니다."
            )
        
        # V2: Use enhanced retrieval logic
        result = await memo_refiner.get_memo_with_analyses(memo_id=memo_id, db_session=db)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"메모 조회 중 오류가 발생했습니다: {str(e)}"
        )