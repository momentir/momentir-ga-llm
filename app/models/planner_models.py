from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum


class LifeStageEnum(str, Enum):
    STUDENT = "student"
    YOUNG_PROFESSIONAL = "young_professional"
    FAMILY_BUILDING = "family_building"
    ESTABLISHED_FAMILY = "established_family"
    PRE_RETIREMENT = "pre_retirement"
    RETIREMENT = "retirement"


class RiskProfileEnum(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InsuranceProductType(str, Enum):
    LIFE = "life"
    HEALTH = "health"
    DISABILITY = "disability"
    AUTO = "auto"
    HOME = "home"
    TRAVEL = "travel"
    BUSINESS = "business"


class ContactMethodEnum(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    SMS = "sms"
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"


class BasicInfo(BaseModel):
    customer_id: str = Field(..., description="고객 ID")
    name: str = Field(..., description="고객 이름")
    age: Optional[int] = Field(None, description="나이")
    gender: Optional[str] = Field(None, description="성별")
    contact: Optional[str] = Field(None, description="연락처")
    income_level: Optional[str] = Field(None, description="소득 수준")
    family_status: Optional[str] = Field(None, description="가족 상황")


class InsuranceProduct(BaseModel):
    product_type: InsuranceProductType = Field(..., description="보험 상품 타입")
    provider: str = Field(..., description="보험사")
    premium: Optional[float] = Field(None, description="보험료")
    coverage_amount: Optional[float] = Field(None, description="보장 금액")
    start_date: Optional[date] = Field(None, description="시작일")
    renewal_date: Optional[date] = Field(None, description="갱신일")
    status: str = Field(default="active", description="상태")


class InsuranceStatus(BaseModel):
    current_products: List[InsuranceProduct] = Field(default=[], description="현재 가입 상품")
    total_premium: Optional[float] = Field(None, description="총 보험료")
    coverage_gaps: List[str] = Field(default=[], description="보장 공백")
    risk_profile: RiskProfileEnum = Field(default=RiskProfileEnum.MODERATE, description="위험 프로필")


class LifeEvent(BaseModel):
    event_type: str = Field(..., description="이벤트 타입 (결혼, 출산, 이직 등)")
    date: Optional[date] = Field(None, description="이벤트 날짜")
    impact_level: str = Field(default="medium", description="영향도 (high/medium/low)")
    insurance_needs: List[str] = Field(default=[], description="관련 보험 니즈")


class Dependent(BaseModel):
    relationship: str = Field(..., description="관계 (배우자, 자녀 등)")
    age: Optional[int] = Field(None, description="나이")
    coverage_needs: List[str] = Field(default=[], description="보장 니즈")


class LifeStage(BaseModel):
    current_stage: LifeStageEnum = Field(..., description="현재 인생 단계")
    life_events: List[LifeEvent] = Field(default=[], description="인생 이벤트")
    dependents: List[Dependent] = Field(default=[], description="피부양자")


class FinancialProfile(BaseModel):
    income_stability: str = Field(default="stable", description="소득 안정성")
    savings_rate: Optional[float] = Field(None, description="저축률")
    investment_experience: str = Field(default="beginner", description="투자 경험")
    financial_goals: List[str] = Field(default=[], description="재정 목표")
    budget_for_insurance: Optional[float] = Field(None, description="보험 예산")


class Preferences(BaseModel):
    communication_style: str = Field(default="formal", description="소통 스타일")
    preferred_contact_method: ContactMethodEnum = Field(default=ContactMethodEnum.PHONE, description="선호 연락 방법")
    preferred_contact_time: Optional[str] = Field(None, description="선호 연락 시간")
    decision_making_style: str = Field(default="analytical", description="의사결정 스타일")
    price_sensitivity: str = Field(default="medium", description="가격 민감도")


class CustomerProfile(BaseModel):
    basic_info: BasicInfo = Field(..., description="기본 정보")
    insurance_status: InsuranceStatus = Field(..., description="보험 현황")
    life_stage: LifeStage = Field(..., description="인생 단계")
    financial_profile: FinancialProfile = Field(..., description="재정 프로필")
    preferences: Preferences = Field(..., description="고객 선호도")


class Recommendation(BaseModel):
    date: date = Field(..., description="추천 날짜")
    recommendation: str = Field(..., description="추천 내용")
    status: str = Field(default="pending", description="상태")
    follow_up_required: bool = Field(default=False, description="후속 조치 필요 여부")


class InteractionHistory(BaseModel):
    last_contact_date: Optional[date] = Field(None, description="마지막 연락일")
    contact_frequency: str = Field(default="monthly", description="연락 빈도")
    interaction_types: List[str] = Field(default=[], description="상호작용 유형")
    sentiment_trend: str = Field(default="neutral", description="감정 트렌드")
    key_concerns: List[str] = Field(default=[], description="주요 관심사")
    previous_recommendations: List[Recommendation] = Field(default=[], description="이전 추천 내역")


class AnalysisContext(BaseModel):
    analysis_type: str = Field(..., description="분석 유형")
    priority_level: str = Field(default="medium", description="우선순위")
    deadline: Optional[date] = Field(None, description="마감일")
    specific_focus: List[str] = Field(default=[], description="특정 포커스 영역")
    regulatory_considerations: List[str] = Field(default=[], description="규제 고려사항")


class EconomicIndicators(BaseModel):
    interest_rates: Optional[float] = Field(None, description="금리")
    inflation_rate: Optional[float] = Field(None, description="인플레이션율")
    market_volatility: str = Field(default="low", description="시장 변동성")


class MarketConditions(BaseModel):
    economic_indicators: EconomicIndicators = Field(..., description="경제 지표")
    industry_trends: List[str] = Field(default=[], description="업계 트렌드")
    competitive_landscape: List[str] = Field(default=[], description="경쟁 환경")
    regulatory_changes: List[str] = Field(default=[], description="규제 변화")


class PlannerInput(BaseModel):
    """
    보험 플래너 분석을 위한 종합 입력 데이터 모델
    PROJECT_CONTEXT_NEW.md에서 언급된 planner_input.json 스키마 구현
    """
    customer_profile: CustomerProfile = Field(..., description="고객 프로필")
    interaction_history: InteractionHistory = Field(..., description="상호작용 이력")
    analysis_context: AnalysisContext = Field(..., description="분석 컨텍스트")
    market_conditions: MarketConditions = Field(..., description="시장 상황")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_profile": {
                    "basic_info": {
                        "customer_id": "12345",
                        "name": "김철수",
                        "age": 35,
                        "gender": "남성",
                        "contact": "010-1234-5678",
                        "income_level": "중상",
                        "family_status": "기혼"
                    },
                    "insurance_status": {
                        "current_products": [
                            {
                                "product_type": "life",
                                "provider": "삼성생명",
                                "premium": 50000,
                                "coverage_amount": 100000000,
                                "start_date": "2020-01-01",
                                "renewal_date": "2025-01-01",
                                "status": "active"
                            }
                        ],
                        "total_premium": 50000,
                        "coverage_gaps": ["건강보험"],
                        "risk_profile": "moderate"
                    },
                    "life_stage": {
                        "current_stage": "family_building",
                        "life_events": [
                            {
                                "event_type": "결혼",
                                "date": "2022-05-01",
                                "impact_level": "high",
                                "insurance_needs": ["생명보험", "건강보험"]
                            }
                        ],
                        "dependents": [
                            {
                                "relationship": "배우자",
                                "age": 32,
                                "coverage_needs": ["건강보험"]
                            }
                        ]
                    },
                    "financial_profile": {
                        "income_stability": "stable",
                        "savings_rate": 0.3,
                        "investment_experience": "intermediate",
                        "financial_goals": ["주택 구매", "자녀 교육비"],
                        "budget_for_insurance": 100000
                    },
                    "preferences": {
                        "communication_style": "friendly",
                        "preferred_contact_method": "phone",
                        "preferred_contact_time": "저녁",
                        "decision_making_style": "analytical",
                        "price_sensitivity": "medium"
                    }
                },
                "interaction_history": {
                    "last_contact_date": "2024-01-01",
                    "contact_frequency": "quarterly",
                    "interaction_types": ["상담", "계약"],
                    "sentiment_trend": "positive",
                    "key_concerns": ["보장 부족", "보험료 부담"],
                    "previous_recommendations": [
                        {
                            "date": "2023-12-01",
                            "recommendation": "건강보험 추가 가입",
                            "status": "pending",
                            "follow_up_required": True
                        }
                    ]
                },
                "analysis_context": {
                    "analysis_type": "comprehensive_review",
                    "priority_level": "high",
                    "deadline": "2024-02-01",
                    "specific_focus": ["보장 분석", "상품 추천"],
                    "regulatory_considerations": ["개인정보보호법"]
                },
                "market_conditions": {
                    "economic_indicators": {
                        "interest_rates": 3.5,
                        "inflation_rate": 2.1,
                        "market_volatility": "medium"
                    },
                    "industry_trends": ["디지털 보험", "맞춤형 상품"],
                    "competitive_landscape": ["가격 경쟁", "서비스 차별화"],
                    "regulatory_changes": ["보험업법 개정"]
                }
            }
        }


class PlannerAnalysisResult(BaseModel):
    """
    플래너 분석 결과 모델
    """
    analysis_id: str = Field(..., description="분석 ID")
    customer_id: str = Field(..., description="고객 ID")
    analysis_summary: str = Field(..., description="분석 요약")
    risk_assessment: Dict[str, Any] = Field(..., description="위험 평가")
    coverage_analysis: Dict[str, Any] = Field(..., description="보장 분석")
    product_recommendations: List[Dict[str, Any]] = Field(..., description="상품 추천")
    action_items: List[str] = Field(..., description="액션 아이템")
    priority_score: float = Field(..., description="우선순위 점수")
    confidence_level: float = Field(..., description="신뢰도")
    next_review_date: Optional[date] = Field(None, description="다음 검토일")
    generated_at: datetime = Field(default_factory=datetime.now, description="생성 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "analysis_12345",
                "customer_id": "12345",
                "analysis_summary": "고객은 현재 생명보험만 가입되어 있으며, 건강보험 보장이 부족합니다.",
                "risk_assessment": {
                    "overall_risk": "medium",
                    "health_risk": "low",
                    "financial_risk": "low",
                    "family_risk": "medium"
                },
                "coverage_analysis": {
                    "current_coverage": 100000000,
                    "recommended_coverage": 150000000,
                    "gap_amount": 50000000,
                    "coverage_ratio": 0.67
                },
                "product_recommendations": [
                    {
                        "product_type": "health",
                        "recommendation_reason": "건강보험 보장 부족",
                        "estimated_premium": 30000,
                        "priority": "high"
                    }
                ],
                "action_items": [
                    "건강보험 상담 예약",
                    "보장 내용 상세 설명",
                    "가족력 조사"
                ],
                "priority_score": 0.8,
                "confidence_level": 0.9,
                "next_review_date": "2024-06-01"
            }
        }