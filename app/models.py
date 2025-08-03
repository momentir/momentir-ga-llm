from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class MemoRefineRequest(BaseModel):
    memo: str = Field(..., description="원본 고객 메모")


class TimeExpressionResponse(BaseModel):
    expression: str = Field(..., description="원본 시간 표현")
    parsed_date: Optional[str] = Field(None, description="파싱된 날짜 (YYYY-MM-DD)")

class InsuranceInfoResponse(BaseModel):
    products: List[str] = Field(default=[], description="언급된 보험 상품명")
    premium_amount: Optional[str] = Field(None, description="보험료 금액")
    interest_products: List[str] = Field(default=[], description="관심 있는 보험 상품")
    policy_changes: List[str] = Field(default=[], description="정책 변경 사항")

class RefinedMemoResponse(BaseModel):
    memo_id: str = Field(..., description="저장된 메모 ID")
    summary: str = Field(..., description="메모 요약")
    status: str = Field(..., description="고객 상태/감정")
    keywords: List[str] = Field(..., description="주요 키워드")
    time_expressions: List[TimeExpressionResponse] = Field(default=[], description="시간 관련 표현")
    required_actions: List[str] = Field(..., description="필요 조치사항")
    insurance_info: InsuranceInfoResponse = Field(..., description="보험 관련 정보")
    original_memo: str = Field(..., description="원본 메모")
    similar_memos_count: int = Field(..., description="유사한 메모 개수")
    processed_at: datetime = Field(default_factory=datetime.now, description="처리 시간")


class MemoAnalyzeRequest(BaseModel):
    memo_id: str = Field(..., description="분석할 메모 ID")
    conditions: Dict[str, Any] = Field(..., description="분석 조건 (customer_type, contract_status 등)")


class MemoAnalyzeResponse(BaseModel):
    analysis_id: str = Field(..., description="분석 결과 ID")
    memo_id: str = Field(..., description="분석된 메모 ID")
    conditions: Dict[str, Any] = Field(..., description="적용된 분석 조건")
    analysis: str = Field(..., description="LLM 분석 결과")
    original_memo: str = Field(..., description="원본 메모")
    refined_memo: Dict[str, Any] = Field(..., description="정제된 메모 데이터")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="분석 시간")


class QuickSaveRequest(BaseModel):
    customer_id: str = Field(..., description="고객 ID")
    content: str = Field(..., description="메모 내용")


class QuickSaveResponse(BaseModel):
    memo_id: str = Field(..., description="저장된 메모 ID")
    customer_id: str = Field(..., description="고객 ID")
    content: str = Field(..., description="저장된 메모 내용")
    status: str = Field(default="draft", description="메모 상태 (draft)")
    saved_at: datetime = Field(default_factory=datetime.now, description="저장 시간")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 에러 정보")