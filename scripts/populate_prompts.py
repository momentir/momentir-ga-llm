#!/usr/bin/env python3
"""
프롬프트 관리 시스템 초기 데이터 생성 스크립트
"""
import asyncio
import os
import sys
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.prompt_service import PromptService
from app.models.prompt_models import PromptTemplateCreate, PromptVersionCreate, PromptCategory

# 환경변수에서 데이터베이스 URL 가져오기
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dbadmin:5JYbqQeiuQI7tYNaDoFAnp0oL@momentir-cx-llm-db.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com:5432/momentir-cx-llm")

# PostgreSQL URL을 AsyncPG 형식으로 변환
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 데이터베이스 엔진 생성
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 초기 프롬프트 템플릿 데이터
INITIAL_PROMPTS = [
    {
        "name": "메모 정제 프롬프트",
        "category": PromptCategory.MEMO_REFINE,
        "description": "고객 메모를 구조화된 JSON 형태로 정제하는 프롬프트",
        "template_content": """당신은 보험회사의 고객 메모를 분석하는 전문가입니다.
고객 메모에서 다음 정보를 정확하게 추출해주세요:

**중요: 시간 관련 표현을 놓치지 말고 모두 찾아주세요!**

메모: {{ memo }}

다음 JSON 형식으로 응답해주세요:
{
  "summary": "메모 요약",
  "status": "고객 상태/감정",
  "keywords": ["키워드1", "키워드2"],
  "time_expressions": [
    {"expression": "2주 후", "parsed_date": "2024-01-15"}
  ],
  "required_actions": ["필요한 후속 조치"],
  "insurance_info": {
    "products": ["현재 가입 상품"],
    "premium_amount": "보험료 정보",
    "interest_products": ["관심 상품"],
    "policy_changes": ["보험 변경사항"]
  }
}
'
보험업계 전문용어와 고객 서비스 관점에서 정확하게 분석하세요.""",
        "variables": {"memo": "고객 메모 내용"},
        "created_by": "system"
    },
    {
        "name": "엑셀 컬럼 매핑 프롬프트", 
        "category": PromptCategory.COLUMN_MAPPING,
        "description": "엑셀 파일의 컬럼명을 표준 스키마로 매핑하는 프롬프트",
        "template_content": """당신은 엑셀 컬럼명을 표준 고객 스키마로 매핑하는 전문가입니다.

표준 스키마:
{{ standard_schema }}

엑셀 컬럼명들을 표준 스키마로 매핑해주세요:

엑셀 컬럼: {{ excel_columns }}

각 엑셀 컬럼이 어떤 표준 필드에 해당하는지 매핑하고,
매핑할 수 없는 컬럼은 'unmapped'로 표시하세요.

JSON 형식으로 응답해주세요:
{
  "mappings": {
    "엑셀컬럼명": "표준필드명",
    "매핑불가컬럼": "unmapped"
  },
  "confidence": 0.95,
  "suggestions": ["매핑 개선 제안"]
}""",
        "variables": {"excel_columns": "엑셀 파일의 컬럼명 목록", "standard_schema": "표준 고객 스키마 정의"},
        "created_by": "system"
    },
    {
        "name": "조건부 분석 프롬프트",
        "category": PromptCategory.CONDITIONAL_ANALYSIS, 
        "description": "고객 정보와 메모를 종합하여 조건부 분석을 수행하는 프롬프트",
        "template_content": """당신은 20년 경력의 보험업계 전문 분석가입니다. 다음 정보를 종합하여 맞춤형 분석을 제공하세요.

=== 고객 정보 ===
{% for key, value in customer_info.items() if value %}
- {{ key }}: {{ value }}
{% endfor %}

=== 메모 요약 ===
{{ refined_memo.summary }}

=== 분석 조건 ===
{{ conditions }}

다음 관점에서 분석해주세요:
1. 고객의 현재 상황과 니즈 분석
2. 적합한 보험 상품 추천
3. 예상 리스크와 대응 방안
4. 향후 관리 전략

구체적이고 실무에 도움되는 인사이트를 제공하세요.""",
        "variables": {"customer_info": "고객 기본 정보", "refined_memo": "정제된 메모 데이터", "conditions": "분석 조건"},
        "created_by": "system"
    }
]

async def populate_prompts():
    """초기 프롬프트 템플릿들을 데이터베이스에 생성"""
    async with AsyncSessionLocal() as db:
        service = PromptService(db)
        
        for prompt_data in INITIAL_PROMPTS:
            try:
                # 이미 존재하는지 확인
                existing_template = await service.get_template_by_category(prompt_data["category"])
                if existing_template:
                    print(f"✅ {prompt_data['name']} 템플릿이 이미 존재합니다. 건너뜀")
                    continue
                
                # 새 템플릿 생성
                template_request = PromptTemplateCreate(
                    name=prompt_data["name"],
                    description=prompt_data["description"],
                    category=prompt_data["category"],
                    template_content=prompt_data["template_content"],
                    variables=prompt_data["variables"],
                    created_by=prompt_data["created_by"]
                )
                
                template = await service.create_template(template_request)
                print(f"✅ {prompt_data['name']} 템플릿 생성 완료 (ID: {template.id})")
                
                # 첫 번째 버전을 게시된 상태로 설정
                versions = await service.get_versions(template.id)
                if versions:
                    published_version = await service.publish_version(versions[0].id)
                    print(f"   📝 버전 {published_version.version_number} 게시 완료")
                    
            except Exception as e:
                print(f"❌ {prompt_data['name']} 생성 실패: {e}")
        
        print(f"\n🎉 프롬프트 초기화 완료!")

async def main():
    print("🚀 프롬프트 관리 시스템 초기 데이터 생성 시작...")
    await populate_prompts()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())