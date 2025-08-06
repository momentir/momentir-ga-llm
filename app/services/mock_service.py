import random
from typing import Dict, Any, List
import uuid
import time
from datetime import datetime


class MockLLMService:
    """
    OpenAI API 호출을 모방하는 Mock 서비스
    실제 API 키 없이도 테스트 가능하도록 구현
    """
    
    def __init__(self):
        # 다양한 샘플 응답 템플릿
        self.sample_responses = [
            {
                "summary": "고객이 보험료 인상에 대해 문의하며 가족 구성원 변경을 고려 중임",
                "keywords": ["보험료 인상", "가족 구성원 변경", "문의"],
                "customer_status": "보험료 변경에 대한 정보가 필요한 상태",
                "required_actions": ["보험료 재계산", "가족 구성원 변경 절차 안내", "상담 예약"]
            },
            {
                "summary": "고객이 사고 처리 진행 상황에 대해 불만을 표시함",
                "keywords": ["사고 처리", "진행 상황", "불만", "처리 지연"],
                "customer_status": "사고 처리 지연으로 인해 불만족 상태",
                "required_actions": ["사고 처리 현황 확인", "담당자 연결", "보상 일정 안내"]
            },
            {
                "summary": "신규 보험 상품에 대한 문의 및 가입 의사 표명",
                "keywords": ["신규 보험", "상품 문의", "가입 의사", "상담"],
                "customer_status": "신규 보험 가입에 관심을 보이는 적극적 상태",
                "required_actions": ["상품 설명 자료 제공", "상담 일정 조율", "견적 산출"]
            },
            {
                "summary": "기존 계약 해지를 고려하며 환급금 관련 문의",
                "keywords": ["계약 해지", "환급금", "해약", "문의"],
                "customer_status": "계약 해지를 고려하는 상태로 환급금에 관심",
                "required_actions": ["해약 환급금 계산", "해지 절차 안내", "유지 방안 제안"]
            },
            {
                "summary": "보험금 청구 절차에 대한 문의 및 서류 준비 관련 질문",
                "keywords": ["보험금 청구", "절차 문의", "서류 준비", "청구"],
                "customer_status": "보험금 청구가 필요한 상황으로 절차 확인 중",
                "required_actions": ["청구 서류 안내", "접수 절차 설명", "담당 부서 연결"]
            }
        ]
    
    async def generate_mock_response(self, memo: str) -> Dict[str, Any]:
        """
        입력 메모를 기반으로 Mock 응답을 생성합니다.
        """
        # 인위적 지연 (실제 API 호출 시뮬레이션)
        await self._simulate_api_delay()
        
        # 메모 내용에 따른 응답 선택 로직
        response = self._select_response_by_memo(memo)
        
        return response
    
    def _select_response_by_memo(self, memo: str) -> Dict[str, Any]:
        """
        메모 내용을 분석하여 적절한 응답 선택
        """
        memo_lower = memo.lower()
        
        # 키워드 기반 응답 선택
        if any(keyword in memo_lower for keyword in ["보험료", "인상", "가족"]):
            return self.sample_responses[0]
        elif any(keyword in memo_lower for keyword in ["사고", "처리", "불만"]):
            return self.sample_responses[1]
        elif any(keyword in memo_lower for keyword in ["신규", "가입", "상품"]):
            return self.sample_responses[2]
        elif any(keyword in memo_lower for keyword in ["해지", "환급", "해약"]):
            return self.sample_responses[3]
        elif any(keyword in memo_lower for keyword in ["청구", "보험금", "서류"]):
            return self.sample_responses[4]
        else:
            # 기본 응답 (메모 내용을 반영한 동적 생성)
            return self._generate_dynamic_response(memo)
    
    def _generate_dynamic_response(self, memo: str) -> Dict[str, Any]:
        """
        메모 내용을 기반으로 동적 응답 생성
        """
        # 메모에서 키워드 추출 (간단한 로직)
        words = memo.split()
        keywords = [word for word in words if len(word) > 2][:3]
        
        return {
            "summary": f"고객이 {memo[:30]}... 관련하여 문의함",
            "keywords": keywords if keywords else ["고객 문의", "상담 필요"],
            "customer_status": "추가 정보가 필요한 상태",
            "required_actions": ["상황 파악", "적절한 담당자 연결", "후속 조치 계획"]
        }
    
    async def _simulate_api_delay(self):
        """API 호출 지연 시뮬레이션"""
        delay = random.uniform(0.5, 2.0)  # 0.5~2초 랜덤 지연
        time.sleep(delay)


class MockEmbeddingService:
    """
    OpenAI Embedding API를 모방하는 Mock 서비스
    """
    
    def __init__(self):
        self.embedding_dimension = 1536  # OpenAI text-embedding-ada-002 차원
    
    async def create_mock_embedding(self, text: str) -> List[float]:
        """
        텍스트에 대한 Mock 임베딩 벡터 생성
        """
        # 인위적 지연
        await self._simulate_api_delay()
        
        # 텍스트 해시를 기반으로 일관된 벡터 생성
        hash_value = hash(text)
        random.seed(hash_value)  # 같은 텍스트는 항상 같은 벡터 생성
        
        # 정규화된 랜덤 벡터 생성
        vector = [random.gauss(0, 1) for _ in range(self.embedding_dimension)]
        
        # L2 정규화
        magnitude = sum(x**2 for x in vector) ** 0.5
        normalized_vector = [x / magnitude for x in vector]
        
        return normalized_vector
    
    async def _simulate_api_delay(self):
        """API 호출 지연 시뮬레이션"""
        delay = random.uniform(0.3, 1.0)  # 0.3~1초 랜덤 지연
        time.sleep(delay)


class MockMemoRefinerService:
    """
    실제 MemoRefinerService의 Mock 버전
    """
    
    def __init__(self):
        self.llm_service = MockLLMService()
        self.embedding_service = MockEmbeddingService()
        print("🎭 Mock 모드로 실행 중 - OpenAI API 키가 필요하지 않습니다")
    
    async def refine_memo(self, memo: str) -> Dict[str, Any]:
        """Mock 메모 정제"""
        return await self.llm_service.generate_mock_response(memo)
    
    async def create_embedding(self, text: str) -> List[float]:
        """Mock 임베딩 생성"""
        return await self.embedding_service.create_mock_embedding(text)
    
    async def save_memo_to_db(self, 
                             original_memo: str, 
                             refined_data: Dict[str, Any], 
                             db_session) -> Any:
        """Mock 데이터베이스 저장"""
        # 실제 DB 모델 import 회피를 위한 Mock 객체
        class MockMemoRecord:
            def __init__(self):
                self.id = uuid.uuid4()
                self.original_memo = original_memo
                self.refined_memo = refined_data
                self.embedding = None  # 실제로는 임베딩 벡터
                self.created_at = datetime.now()
        
        # 임베딩 생성
        embedding_text = f"{original_memo} {refined_data.get('summary', '')}"
        embedding_vector = await self.create_embedding(embedding_text)
        
        # Mock 레코드 생성
        memo_record = MockMemoRecord()
        memo_record.embedding = embedding_vector
        
        # 실제 DB 저장 시뮬레이션
        await self._simulate_db_operation()
        
        return memo_record
    
    async def find_similar_memos(self, memo: str, db_session, limit: int = 5) -> List:
        """Mock 유사 메모 검색"""
        await self._simulate_db_operation()
        
        # Mock 유사 메모 생성 (실제로는 벡터 검색)
        similar_count = random.randint(0, 3)
        return ["mock_memo"] * similar_count
    
    async def refine_and_save_memo(self, memo: str, db_session) -> Dict[str, Any]:
        """Mock 통합 메모 처리"""
        # 1. 메모 정제
        refined_data = await self.refine_memo(memo)
        
        # 2. 데이터베이스에 저장
        memo_record = await self.save_memo_to_db(memo, refined_data, db_session)
        
        # 3. 유사한 메모 검색
        similar_memos = await self.find_similar_memos(memo, db_session, limit=3)
        
        return {
            "memo_id": str(memo_record.id),
            "refined_data": refined_data,
            "similar_memos_count": len(similar_memos),
            "created_at": memo_record.created_at.isoformat()
        }
    
    async def _simulate_db_operation(self):
        """데이터베이스 작업 시뮬레이션"""
        delay = random.uniform(0.1, 0.5)
        time.sleep(delay)