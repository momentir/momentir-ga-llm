from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from fastapi import UploadFile


class MemoRefineRequest(BaseModel):
    memo: str = Field(..., description="원본 고객 메모")
    custom_prompt: Optional[str] = Field(None, description="사용자 정의 프롬프트")


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
    raw_response: Optional[str] = Field(None, description="사용자 정의 프롬프트 사용 시 LLM 원본 응답")


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


# 고객 상품 관련 모델들
class CustomerProductCreate(BaseModel):
    product_name: Optional[str] = Field(None, description="가입상품명")
    coverage_amount: Optional[str] = Field(None, description="가입금액")
    subscription_date: Optional[date] = Field(None, description="가입일자")
    expiry_renewal_date: Optional[date] = Field(None, description="종료일/갱신일")
    auto_transfer_date: Optional[str] = Field(None, description="자동이체일")
    policy_issued: Optional[bool] = Field(False, description="증권교부여부")


class CustomerProductResponse(BaseModel):
    product_id: str = Field(..., description="상품 ID")
    product_name: Optional[str] = Field(None, description="가입상품명")
    coverage_amount: Optional[str] = Field(None, description="가입금액")
    subscription_date: Optional[date] = Field(None, description="가입일자")
    expiry_renewal_date: Optional[date] = Field(None, description="종료일/갱신일")
    auto_transfer_date: Optional[str] = Field(None, description="자동이체일")
    policy_issued: Optional[bool] = Field(False, description="증권교부여부")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")


# 고객 데이터 관련 모델들
class CustomerCreateRequest(BaseModel):
    user_id: Optional[int] = Field(None, description="설계사 ID")
    name: Optional[str] = Field(None, description="고객 이름")
    contact: Optional[str] = Field(None, description="연락처")
    affiliation: Optional[str] = Field(None, description="소속")
    occupation: Optional[str] = Field(None, description="직업")
    gender: Optional[str] = Field(None, description="성별")
    date_of_birth: Optional[date] = Field(None, description="생년월일")
    interests: Optional[List[str]] = Field(default=[], description="관심사")
    life_events: Optional[List[Dict[str, Any]]] = Field(default=[], description="인생 이벤트")
    insurance_products: Optional[List[Dict[str, Any]]] = Field(default=[], description="보험 상품 정보")
    
    # 새로 추가된 필드들
    customer_type: Optional[str] = Field(None, description="고객 유형: 가입, 미가입")
    contact_channel: Optional[str] = Field(None, description="고객 접점: 가족, 지역, 소개, 지역마케팅, 인바운드, 제휴db, 단체계약, 방카, 개척, 기타")
    phone: Optional[str] = Field(None, description="전화번호 (000-0000-0000 포맷)")
    resident_number: Optional[str] = Field(None, description="주민번호 (999999-1****** 포맷)")
    address: Optional[str] = Field(None, description="주소")
    job_title: Optional[str] = Field(None, description="직업")
    bank_name: Optional[str] = Field(None, description="계좌은행")
    account_number: Optional[str] = Field(None, description="계좌번호")
    referrer: Optional[str] = Field(None, description="소개자")
    notes: Optional[str] = Field(None, description="기타")
    
    # 가입상품 리스트
    products: Optional[List[CustomerProductCreate]] = Field(default=[], description="가입상품 리스트")


class CustomerResponse(BaseModel):
    customer_id: str = Field(..., description="고객 ID")
    user_id: Optional[int] = Field(None, description="설계사 ID")
    name: Optional[str] = Field(None, description="고객 이름")
    contact: Optional[str] = Field(None, description="연락처")
    affiliation: Optional[str] = Field(None, description="소속")
    occupation: Optional[str] = Field(None, description="직업")
    gender: Optional[str] = Field(None, description="성별")
    date_of_birth: Optional[date] = Field(None, description="생년월일")
    interests: Optional[List[str]] = Field(default=[], description="관심사")
    life_events: Optional[List[Dict[str, Any]]] = Field(default=[], description="인생 이벤트")
    insurance_products: Optional[List[Dict[str, Any]]] = Field(default=[], description="보험 상품 정보")
    
    # 새로 추가된 필드들
    customer_type: Optional[str] = Field(None, description="고객 유형: 가입, 미가입")
    contact_channel: Optional[str] = Field(None, description="고객 접점: 가족, 지역, 소개, 지역마케팅, 인바운드, 제휴db, 단체계약, 방카, 개척, 기타")
    phone: Optional[str] = Field(None, description="전화번호 (000-0000-0000 포맷)")
    resident_number: Optional[str] = Field(None, description="주민번호 (999999-1****** 포맷)")
    address: Optional[str] = Field(None, description="주소")
    job_title: Optional[str] = Field(None, description="직업")
    bank_name: Optional[str] = Field(None, description="계좌은행")
    account_number: Optional[str] = Field(None, description="계좌번호")
    referrer: Optional[str] = Field(None, description="소개자")
    notes: Optional[str] = Field(None, description="기타")
    
    # 가입상품 리스트
    products: Optional[List[CustomerProductResponse]] = Field(default=[], description="가입상품 리스트")
    
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")


class CustomerUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="고객 이름")
    contact: Optional[str] = Field(None, description="연락처")
    affiliation: Optional[str] = Field(None, description="소속")
    occupation: Optional[str] = Field(None, description="직업")
    gender: Optional[str] = Field(None, description="성별")
    date_of_birth: Optional[date] = Field(None, description="생년월일")
    interests: Optional[List[str]] = Field(None, description="관심사")
    life_events: Optional[List[Dict[str, Any]]] = Field(None, description="인생 이벤트")
    insurance_products: Optional[List[Dict[str, Any]]] = Field(None, description="보험 상품 정보")


class ExcelUploadRequest(BaseModel):
    user_id: int = Field(..., description="설계사 ID")
    file: UploadFile = Field(..., description="업로드할 엑셀 파일")


class ExcelUploadResponse(BaseModel):
    success: bool = Field(..., description="업로드 성공 여부")
    processed_rows: int = Field(..., description="처리된 행 수")
    created_customers: int = Field(..., description="생성된 고객 수")
    updated_customers: int = Field(..., description="업데이트된 고객 수")
    errors: List[str] = Field(default=[], description="처리 중 발생한 오류들")
    column_mapping: Dict[str, str] = Field(..., description="LLM이 매핑한 컬럼 정보")
    
    # 가입상품 처리 통계
    total_products: int = Field(default=0, description="총 상품 수")
    created_products: int = Field(default=0, description="생성된 상품 수")
    failed_products: int = Field(default=0, description="처리 실패한 상품 수")
    
    # 필드별 매핑 성공률
    mapping_success_rate: Dict[str, float] = Field(default={}, description="필드별 매핑 성공률 (0-1)")
    
    # 처리 시간 정보
    processing_time_seconds: Optional[float] = Field(None, description="처리 시간 (초)")
    processed_at: datetime = Field(default_factory=datetime.now, description="처리 완료 시간")


class ColumnMappingRequest(BaseModel):
    excel_columns: List[str] = Field(..., description="엑셀 파일의 컬럼명들")


class ColumnMappingResponse(BaseModel):
    mapping: Dict[str, str] = Field(..., description="엑셀 컬럼 -> 표준 필드 매핑")
    unmapped_columns: List[str] = Field(default=[], description="매핑되지 않은 컬럼들")
    confidence_score: float = Field(..., description="매핑 신뢰도 (0-1)")


# 이벤트 관련 모델들
class EventCreateRequest(BaseModel):
    customer_id: str = Field(..., description="고객 ID")
    memo_id: Optional[str] = Field(None, description="관련 메모 ID")
    event_type: str = Field(..., description="이벤트 타입: call, message, reminder, calendar")
    scheduled_date: Optional[datetime] = Field(None, description="예정 날짜")
    priority: str = Field(default="medium", description="우선순위: high, medium, low")
    description: Optional[str] = Field(None, description="이벤트 설명")


class EventResponse(BaseModel):
    event_id: str = Field(..., description="이벤트 ID")
    customer_id: str = Field(..., description="고객 ID")
    memo_id: Optional[str] = Field(None, description="관련 메모 ID")
    event_type: str = Field(..., description="이벤트 타입")
    scheduled_date: Optional[datetime] = Field(None, description="예정 날짜")
    priority: str = Field(..., description="우선순위")
    status: str = Field(..., description="상태")
    description: Optional[str] = Field(None, description="이벤트 설명")
    created_at: datetime = Field(..., description="생성 시간")


class UpcomingEventsRequest(BaseModel):
    customer_id: Optional[str] = Field(None, description="특정 고객 ID (없으면 전체)")
    days: int = Field(default=7, description="향후 며칠간의 이벤트")


class UpcomingEventsResponse(BaseModel):
    events: List[EventResponse] = Field(..., description="향후 이벤트 목록")
    total_count: int = Field(..., description="전체 이벤트 수")