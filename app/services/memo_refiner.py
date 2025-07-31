import os
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseOutputParser
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db_models import CustomerMemo
import json
import re
import uuid


class RefinedMemoOutput(BaseModel):
    summary: str = Field(description="메모의 핵심 내용을 한 문장으로 요약")
    keywords: List[str] = Field(description="메모에서 추출한 주요 키워드들")
    customer_status: str = Field(description="고객의 현재 상황이나 감정 상태")
    required_actions: List[str] = Field(description="필요한 조치사항들")


class MemoRefinementParser(BaseOutputParser):
    def __init__(self):
        self.pydantic_parser = PydanticOutputParser(pydantic_object=RefinedMemoOutput)
    
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            # Try Pydantic parser first
            parsed = self.pydantic_parser.parse(text)
            return parsed.dict()
        except:
            # Fallback to manual parsing
            lines = text.strip().split('\n')
            result = {
                "summary": "",
                "keywords": [],
                "customer_status": "",
                "required_actions": []
            }
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('- 요약:'):
                    result["summary"] = line.replace('- 요약:', '').strip()
                elif line.startswith('요약:'):
                    result["summary"] = line.replace('요약:', '').strip()
                elif line.startswith('- 주요 키워드:'):
                    keywords_text = line.replace('- 주요 키워드:', '').strip()
                    result["keywords"] = [k.strip() for k in keywords_text.split(',') if k.strip()]
                elif line.startswith('주요 키워드:'):
                    keywords_text = line.replace('주요 키워드:', '').strip()
                    result["keywords"] = [k.strip() for k in keywords_text.split(',') if k.strip()]
                elif line.startswith('- 고객 상태:'):
                    result["customer_status"] = line.replace('- 고객 상태:', '').strip()
                elif line.startswith('고객 상태:'):
                    result["customer_status"] = line.replace('고객 상태:', '').strip()
                elif line.startswith('- 필요 조치:'):
                    actions_text = line.replace('- 필요 조치:', '').strip()
                    if actions_text:
                        result["required_actions"] = [a.strip() for a in actions_text.split(',') if a.strip()]
                elif line.startswith('필요 조치:'):
                    actions_text = line.replace('필요 조치:', '').strip()
                    if actions_text:
                        result["required_actions"] = [a.strip() for a in actions_text.split(',') if a.strip()]
            
            return result


class MemoRefinerService:
    def __init__(self):
        # GPT-4 모델 설정 - PROJECT_CONTEXT.md에 따라 최적화
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.1,  # 일관된 출력을 위해 낮은 온도 설정
            max_tokens=1000,  # 충분한 출력 길이 보장
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # OpenAI 임베딩 모델 설정 (pgvector용)
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # PROJECT_CONTEXT.md의 프롬프트 템플릿 정확히 적용
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """당신은 보험회사의 고객 메모를 정제하는 전문가입니다.
다음 고객 메모를 구조화된 형태로 정제해주세요:

입력 메모: {memo}

다음 형식으로 출력하세요:
- 요약: [메모의 핵심 내용을 한 문장으로 명확하게 요약]
- 주요 키워드: [키워드1, 키워드2, 키워드3] (중요한 키워드들을 쉼표로 구분)
- 고객 상태: [고객의 현재 상황, 감정 상태, 니즈 등을 파악하여 기술]
- 필요 조치: [고객 대응을 위해 필요한 구체적인 조치사항들] (쉼표로 구분)

보험업계 전문용어와 고객 서비스 관점에서 분석하여 정확하고 유용한 정보를 제공하세요."""),
            ("human", "{memo}")
        ])
        
        self.parser = MemoRefinementParser()
    
    async def refine_memo(self, memo: str) -> Dict[str, Any]:
        """
        LangChain을 사용하여 메모를 정제하는 메인 메서드
        """
        try:
            # LangChain 체인 구성: 프롬프트 -> LLM -> 파서
            chain = self.prompt_template | self.llm | self.parser
            
            # 비동기 실행
            result = await chain.ainvoke({"memo": memo})
            
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
            "keywords": result.get("keywords", []) or ["키워드 없음"],
            "customer_status": result.get("customer_status", "").strip() or "고객 상태 파악 필요",
            "required_actions": result.get("required_actions", []) or ["추가 분석 필요"]
        }
        
        # 키워드가 문자열인 경우 리스트로 변환
        if isinstance(validated["keywords"], str):
            validated["keywords"] = [k.strip() for k in validated["keywords"].split(',') if k.strip()]
        
        # 필요 조치가 문자열인 경우 리스트로 변환
        if isinstance(validated["required_actions"], str):
            validated["required_actions"] = [a.strip() for a in validated["required_actions"].split(',') if a.strip()]
        
        return validated
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        텍스트에 대한 임베딩 벡터를 생성합니다.
        """
        try:
            # 원본 메모와 정제된 요약을 결합하여 임베딩 생성
            embedding = await self.embeddings.aembed_query(text)
            return embedding
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