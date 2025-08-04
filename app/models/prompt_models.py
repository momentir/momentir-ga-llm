"""
프롬프트 관리 시스템을 위한 Pydantic 모델들
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import uuid


class PromptCategory(str, Enum):
    MEMO_REFINE = "memo_refine"
    COLUMN_MAPPING = "column_mapping"
    ANALYSIS = "analysis"
    CONDITIONAL_ANALYSIS = "conditional_analysis"


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., max_length=100, description="프롬프트 템플릿 이름")
    description: Optional[str] = Field(None, description="프롬프트 설명")
    category: PromptCategory = Field(..., description="프롬프트 카테고리")
    template_content: str = Field(..., description="프롬프트 템플릿 내용 (변수 포함)")
    variables: Optional[Dict[str, Any]] = Field(None, description="템플릿 변수 정의")
    created_by: Optional[str] = Field(None, max_length=100, description="생성자")

    class Config:
        json_encoders = {
            PromptCategory: lambda v: v.value
        }


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    template_content: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PromptTemplate(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    category: PromptCategory
    template_content: str
    variables: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True
        json_encoders = {
            PromptCategory: lambda v: v.value
        }


class PromptVersionCreate(BaseModel):
    template_id: uuid.UUID
    template_content: str = Field(..., description="새 버전의 프롬프트 내용")
    variables: Optional[Dict[str, Any]] = Field(None, description="템플릿 변수")
    change_notes: Optional[str] = Field(None, description="변경 사항 설명")
    created_by: Optional[str] = Field(None, max_length=100)


class PromptVersion(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    version_number: int
    template_content: str
    variables: Optional[Dict[str, Any]]
    change_notes: Optional[str]
    is_published: bool
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class ABTestCreate(BaseModel):
    test_name: str = Field(..., max_length=100, description="A/B 테스트 이름")
    description: Optional[str] = Field(None, description="테스트 설명")
    category: PromptCategory = Field(..., description="테스트 카테고리")
    version_a_id: uuid.UUID = Field(..., description="A 버전 ID")
    version_b_id: uuid.UUID = Field(..., description="B 버전 ID")
    traffic_split: float = Field(0.5, ge=0.0, le=1.0, description="트래픽 분할 비율 (A 버전)")
    start_date: datetime = Field(..., description="테스트 시작일")
    end_date: Optional[datetime] = Field(None, description="테스트 종료일")
    success_metric: Optional[str] = Field(None, description="성공 지표")
    created_by: Optional[str] = Field(None, max_length=100)

    class Config:
        json_encoders = {
            PromptCategory: lambda v: v.value
        }


class ABTest(BaseModel):
    id: uuid.UUID
    test_name: str
    description: Optional[str]
    category: PromptCategory
    version_a_id: uuid.UUID
    version_b_id: uuid.UUID
    traffic_split: float
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime]
    success_metric: Optional[str]
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True
        json_encoders = {
            PromptCategory: lambda v: v.value
        }


class TestResultCreate(BaseModel):
    test_id: uuid.UUID
    version_id: uuid.UUID
    user_session: Optional[str] = Field(None, max_length=100)
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    response_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    success: Optional[bool] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class TestResult(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    version_id: uuid.UUID
    user_session: Optional[str]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    response_time_ms: Optional[int]
    tokens_used: Optional[int]
    success: Optional[bool]
    quality_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class PromptRenderRequest(BaseModel):
    template_id: Optional[uuid.UUID] = None
    category: Optional[PromptCategory] = None
    variables: Dict[str, Any] = Field(default_factory=dict, description="템플릿 변수 값들")
    user_session: Optional[str] = Field(None, description="A/B 테스트용 사용자 세션")

    class Config:
        json_encoders = {
            PromptCategory: lambda v: v.value
        }


class PromptRenderResponse(BaseModel):
    rendered_content: str = Field(..., description="렌더링된 프롬프트 내용")
    template_id: uuid.UUID = Field(..., description="사용된 템플릿 ID")
    version_id: uuid.UUID = Field(..., description="사용된 버전 ID")
    is_ab_test: bool = Field(False, description="A/B 테스트 여부")
    test_id: Optional[uuid.UUID] = Field(None, description="A/B 테스트 ID")
    version_label: Optional[str] = Field(None, description="버전 라벨 (A/B)")


class ABTestStats(BaseModel):
    test_id: uuid.UUID
    test_name: str
    total_runs: int
    version_a_runs: int
    version_b_runs: int
    version_a_success_rate: float
    version_b_success_rate: float
    version_a_avg_response_time: Optional[float]
    version_b_avg_response_time: Optional[float]
    version_a_avg_quality: Optional[float]
    version_b_avg_quality: Optional[float]
    confidence_level: Optional[float] = Field(None, description="통계적 신뢰도")
    recommendation: Optional[str] = Field(None, description="권장사항")


class PromptTemplateList(BaseModel):
    templates: List[PromptTemplate]
    total: int
    page: int
    size: int