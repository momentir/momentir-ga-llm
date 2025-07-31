from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MemoRefineRequest(BaseModel):
    memo: str = Field(..., description="원본 고객 메모")


class RefinedMemoResponse(BaseModel):
    memo_id: str = Field(..., description="저장된 메모 ID")
    summary: str = Field(..., description="메모 요약")
    keywords: List[str] = Field(..., description="주요 키워드")
    customer_status: str = Field(..., description="고객 상태")
    required_actions: List[str] = Field(..., description="필요 조치사항")
    original_memo: str = Field(..., description="원본 메모")
    similar_memos_count: int = Field(..., description="유사한 메모 개수")
    processed_at: datetime = Field(default_factory=datetime.now, description="처리 시간")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 에러 정보")