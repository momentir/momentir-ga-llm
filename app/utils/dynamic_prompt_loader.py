"""
동적 프롬프트 로더 - 기존 하드코딩된 프롬프트를 동적으로 로드
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.prompt_service import PromptService
from app.models.prompt_models import PromptCategory, PromptRenderRequest, TestResultCreate
from app.database import get_db
import uuid
import time

logger = logging.getLogger(__name__)


class DynamicPromptLoader:
    """동적 프롬프트 로딩 및 A/B 테스트 지원"""
    
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5분 캐시
    
    async def get_prompt(
        self, 
        category: PromptCategory, 
        variables: Dict[str, Any] = None,
        user_session: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Optional[str]:
        """프롬프트 렌더링 (A/B 테스트 지원)"""
        if variables is None:
            variables = {}
        
        # DB 세션이 없으면 새로 생성
        close_db = False
        if db is None:
            # Python 3.9 호환성: anext() 대신 __anext__() 사용
            db_generator = get_db()
            db = await db_generator.__anext__()
            close_db = True
        
        try:
            service = PromptService(db)
            
            request = PromptRenderRequest(
                category=category,
                variables=variables,
                user_session=user_session
            )
            
            response = await service.render_prompt(request)
            
            if response:
                # A/B 테스트 메타데이터 저장 (나중에 결과 기록용)
                if response.is_ab_test and user_session:
                    cache_key = f"ab_test_{user_session}_{category.value}"
                    self._cache[cache_key] = {
                        'test_id': response.test_id,
                        'version_id': response.version_id,
                        'timestamp': time.time()
                    }
                
                return response.rendered_content
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading prompt for category {category}: {e}")
            return None
        finally:
            if close_db:
                await db.close()
    
    async def record_usage_result(
        self,
        category: PromptCategory,
        user_session: Optional[str],
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        response_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        success: Optional[bool] = None,
        quality_score: Optional[float] = None,
        db: Optional[AsyncSession] = None
    ):
        """프롬프트 사용 결과 기록 (A/B 테스트용)"""
        if not user_session:
            return
        
        cache_key = f"ab_test_{user_session}_{category.value}"
        ab_test_data = self._cache.get(cache_key)
        
        if not ab_test_data:
            return  # A/B 테스트가 아님
        
        # 캐시 만료 확인
        if time.time() - ab_test_data['timestamp'] > self._cache_ttl:
            del self._cache[cache_key]
            return
        
        # DB 세션이 없으면 새로 생성
        close_db = False
        if db is None:
            # Python 3.9 호환성: anext() 대신 __anext__() 사용
            db_generator = get_db()
            db = await db_generator.__anext__()
            close_db = True
        
        try:
            service = PromptService(db)
            
            result_data = TestResultCreate(
                test_id=ab_test_data['test_id'],
                version_id=ab_test_data['version_id'],
                user_session=user_session,
                input_data=input_data,
                output_data=output_data,
                response_time_ms=response_time_ms,
                tokens_used=tokens_used,
                success=success,
                quality_score=quality_score
            )
            
            await service.record_test_result(result_data)
            
            # 캐시에서 제거 (한 번만 기록)
            del self._cache[cache_key]
            
        except Exception as e:
            logger.error(f"Error recording A/B test result: {e}")
        finally:
            if close_db:
                await db.close()


# 전역 인스턴스
prompt_loader = DynamicPromptLoader()


async def get_memo_refine_prompt(memo: str, user_session: str = None, db: AsyncSession = None) -> str:
    """메모 정제 프롬프트 동적 로딩"""
    variables = {"memo": memo}
    
    prompt = await prompt_loader.get_prompt(
        category=PromptCategory.MEMO_REFINE,
        variables=variables,
        user_session=user_session,
        db=db
    )
    
    # 폴백: 하드코딩된 프롬프트
    if not prompt:
        logger.warning("Dynamic prompt not found, using fallback")
        return f"""당신은 보험회사의 고객 메모를 분석하는 전문가입니다.
고객 메모에서 다음 정보를 정확하게 추출해주세요:

**중요: 시간 관련 표현을 놓치지 말고 모두 찾아주세요!**

메모: {memo}

다음 JSON 형식으로 응답해주세요:
{{
  "summary": "메모 요약",
  "status": "고객 상태/감정",
  "keywords": ["키워드1", "키워드2"],
  "time_expressions": [
    {{"expression": "2주 후", "parsed_date": "2024-01-15"}}
  ],
  "required_actions": ["필요한 후속 조치"],
  "insurance_info": {{
    "products": ["현재 가입 상품"],
    "premium_amount": "보험료 정보",
    "interest_products": ["관심 상품"],
    "policy_changes": ["보험 변경사항"]
  }}
}}

보험업계 전문용어와 고객 서비스 관점에서 정확하게 분석하세요."""
    
    return prompt


async def get_column_mapping_prompt(excel_columns: list, standard_schema: dict, user_session: str = None, db: AsyncSession = None) -> str:
    """엑셀 컬럼 매핑 프롬프트 동적 로딩"""
    variables = {
        "excel_columns": excel_columns,
        "standard_schema": standard_schema
    }
    
    prompt = await prompt_loader.get_prompt(
        category=PromptCategory.COLUMN_MAPPING,
        variables=variables,
        user_session=user_session,
        db=db
    )
    
    # 폴백: 하드코딩된 프롬프트
    if not prompt:
        logger.warning("Dynamic column mapping prompt not found, using fallback")
        return f"""당신은 엑셀 컬럼명을 표준 고객 스키마로 매핑하는 전문가입니다.

표준 스키마:
{standard_schema}

엑셀 컬럼명들을 표준 스키마로 매핑해주세요:

엑셀 컬럼: {excel_columns}

각 엑셀 컬럼이 어떤 표준 필드에 해당하는지 매핑하고,
매핑할 수 없는 컬럼은 'unmapped'로 표시하세요.

JSON 형식으로 응답해주세요:
{{
  "mappings": {{
    "엑셀컬럼명": "표준필드명",
    "매핑불가컬럼": "unmapped"
  }},
  "confidence": 0.95,
  "suggestions": ["매핑 개선 제안"]
}}"""
    
    return prompt


async def get_conditional_analysis_prompt(
    customer_info: dict,
    refined_memo: dict,
    conditions: dict,
    user_session: str = None,
    db: AsyncSession = None
) -> str:
    """조건부 분석 프롬프트 동적 로딩"""
    variables = {
        "customer_info": customer_info,
        "refined_memo": refined_memo,
        "conditions": conditions
    }
    
    prompt = await prompt_loader.get_prompt(
        category=PromptCategory.CONDITIONAL_ANALYSIS,
        variables=variables,
        user_session=user_session,
        db=db
    )
    
    # 폴백: 하드코딩된 프롬프트
    if not prompt:
        logger.warning("Dynamic conditional analysis prompt not found, using fallback")
        customer_info_text = "\n".join([f"- {k}: {v}" for k, v in customer_info.items() if v])
        memo_summary = refined_memo.get('summary', '정보 없음')
        
        return f"""당신은 20년 경력의 보험업계 전문 분석가입니다. 다음 정보를 종합하여 맞춤형 분석을 제공하세요.

=== 고객 정보 ===
{customer_info_text}

=== 메모 요약 ===
{memo_summary}

=== 분석 조건 ===
{conditions}

다음 관점에서 분석해주세요:
1. 고객의 현재 상황과 니즈 분석
2. 적합한 보험 상품 추천
3. 예상 리스크와 대응 방안
4. 향후 관리 전략

구체적이고 실무에 도움되는 인사이트를 제공하세요."""
    
    return prompt