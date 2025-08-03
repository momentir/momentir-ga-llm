import os
from typing import Dict, Any, List, Optional
import openai
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db_models import CustomerMemo, AnalysisResult
import json
import re
import uuid


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
            import json
            import re
            
            # Extract JSON from the response if it's wrapped in text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                parsed_json = json.loads(json_text)
                
                # Validate and convert to our expected format
                result = {
                    "summary": parsed_json.get("summary", ""),
                    "status": parsed_json.get("status", ""),
                    "keywords": parsed_json.get("keywords", []),
                    "time_expressions": parsed_json.get("time_expressions", []),
                    "required_actions": parsed_json.get("required_actions", []),
                    "insurance_info": parsed_json.get("insurance_info", {})
                }
                return result
        except:
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


class MemoRefinerService:
    def __init__(self):
        # OpenAI 클라이언트 설정
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 시스템 프롬프트 정의
        self.system_prompt = """당신은 보험회사의 고객 메모를 분석하는 전문가입니다.
다음 고객 메모에서 중요한 정보를 추출해주세요:

다음 정보를 추출하세요:
1. 고객 상태/감정
2. 주요 키워드 (관심사, 니즈)
3. 시간 관련 표현 (예: "2주 후", "다음 달", "내일", "곧")
4. 필요한 후속 조치
5. 보험 관련 정보 (상품명, 보험료, 관심 상품)

출력은 반드시 다음 JSON 형식으로 제공하세요:
{
  "summary": "메모의 핵심 내용을 한 문장으로 요약",
  "status": "고객의 현재 상태/감정",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "time_expressions": [{
    "expression": "원본 시간 표현",
    "parsed_date": "YYYY-MM-DD 형식 (파싱 가능한 경우)"
  }],
  "required_actions": ["조치1", "조치2"],
  "insurance_info": {
    "products": ["언급된 보험상품"],
    "premium_amount": "보험료 금액",
    "interest_products": ["관심 상품"],
    "policy_changes": ["정책 변경사항"]
  }
}

시간 표현 파싱 규칙:
- "2주 후" → 현재 날짜 + 14일
- "다음 달" → 다음 달 1일
- "내일" → 현재 날짜 + 1일
- 구체적 날짜는 그대로 활용

보험업계 전문용어와 고객 서비스 관점에서 정확하게 분석하세요."""
        
        self.parser = MemoRefinementParser()
    
    async def refine_memo(self, memo: str) -> Dict[str, Any]:
        """
        OpenAI를 사용하여 메모를 정제하는 메인 메서드
        """
        try:
            # OpenAI API 호출
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"메모: {memo}"}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # 응답 텍스트 추출
            result_text = response.choices[0].message.content
            
            # 파서를 통해 결과 파싱
            result = self.parser.parse(result_text)
            
            # 결과 검증 및 기본값 설정
            validated_result = self._validate_result(result)
            
            return validated_result
            
        except Exception as e:
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
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        텍스트에 대한 임베딩 벡터를 생성합니다.
        """
        try:
            # OpenAI 임베딩 API 호출
            response = await self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"임베딩 생성 중 오류가 발생했습니다: {str(e)}")
    
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
            
            # 데이터베이스 모델 생성
            memo_record = CustomerMemo(
                id=uuid.uuid4(),
                original_memo=original_memo,
                refined_memo=refined_data,
                status="refined",
                embedding=embedding_vector
            )
            
            # 데이터베이스에 저장
            db_session.add(memo_record)
            await db_session.commit()
            await db_session.refresh(memo_record)
            
            return memo_record
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"메모 저장 중 오류가 발생했습니다: {str(e)}")
    
    async def find_similar_memos(self, 
                                memo: str, 
                                db_session: AsyncSession, 
                                limit: int = 5) -> List[CustomerMemo]:
        """
        유사한 메모를 벡터 검색으로 찾습니다.
        """
        try:
            # 입력 메모의 임베딩 생성
            query_embedding = await self.create_embedding(memo)
            
            # pgvector를 사용한 유사도 검색
            stmt = select(CustomerMemo).order_by(
                CustomerMemo.embedding.cosine_distance(query_embedding)
            ).limit(limit)
            
            result = await db_session.execute(stmt)
            similar_memos = result.scalars().all()
            
            return similar_memos
            
        except Exception as e:
            raise Exception(f"유사 메모 검색 중 오류가 발생했습니다: {str(e)}")
    
    async def refine_and_save_memo(self, 
                                  memo: str, 
                                  db_session: AsyncSession) -> Dict[str, Any]:
        """
        메모를 정제하고 데이터베이스에 저장하는 통합 메서드
        """
        try:
            # 1. 메모 정제
            refined_data = await self.refine_memo(memo)
            
            # 2. 데이터베이스에 저장
            memo_record = await self.save_memo_to_db(memo, refined_data, db_session)
            
            # 3. 유사한 메모 검색 (선택적)
            similar_memos = await self.find_similar_memos(memo, db_session, limit=3)
            
            return {
                "memo_id": str(memo_record.id),
                "refined_data": refined_data,
                "similar_memos_count": len(similar_memos),
                "created_at": memo_record.created_at.isoformat()
            }
            
        except Exception as e:
            raise Exception(f"메모 정제 및 저장 중 오류가 발생했습니다: {str(e)}")
    
    async def analyze_memo_with_conditions(self, 
                                         memo_id: str, 
                                         conditions: Dict[str, Any], 
                                         db_session: AsyncSession) -> Dict[str, Any]:
        """
        기존 메모를 조건에 따라 분석합니다.
        """
        try:
            # 1. 메모 조회
            stmt = select(CustomerMemo).where(CustomerMemo.id == uuid.UUID(memo_id))
            result = await db_session.execute(stmt)
            memo_record = result.scalar_one_or_none()
            
            if not memo_record:
                raise Exception(f"메모 ID {memo_id}를 찾을 수 없습니다.")
            
            # 2. 조건부 분석 수행
            analysis_result = await self.perform_conditional_analysis(
                refined_memo=memo_record.refined_memo,
                conditions=conditions
            )
            
            # 3. 분석 결과를 데이터베이스에 저장
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
            
            # OpenAI API 호출
            response = await self.client.chat.completions.create(
                model="gpt-4",
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