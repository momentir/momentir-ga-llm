import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db_models import CustomerMemo, AnalysisResult, Customer
from app.db_models.prompt_models import PromptTestLog
from app.utils.langsmith_config import langsmith_manager, trace_llm_call
from app.utils.llm_client import llm_client_manager
from app.utils.dynamic_prompt_loader import get_memo_refine_prompt, get_conditional_analysis_prompt, prompt_loader
from app.models.prompt_models import PromptCategory
import json
import re
import uuid
import logging
import time

logger = logging.getLogger(__name__)


class TimeExpression(BaseModel):
    expression: str = Field(description="원본 시간 표현")
    parsed_date: Optional[str] = Field(description="파싱된 날짜 (YYYY-MM-DD 형식)", default=None)

class InsuranceInfo(BaseModel):
    products: List[str] = Field(description="언급된 보험 상품명", default=[])
    premium_amount: Optional[str] = Field(description="보험료 금액", default=None)
    interest_products: List[str] = Field(description="관심 있는 보험 상품", default=[])
    policy_changes: List[str] = Field(description="정책 변경 사항", default=[])

class RefinedMemoOutput(BaseModel):
    summary: str = Field(description="메모의 핵심 내용을 한 문장으로 요약")
    status: str = Field(description="고객의 현재 상태/감정")
    keywords: List[str] = Field(description="주요 키워드 (관심사, 니즈)")
    time_expressions: List[TimeExpression] = Field(description="시간 관련 표현들", default=[])
    required_actions: List[str] = Field(description="필요한 후속 조치")
    insurance_info: InsuranceInfo = Field(description="보험 관련 정보", default_factory=InsuranceInfo)


class MemoRefinementParser:
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            # Try JSON parsing first
            
            logger.info(f"🔍 파싱할 텍스트 (처음 200자): {text[:200]}...")
            
            # Extract JSON from the response if it's wrapped in text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                logger.info(f"🔍 추출된 JSON (처음 100자): {json_text[:100]}...")
                
                parsed_json = json.loads(json_text)
                logger.info(f"✅ JSON 파싱 성공: {list(parsed_json.keys())}")
                
                # Validate and convert to our expected format (안전한 None 처리)
                result = {
                    "summary": parsed_json.get("summary", ""),
                    "status": parsed_json.get("status", ""),
                    "keywords": parsed_json.get("keywords") or [],
                    "time_expressions": parsed_json.get("time_expressions") or [],
                    "required_actions": parsed_json.get("required_actions") or [],
                    "insurance_info": self._safe_insurance_info(parsed_json.get("insurance_info", {}))
                }
                return result
        except Exception as e:
            logger.warning(f"❌ JSON 파싱 실패: {e}")
            logger.info(f"🔍 원본 텍스트: {text}")
            pass
        
        # Fallback to manual parsing for backward compatibility
        lines = text.strip().split('\n')
        result = {
            "summary": "",
            "status": "",
            "keywords": [],
            "time_expressions": [],
            "required_actions": [],
            "insurance_info": {
                "products": [],
                "premium_amount": None,
                "interest_products": [],
                "policy_changes": []
            }
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('- 요약:') or line.startswith('요약:'):
                result["summary"] = line.replace('- 요약:', '').replace('요약:', '').strip()
            elif line.startswith('- 고객 상태:') or line.startswith('고객 상태:'):
                result["status"] = line.replace('- 고객 상태:', '').replace('고객 상태:', '').strip()
            elif line.startswith('- 주요 키워드:') or line.startswith('주요 키워드:'):
                keywords_text = line.replace('- 주요 키워드:', '').replace('주요 키워드:', '').strip()
                result["keywords"] = [k.strip() for k in keywords_text.split(',') if k.strip()]
            elif line.startswith('- 필요 조치:') or line.startswith('필요 조치:'):
                actions_text = line.replace('- 필요 조치:', '').replace('필요 조치:', '').strip()
                if actions_text:
                    result["required_actions"] = [a.strip() for a in actions_text.split(',') if a.strip()]
        
        return result
    
    def _safe_insurance_info(self, insurance_data: Dict[str, Any]) -> Dict[str, Any]:
        """보험 정보의 None 값을 안전하게 처리"""
        if not isinstance(insurance_data, dict):
            insurance_data = {}
        
        return {
            "products": insurance_data.get("products") or [],
            "premium_amount": insurance_data.get("premium_amount"),
            "interest_products": insurance_data.get("interest_products") or [],
            "policy_changes": insurance_data.get("policy_changes") or []
        }


class MemoRefinerService:
    def __init__(self):
        # 싱글톤 LLM 클라이언트 매니저 사용
        self.llm_manager = llm_client_manager
        
        # 동적 프롬프트 로딩을 위한 설정
        self.use_dynamic_prompts = True
        
        self.parser = MemoRefinementParser()
        
        # LLM 클라이언트들
        self.llm_client = self.llm_manager.get_chat_client()
        self.embedding_llm = self.llm_manager.get_embedding_client()
        self.chat_model = self.llm_manager.get_chat_model_name()
        self.embedding_model = self.llm_manager.get_embedding_model_name()
        
        logger.info("✅ MemoRefinerService 초기화 완료 (싱글톤 클라이언트 사용)")
    
    
    async def refine_memo(self, memo: str, user_session: str = None, db_session: AsyncSession = None, custom_prompt: str = None) -> Dict[str, Any]:
        """
        OpenAI를 사용하여 메모를 정제하는 메인 메서드 (동적 프롬프트 지원)
        """
        try:
            logger.info(f"메모 정제 시작: {memo[:50]}...")
            start_time = time.time()
            
            # 프롬프트 결정 로직 (우선순위: custom_prompt > 동적 프롬프트 > 폴백 프롬프트)
            logger.info(f"🔍 프롬프트 결정 - custom_prompt: {custom_prompt is not None}, use_dynamic_prompts: {self.use_dynamic_prompts}")
            if custom_prompt:
                # 사용자 정의 프롬프트 사용 - {memo} 플레이스홀더가 있는 경우에만 format 적용
                try:
                    if "{memo}" in custom_prompt:
                        system_prompt = custom_prompt.format(memo=memo)
                    else:
                        # 플레이스홀더가 없으면 메모를 프롬프트 끝에 추가
                        system_prompt = f"{custom_prompt}\n\n메모: {memo}"
                    logger.info(f"✅ 사용자 정의 프롬프트 사용: {custom_prompt[:100]}...")
                except Exception as format_error:
                    logger.error(f"❌ 프롬프트 포맷팅 오류: {format_error}")
                    # 안전한 폴백: 메모를 끝에 추가
                    system_prompt = f"{custom_prompt}\n\n메모: {memo}"
                    logger.info(f"✅ 폴백 프롬프트 사용")
            elif self.use_dynamic_prompts:
                # 동적 프롬프트 로딩
                system_prompt = await get_memo_refine_prompt(memo, user_session, db_session)
                logger.info(f"✅ 동적 프롬프트 사용: {system_prompt[:100]}...")
            else:
                # 폴백 프롬프트 (하드코딩)
                system_prompt = f"""당신은 보험회사의 고객 메모를 분석하는 전문가입니다.
고객 메모에서 다음 정보를 정확하게 추출해주세요:

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
"""
                logger.info("❌ 기본 폴백 프롬프트 사용")
            
            logger.info(f"🚀 실제 사용될 프롬프트 (처음 200자): {system_prompt[:200]}...")
            
            # LangChain 클라이언트 사용 (LangSmith 자동 추적)
            response = await self.llm_client.ainvoke(system_prompt)
            result_text = response.content
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            # 파서를 통해 결과 파싱 (사용자 정의 프롬프트도 JSON 형태로 처리 시도)
            logger.info("✅ LLM 응답 파싱 시작")
            result = self.parser.parse(result_text)

            # 사용자 정의 프롬프트인 경우 항상 원본 응답을 포함
            if custom_prompt:
                logger.info("✅ 사용자 정의 프롬프트 - 원본 응답 포함")
                if not result.get("summary"):
                    # JSON 파싱 실패한 경우
                    result = {
                        "summary": "사용자 정의 프롬프트 응답",
                        "status": "원본 응답",
                        "keywords": ["사용자 정의 프롬프트"],
                        "time_expressions": [],
                        "required_actions": [],
                        "insurance_info": {
                            "products": [],
                            "premium_amount": None,
                            "interest_products": [],
                            "policy_changes": []
                        }
                    }
                # 성공/실패 관계없이 원본 응답 항상 추가
                result["raw_response"] = result_text.strip()

            # 결과 검증 및 기본값 설정
            validated_result = self._validate_result(result)
            
            # 사용자 정의 프롬프트인 경우 테스트 로그 저장
            if custom_prompt and db_session:
                await self._save_prompt_test_log(
                    prompt_content=custom_prompt,
                    memo_content=memo,
                    llm_response=result_text,
                    response_time_ms=response_time_ms,
                    success=True,
                    db_session=db_session
                )
            
            # A/B 테스트 결과 기록 (동적 프롬프트 사용 시)
            if self.use_dynamic_prompts and user_session:
                try:
                    await prompt_loader.record_usage_result(
                        category=PromptCategory.MEMO_REFINE,
                        user_session=user_session,
                        input_data={"memo": memo},
                        output_data=validated_result,
                        response_time_ms=response_time_ms,
                        success=True,
                        db=db_session
                    )
                except Exception as e:
                    logger.warning(f"A/B 테스트 결과 기록 실패: {e}")
            
            logger.info("메모 정제 완료")
            return validated_result
            
        except Exception as e:
            logger.error(f"메모 정제 중 오류: {str(e)}")
            
            # 에러 발생 시에도 사용자 정의 프롬프트인 경우 로그 저장
            if custom_prompt and db_session:
                try:
                    await self._save_prompt_test_log(
                        prompt_content=custom_prompt,
                        memo_content=memo,
                        llm_response="",
                        response_time_ms=int((time.time() - start_time) * 1000),
                        success=False,
                        error_message=str(e),
                        db_session=db_session
                    )
                except Exception as log_error:
                    logger.warning(f"프롬프트 테스트 로그 저장 실패: {log_error}")
            
            raise Exception(f"메모 정제 중 오류가 발생했습니다: {str(e)}")
    
    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        결과 검증 및 기본값 설정
        """
        validated = {
            "summary": result.get("summary", "").strip() or "메모 요약을 생성할 수 없습니다.",
            "status": result.get("status", "").strip() or "고객 상태 파악 필요",
            "keywords": result.get("keywords", []) or ["키워드 없음"],
            "time_expressions": result.get("time_expressions", []) or [],
            "required_actions": result.get("required_actions", []) or ["추가 분석 필요"],
            "insurance_info": result.get("insurance_info", {}) or {}
        }
        
        # raw_response 필드가 있으면 보존
        if "raw_response" in result:
            validated["raw_response"] = result["raw_response"]
        
        # 키워드가 문자열인 경우 리스트로 변환
        if isinstance(validated["keywords"], str):
            validated["keywords"] = [k.strip() for k in validated["keywords"].split(',') if k.strip()]
        
        # 필요 조치가 문자열인 경우 리스트로 변환
        if isinstance(validated["required_actions"], str):
            validated["required_actions"] = [a.strip() for a in validated["required_actions"].split(',') if a.strip()]
        
        # insurance_info 기본값 설정
        if not validated["insurance_info"]:
            validated["insurance_info"] = {
                "products": [],
                "premium_amount": None,
                "interest_products": [],
                "policy_changes": []
            }
        
        # time_expressions 검증
        if validated["time_expressions"] and isinstance(validated["time_expressions"], list):
            for i, expr in enumerate(validated["time_expressions"]):
                if isinstance(expr, str):
                    # 문자열인 경우 딕셔너리로 변환
                    validated["time_expressions"][i] = {
                        "expression": expr,
                        "parsed_date": None
                    }
        
        return validated
    
    async def create_embedding(self, text: str) -> Optional[List[float]]:
        """
        텍스트에 대한 임베딩 벡터를 생성합니다.
        LangChain 임베딩 클라이언트를 사용하여 LangSmith 자동 추적을 지원합니다.
        """
        if not hasattr(self, 'embedding_llm') or not self.embedding_llm:
            logger.warning("임베딩 LangChain 클라이언트가 설정되지 않았습니다.")
            return None
            
        try:
            logger.info(f"임베딩 생성 시작 ({self.embedding_model}): {text[:50]}...")
            
            # LangChain 임베딩 클라이언트 사용 (자동 LangSmith 추적)
            # 환경변수가 설정되어 있으면 자동으로 추적됨
            embedding = await self.embedding_llm.aembed_query(text)
            logger.info(f"임베딩 생성 완료 (LangSmith 자동 추적): 차원 {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            return None
    
    async def save_memo_to_db(self, 
                             original_memo: str, 
                             refined_data: Dict[str, Any], 
                             db_session: AsyncSession) -> CustomerMemo:
        """
        정제된 메모를 데이터베이스에 저장합니다.
        """
        try:
            # 임베딩을 위한 텍스트 생성 (원본 메모 + 요약)
            embedding_text = f"{original_memo} {refined_data.get('summary', '')}"
            embedding_vector = await self.create_embedding(embedding_text)
            
            # 데이터베이스 모델 생성 (임베딩이 실패해도 계속 진행)
            memo_record = CustomerMemo(
                id=uuid.uuid4(),
                original_memo=original_memo,
                refined_memo=refined_data,
                status="refined",
                embedding=embedding_vector  # JSONB로 저장됨
            )
            
            # 데이터베이스에 저장
            db_session.add(memo_record)
            await db_session.commit()
            await db_session.refresh(memo_record)
            
            logger.info(f"메모 저장 완료 (임베딩 포함): {memo_record.id}")
            return memo_record
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"메모 저장 중 오류가 발생했습니다: {str(e)}")
    
    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        두 벡터 간의 코사인 유사도를 계산합니다.
        """
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
            
        return dot_product / (magnitude1 * magnitude2)
    
    async def find_similar_memos(self, 
                                memo: str, 
                                db_session: AsyncSession, 
                                limit: int = 5) -> List[CustomerMemo]:
        """
        pgvector를 사용한 효율적인 유사도 검색
        코사인 유사도 기반으로 가장 유사한 메모들을 찾습니다.
        """
        try:
            # 입력 메모의 임베딩 생성
            query_embedding = await self.create_embedding(memo)
            
            if query_embedding is not None:
                # pgvector의 코사인 유사도를 사용한 효율적인 검색
                # 1 - (embedding <=> query_vector)로 유사도 계산 (높을수록 유사)
                from sqlalchemy import text
                
                # 쿼리 임베딩을 PostgreSQL vector 형태로 변환
                vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
                
                # pgvector의 코사인 거리 연산자(<=>)를 사용한 효율적인 검색
                stmt = text("""
                    SELECT id, customer_id, original_memo, refined_memo, status, author, 
                           embedding, created_at,
                           1 - (embedding <=> :query_vector) as similarity
                    FROM customer_memos 
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :query_vector
                    LIMIT :limit
                """)
                
                result = await db_session.execute(stmt, {"query_vector": vector_str, "limit": limit})
                rows = result.fetchall()
                
                if not rows:
                    logger.info("임베딩이 있는 메모가 없습니다. 최근 메모를 반환합니다.")
                    return await self._get_recent_memos(db_session, limit)
                
                # 결과를 CustomerMemo 객체로 변환
                similar_memos = []
                for row in rows:
                    # 각 행에서 CustomerMemo 객체 재구성
                    memo_obj = CustomerMemo(
                        id=row.id,
                        customer_id=row.customer_id,
                        original_memo=row.original_memo,
                        refined_memo=row.refined_memo,
                        status=row.status,
                        author=row.author,
                        embedding=row.embedding,
                        created_at=row.created_at
                    )
                    similar_memos.append(memo_obj)
                
                logger.info(f"pgvector 유사도 검색 완료: {len(similar_memos)}개 메모 반환")
                return similar_memos
            else:
                logger.warning("쿼리 임베딩 생성 실패, 최근 메모를 반환합니다.")
                return await self._get_recent_memos(db_session, limit)
            
        except Exception as e:
            logger.warning(f"pgvector 유사 메모 검색 실패, 최근 메모를 반환합니다: {str(e)}")
            # Fallback: 기존 Python 기반 검색 사용
            return await self._find_similar_memos_fallback(memo, db_session, limit)
    
    async def _get_recent_memos(self, db_session: AsyncSession, limit: int) -> List[CustomerMemo]:
        """최근 메모들을 반환하는 헬퍼 함수"""
        try:
            stmt = select(CustomerMemo).order_by(CustomerMemo.created_at.desc()).limit(limit)
            result = await db_session.execute(stmt)
            return result.scalars().all()
        except:
            return []
    
    async def _find_similar_memos_fallback(self, 
                                         memo: str, 
                                         db_session: AsyncSession, 
                                         limit: int = 5) -> List[CustomerMemo]:
        """
        Python 기반 코사인 유사도를 사용한 폴백 메모 검색
        pgvector가 실패했을 때 사용됩니다.
        """
        try:
            logger.info("Python 기반 유사도 검색 실행 (폴백 모드)")
            
            # 쿼리 임베딩 생성
            query_embedding = await self.create_embedding(memo)
            if not query_embedding:
                logger.warning("쿼리 임베딩 생성 실패, 최근 메모를 반환합니다.")
                return await self._get_recent_memos(db_session, limit)
            
            # 임베딩이 있는 모든 메모 조회
            stmt = select(CustomerMemo).where(CustomerMemo.embedding.isnot(None))
            result = await db_session.execute(stmt)
            memos_with_embeddings = result.scalars().all()
            
            if not memos_with_embeddings:
                logger.info("임베딩이 있는 메모가 없습니다. 최근 메모를 반환합니다.")
                return await self._get_recent_memos(db_session, limit)
            
            # 유사도 계산 및 정렬
            memo_similarities = []
            for memo_record in memos_with_embeddings:
                try:
                    # 임베딩이 리스트인지 확인 (이전 JSONB 형태 또는 vector 형태)
                    embedding = memo_record.embedding
                    if isinstance(embedding, list):
                        memo_embedding = embedding
                    elif hasattr(embedding, 'tolist'):
                        # pgvector 형태인 경우
                        memo_embedding = embedding.tolist()
                    else:
                        logger.warning(f"메모 {memo_record.id}의 임베딩 형태를 인식할 수 없습니다: {type(embedding)}")
                        continue
                    
                    # 코사인 유사도 계산
                    similarity = self._calculate_cosine_similarity(query_embedding, memo_embedding)
                    memo_similarities.append((memo_record, similarity))
                    
                except Exception as e:
                    logger.warning(f"메모 {memo_record.id}의 유사도 계산 실패: {e}")
                    continue
            
            # 유사도 기준으로 정렬 (높은 순)
            memo_similarities.sort(key=lambda x: x[1], reverse=True)
            
            # 상위 N개 메모 반환
            similar_memos = [memo_record for memo_record, similarity in memo_similarities[:limit]]
            
            logger.info(f"Python 기반 유사도 검색 완료: {len(similar_memos)}개 메모 반환")
            return similar_memos
            
        except Exception as e:
            logger.error(f"Python 기반 유사도 검색 실패: {str(e)}")
            # 마지막 폴백: 최근 메모 반환
            return await self._get_recent_memos(db_session, limit)
    
    async def refine_and_save_memo(self, 
                                  memo: str, 
                                  db_session: AsyncSession,
                                  auto_generate_events: bool = True,
                                  custom_prompt: str = None) -> Dict[str, Any]:
        """
        메모를 정제하고 데이터베이스에 저장하는 통합 메서드
        """
        try:
            # 1. 메모 정제
            refined_data = await self.refine_memo(memo, user_session=None, db_session=db_session, custom_prompt=custom_prompt)
            
            # 2. 데이터베이스에 저장
            memo_record = await self.save_memo_to_db(memo, refined_data, db_session)
            
            # 3. 유사한 메모 검색 (선택적)
            similar_memos = await self.find_similar_memos(memo, db_session, limit=3)
            
            # 4. 이벤트 자동 생성 (옵션) - 별도 트랜잭션으로 처리
            events_created = []
            if auto_generate_events:
                logger.info(f"메모 {memo_record.id}에 대한 이벤트 자동 생성은 별도 API 호출로 처리하세요: POST /api/events/process-memo")
            
            return {
                "memo_id": str(memo_record.id),
                "refined_data": refined_data,
                "similar_memos_count": len(similar_memos),
                "events_created": len(events_created),
                "events": events_created,
                "created_at": memo_record.created_at.isoformat()
            }
            
        except Exception as e:
            raise Exception(f"메모 정제 및 저장 중 오류가 발생했습니다: {str(e)}")
    
    async def analyze_memo_with_conditions(self, 
                                         memo_id: str, 
                                         conditions: Dict[str, Any], 
                                         db_session: AsyncSession) -> Dict[str, Any]:
        """
        기존 메모를 조건에 따라 분석합니다. (고객 데이터 연동 개선)
        """
        try:
            # 1. 메모 조회 (고객 정보 포함)
            stmt = select(CustomerMemo).where(CustomerMemo.id == uuid.UUID(memo_id))
            result = await db_session.execute(stmt)
            memo_record = result.scalar_one_or_none()
            
            if not memo_record:
                raise Exception(f"메모 ID {memo_id}를 찾을 수 없습니다.")
            
            # 2. 고객 정보 조회 (있는 경우)
            customer_data = None
            if memo_record.customer_id:
                customer_stmt = select(Customer).where(Customer.customer_id == memo_record.customer_id)
                customer_result = await db_session.execute(customer_stmt)
                customer_record = customer_result.scalar_one_or_none()
                
                if customer_record:
                    customer_data = {
                        "name": customer_record.name,
                        "age": self._calculate_age(customer_record.date_of_birth) if customer_record.date_of_birth else None,
                        "gender": customer_record.gender,
                        "interests": customer_record.interests or [],
                        "life_events": customer_record.life_events or [],
                        "insurance_products": customer_record.insurance_products or []
                    }
            
            # 3. 고객 데이터를 포함한 조건부 분석 수행
            analysis_result = await self.perform_enhanced_conditional_analysis(
                refined_memo=memo_record.refined_memo,
                conditions=conditions,
                customer_data=customer_data
            )
            
            # 4. 분석 결과를 데이터베이스에 저장
            analysis_record = await self.save_analysis_to_db(
                memo_id=memo_record.id,
                conditions=conditions,
                analysis=analysis_result,
                db_session=db_session
            )
            
            return {
                "analysis_id": str(analysis_record.id),
                "memo_id": str(memo_record.id),
                "conditions": conditions,
                "analysis": analysis_result,
                "original_memo": memo_record.original_memo,
                "refined_memo": memo_record.refined_memo,
                "customer_data": customer_data,
                "analyzed_at": analysis_record.created_at.isoformat()
            }
            
        except Exception as e:
            raise Exception(f"조건부 분석 중 오류가 발생했습니다: {str(e)}")
    
    async def perform_conditional_analysis(self, 
                                         refined_memo: Dict[str, Any], 
                                         conditions: Dict[str, Any]) -> str:
        """
        정제된 메모와 조건을 바탕으로 LLM 분석을 수행합니다.
        """
        try:
            # 조건에서 주요 정보 추출
            customer_type = conditions.get("customer_type", "일반")
            contract_status = conditions.get("contract_status", "활성")
            
            # 정제된 메모를 텍스트로 변환
            refined_memo_text = f"""
요약: {refined_memo.get('summary', '')}
키워드: {', '.join(refined_memo.get('keywords', []))}
고객 상태: {refined_memo.get('customer_status', '')}
필요 조치: {', '.join(refined_memo.get('required_actions', []))}
"""
            
            # 분석 프롬프트
            analysis_prompt = f"""고객 정보와 메모를 분석하여 적절한 대응 방안을 제시하세요.

고객 유형: {customer_type}
계약 상태: {contract_status}
정제된 메모: {refined_memo_text}

다음 관점에서 종합적으로 분석해주세요:
1. 고객의 현재 상황과 니즈 파악
2. 고객 유형과 계약 상태를 고려한 맞춤형 대응 방안
3. 우선순위가 높은 조치사항
4. 추가로 확인이 필요한 정보
5. 예상되는 고객 만족도 및 위험 요소

분석 결과를 구체적이고 실행 가능한 형태로 제시하세요."""
            
            # Azure OpenAI API 호출
            response = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "당신은 보험업계 전문가입니다."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"조건부 분석 수행 중 오류가 발생했습니다: {str(e)}")
    
    async def save_analysis_to_db(self, 
                                 memo_id: uuid.UUID, 
                                 conditions: Dict[str, Any], 
                                 analysis: str, 
                                 db_session: AsyncSession) -> AnalysisResult:
        """
        분석 결과를 데이터베이스에 저장합니다.
        """
        try:
            # 데이터베이스 모델 생성
            analysis_record = AnalysisResult(
                id=uuid.uuid4(),
                memo_id=memo_id,
                conditions=conditions,
                analysis=analysis
            )
            
            # 데이터베이스에 저장
            db_session.add(analysis_record)
            await db_session.commit()
            await db_session.refresh(analysis_record)
            
            return analysis_record
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"분석 결과 저장 중 오류가 발생했습니다: {str(e)}")
    
    async def get_memo_with_analyses(self, 
                                   memo_id: str, 
                                   db_session: AsyncSession) -> Dict[str, Any]:
        """
        메모와 관련된 모든 분석 결과를 조회합니다.
        """
        try:
            # 메모 조회 (분석 결과 포함)
            stmt = select(CustomerMemo).where(CustomerMemo.id == uuid.UUID(memo_id))
            result = await db_session.execute(stmt)
            memo_record = result.scalar_one_or_none()
            
            if not memo_record:
                raise Exception(f"메모 ID {memo_id}를 찾을 수 없습니다.")
            
            # 관련 분석 결과들 조회
            analysis_stmt = select(AnalysisResult).where(AnalysisResult.memo_id == memo_record.id)
            analysis_result = await db_session.execute(analysis_stmt)
            analyses = analysis_result.scalars().all()
            
            return {
                "memo_id": str(memo_record.id),
                "original_memo": memo_record.original_memo,
                "refined_memo": memo_record.refined_memo,
                "created_at": memo_record.created_at.isoformat(),
                "analyses": [
                    {
                        "analysis_id": str(analysis.id),
                        "conditions": analysis.conditions,
                        "analysis": analysis.analysis,
                        "analyzed_at": analysis.created_at.isoformat()
                    }
                    for analysis in analyses
                ]
            }
            
        except Exception as e:
            raise Exception(f"메모 및 분석 결과 조회 중 오류가 발생했습니다: {str(e)}")
    
    async def quick_save_memo(self, 
                             customer_id: str, 
                             content: str, 
                             db_session: AsyncSession,
                             author: Optional[str] = None) -> Dict[str, Any]:
        """
        빠른 메모 저장 - AI 정제 없이 원본 메모만 저장 (draft 상태)
        """
        try:
            # 데이터베이스 모델 생성 (draft 상태)
            memo_record = CustomerMemo(
                id=uuid.uuid4(),
                customer_id=customer_id,
                original_memo=content,
                refined_memo=None,  # 정제되지 않은 상태
                status="draft",
                author=author
            )
            
            # 데이터베이스에 저장
            db_session.add(memo_record)
            await db_session.commit()
            await db_session.refresh(memo_record)
            
            return {
                "memo_id": str(memo_record.id),
                "customer_id": memo_record.customer_id,
                "content": memo_record.original_memo,
                "status": memo_record.status,
                "saved_at": memo_record.created_at.isoformat()
            }
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"빠른 메모 저장 중 오류가 발생했습니다: {str(e)}")
    
    def _calculate_age(self, birth_date) -> Optional[int]:
        """
        생년월일로부터 나이를 계산합니다.
        """
        if not birth_date:
            return None
        
        from datetime import date
        today = date.today()
        
        if hasattr(birth_date, 'date'):
            birth_date = birth_date.date()
        elif isinstance(birth_date, str):
            try:
                birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except:
                return None
        
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    async def perform_enhanced_conditional_analysis(self, 
                                                  refined_memo: Dict[str, Any], 
                                                  conditions: Dict[str, Any],
                                                  customer_data: Optional[Dict[str, Any]] = None) -> str:
        """
        고객 데이터를 포함한 향상된 조건부 분석을 수행합니다.
        """
        try:
            logger.info("향상된 조건부 분석 시작")
            
            # 조건에서 주요 정보 추출
            customer_type = conditions.get("customer_type", "일반")
            contract_status = conditions.get("contract_status", "활성")
            analysis_focus = conditions.get("analysis_focus", ["종합분석"])
            
            # 정제된 메모를 텍스트로 변환
            refined_memo_text = f"""
요약: {refined_memo.get('summary', '')}
키워드: {', '.join(refined_memo.get('keywords', []))}
고객 상태: {refined_memo.get('status', '')}
필요 조치: {', '.join(refined_memo.get('required_actions', []))}
보험 정보: {refined_memo.get('insurance_info', {})}
시간 표현: {refined_memo.get('time_expressions', [])}
"""
            
            # 고객 정보 텍스트 구성
            customer_info_text = "고객 정보 없음"
            if customer_data:
                customer_info_text = f"""
고객명: {customer_data.get('name', '미상')}
나이: {customer_data.get('age', '미상')}세
성별: {customer_data.get('gender', '미상')}
관심사: {', '.join(customer_data.get('interests', []))}
인생 이벤트: {customer_data.get('life_events', [])}
보험 가입 현황: {customer_data.get('insurance_products', [])}
"""
            
            # 향상된 분석 프롬프트
            analysis_prompt = f"""당신은 보험업계의 전문 분석가입니다. 다음 정보를 종합하여 맞춤형 분석을 제공하세요.

=== 고객 정보 ===
{customer_info_text}

=== 메모 분석 내용 ===
{refined_memo_text}

=== 분석 조건 ===
고객 유형: {customer_type}
계약 상태: {contract_status}
분석 포커스: {', '.join(analysis_focus)}

=== 분석 요청 사항 ===
다음 관점에서 종합적으로 분석해주세요:

1. **고객 프로필 분석**
   - 현재 고객의 인생 단계와 니즈 파악
   - 메모 내용과 고객 정보의 일치성 검토
   - 잠재적 위험 요소 및 기회 식별

2. **맞춤형 대응 전략**
   - 고객 유형과 특성을 고려한 커뮤니케이션 방식
   - 개인화된 상품 추천 및 서비스 제안
   - 고객 만족도 향상을 위한 구체적 액션

3. **우선순위 및 타이밍**
   - 즉시 처리가 필요한 사항
   - 중장기적 관리 방안
   - 최적의 접촉 시점과 방법

4. **위험 관리**
   - 고객 이탈 위험 평가
   - 컴플라이언스 및 규정 준수 체크
   - 예상되는 문제점과 해결 방안

5. **성과 측정**
   - 분석 결과의 실행 가능성 평가
   - 성공 지표 및 KPI 제안
   - 후속 조치 및 모니터링 계획

분석 결과는 실무진이 바로 활용할 수 있도록 구체적이고 실행 가능한 형태로 제시하세요."""

            # LangChain 클라이언트 사용 (LangSmith 자동 추적)
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content="당신은 20년 경력의 보험업계 전문 분석가입니다. 고객 데이터와 메모를 종합하여 실무진에게 유용한 인사이트를 제공합니다."),
                HumanMessage(content=analysis_prompt)
            ]
            
            response = await self.llm_client.ainvoke(messages)
            analysis_result = response.content
            
            logger.info("향상된 조건부 분석 완료")
            return analysis_result
            
        except Exception as e:
            logger.error(f"향상된 조건부 분석 중 오류: {str(e)}")
            raise Exception(f"향상된 조건부 분석 수행 중 오류가 발생했습니다: {str(e)}")
    
    async def get_customer_analytics(self, customer_id: str, db_session: AsyncSession) -> Dict[str, Any]:
        """
        특정 고객의 분석 통계를 조회합니다.
        """
        try:
            # 고객 정보 조회
            customer_stmt = select(Customer).where(Customer.customer_id == uuid.UUID(customer_id))
            customer_result = await db_session.execute(customer_stmt)
            customer = customer_result.scalar_one_or_none()
            
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")
            
            # 고객의 메모 통계
            memo_stmt = select(CustomerMemo).where(CustomerMemo.customer_id == customer.customer_id)
            memo_result = await db_session.execute(memo_stmt)
            memos = memo_result.scalars().all()
            
            # 분석 결과 통계
            analysis_stmt = select(AnalysisResult).join(CustomerMemo).where(CustomerMemo.customer_id == customer.customer_id)
            analysis_result = await db_session.execute(analysis_stmt)
            analyses = analysis_result.scalars().all()
            
            # 통계 계산
            total_memos = len(memos)
            refined_memos = len([m for m in memos if m.status == "refined"])
            total_analyses = len(analyses)
            
            # 최근 활동
            recent_memo = max(memos, key=lambda x: x.created_at) if memos else None
            recent_analysis = max(analyses, key=lambda x: x.created_at) if analyses else None
            
            return {
                "customer_id": str(customer.customer_id),
                "customer_name": customer.name,
                "statistics": {
                    "total_memos": total_memos,
                    "refined_memos": refined_memos,
                    "total_analyses": total_analyses,
                    "refinement_rate": refined_memos / total_memos if total_memos > 0 else 0
                },
                "recent_activity": {
                    "last_memo_date": recent_memo.created_at.isoformat() if recent_memo else None,
                    "last_analysis_date": recent_analysis.created_at.isoformat() if recent_analysis else None
                },
                "customer_profile": {
                    "age": self._calculate_age(customer.date_of_birth),
                    "interests_count": len(customer.interests or []),
                    "insurance_products_count": len(customer.insurance_products or [])
                }
            }
            
        except Exception as e:
            raise Exception(f"고객 분석 통계 조회 중 오류가 발생했습니다: {str(e)}")
    
    async def _save_prompt_test_log(self, 
                                   prompt_content: str,
                                   memo_content: str, 
                                   llm_response: str,
                                   response_time_ms: int,
                                   success: bool = True,
                                   error_message: str = None,
                                   db_session: AsyncSession = None) -> None:
        """
        프롬프트 테스트 로그를 데이터베이스에 저장합니다.
        """
        if not db_session:
            return
            
        try:
            log_record = PromptTestLog(
                prompt_content=prompt_content,
                memo_content=memo_content,
                llm_response=llm_response,
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message,
                source="api_direct"  # /api/memo/refine에서 호출
            )
            
            db_session.add(log_record)
            await db_session.commit()
            
            logger.info(f"프롬프트 테스트 로그 저장 완료 (ID: {log_record.id})")
            
        except Exception as e:
            logger.error(f"프롬프트 테스트 로그 저장 실패: {e}")
            await db_session.rollback()