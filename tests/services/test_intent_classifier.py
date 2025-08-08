"""
Intent Classifier 테스트 케이스
"""
import pytest
import asyncio
from typing import Dict, Any

from app.services.intent_classifier import (
    KoreanIntentClassifier, IntentOutputParser, QueryType,
    ClassificationResultDict, QueryTypeDict, EntityDict,
    intent_output_parser, korean_intent_classifier
)


class TestKoreanIntentClassifier:
    """한국어 의도 분류기 테스트"""
    
    @pytest.fixture
    def classifier(self):
        """분류기 인스턴스 픽스처"""
        return KoreanIntentClassifier(use_konlpy=False)  # 테스트에서는 패턴 매칭만 사용
    
    @pytest.mark.asyncio
    async def test_simple_query_classification(self, classifier):
        """단순 조회 쿼리 분류 테스트"""
        query = "고객 목록을 보여주세요"
        
        result = await classifier.classify(query)
        
        assert result["query_type"]["main_type"] == QueryType.SIMPLE_QUERY
        assert result["query_type"]["confidence"] > 0.0
        # 키워드 또는 엔티티가 적절히 추출되었는지 확인
        has_keywords = len(result["intent_keywords"]) > 0 or len(result["entities"]) > 0
        assert has_keywords
        assert result["complexity_score"] >= 0.0
    
    @pytest.mark.asyncio
    async def test_filtering_query_classification(self, classifier):
        """필터링 쿼리 분류 테스트"""
        query = "30대 고객들을 찾아주세요"
        
        result = await classifier.classify(query)
        
        assert result["query_type"]["main_type"] == QueryType.FILTERING
        assert result["query_type"]["confidence"] > 0.0
        assert result["complexity_score"] > 0.1
    
    @pytest.mark.asyncio
    async def test_aggregation_query_classification(self, classifier):
        """집계 쿼리 분류 테스트"""
        query = "고객 수를 세어주세요"
        
        result = await classifier.classify(query)
        
        assert result["query_type"]["main_type"] == QueryType.AGGREGATION
        assert result["query_type"]["confidence"] > 0.0
        assert "수" in str(result)
    
    @pytest.mark.asyncio
    async def test_join_query_classification(self, classifier):
        """조인 쿼리 분류 테스트"""
        query = "고객과 관련된 상품 정보를 보여주세요"
        
        result = await classifier.classify(query)
        
        assert result["query_type"]["main_type"] == QueryType.JOIN
        assert result["query_type"]["confidence"] > 0.0
        assert result["complexity_score"] > 0.3
    
    @pytest.mark.asyncio
    async def test_customer_name_entity_extraction(self, classifier):
        """고객명 엔티티 추출 테스트"""
        query = "홍길동님의 정보를 보여주세요"
        
        result = await classifier.classify(query)
        
        assert "customer_names" in result["entities"]
        customer_names = result["entities"]["customer_names"]
        assert any("홍길동" in name for name in customer_names)
    
    @pytest.mark.asyncio
    async def test_date_entity_extraction(self, classifier):
        """날짜 엔티티 추출 테스트"""
        query = "최근 30일 동안의 가입 고객을 보여주세요"
        
        result = await classifier.classify(query)
        
        assert "dates" in result["entities"]
        dates = result["entities"]["dates"]
        assert any("30일" in date for date in dates)
    
    @pytest.mark.asyncio
    async def test_product_name_entity_extraction(self, classifier):
        """상품명 엔티티 추출 테스트"""
        query = "자동차보험 가입 고객 목록"
        
        result = await classifier.classify(query)
        
        assert "product_names" in result["entities"]
        products = result["entities"]["product_names"]
        assert any("자동차보험" in product for product in products)
    
    @pytest.mark.asyncio
    async def test_amount_entity_extraction(self, classifier):
        """금액/수량 엔티티 추출 테스트"""
        query = "100만원 이상 보험료를 낸 고객들"
        
        result = await classifier.classify(query)
        
        assert "amounts" in result["entities"]
        amounts = result["entities"]["amounts"]
        assert any("100만원" in amount for amount in amounts)
    
    @pytest.mark.asyncio
    async def test_location_entity_extraction(self, classifier):
        """지역 엔티티 추출 테스트"""
        query = "서울 강남구 거주 고객들"
        
        result = await classifier.classify(query)
        
        assert "locations" in result["entities"]
        locations = result["entities"]["locations"]
        assert any("서울" in loc or "강남" in loc for loc in locations)
    
    @pytest.mark.asyncio
    async def test_keyword_entity_extraction(self, classifier):
        """키워드 엔티티 추출 테스트"""
        query = "보험 가입을 신청한 고객들"
        
        result = await classifier.classify(query)
        
        assert "keywords" in result["entities"] or len(result["intent_keywords"]) > 0
        # 가입이나 신청 관련 키워드가 포함되어야 함
    
    @pytest.mark.asyncio
    async def test_complex_query_with_multiple_entities(self, classifier):
        """복합 엔티티가 포함된 복잡한 쿼리 테스트"""
        query = "홍길동님이 지난달에 가입한 자동차보험 상품 정보와 100만원 이상 보험료 내역을 서울 지역 기준으로 분석해주세요"
        
        result = await classifier.classify(query)
        
        # 여러 엔티티 타입이 추출되어야 함
        entities = result["entities"]
        assert len(entities) >= 3  # 고객명, 날짜, 상품명 등
        
        # 복잡도 점수가 높아야 함
        assert result["complexity_score"] > 0.5
        
        # 복잡한 쿼리이므로 SIMPLE_QUERY가 아니어야 함
        assert result["query_type"]["main_type"] != QueryType.SIMPLE_QUERY
    
    @pytest.mark.asyncio
    async def test_empty_query(self, classifier):
        """빈 쿼리 처리 테스트"""
        query = ""
        
        result = await classifier.classify(query)
        
        assert result["query_type"]["main_type"] == QueryType.SIMPLE_QUERY
        assert result["query_type"]["confidence"] < 0.5
        assert result["complexity_score"] < 0.2
    
    @pytest.mark.asyncio
    async def test_special_characters_query(self, classifier):
        """특수문자가 포함된 쿼리 테스트"""
        query = "고객!@#$%^&*()_+ 정보를 보여주세요???"
        
        result = await classifier.classify(query)
        
        # 전처리가 정상적으로 되어야 함
        assert result["query_type"]["main_type"] == QueryType.SIMPLE_QUERY
        assert result["query_type"]["confidence"] > 0.0
    
    @pytest.mark.asyncio
    async def test_morpheme_analysis_availability(self, classifier):
        """형태소 분석 가용성 테스트"""
        query = "고객들의 평균 나이를 계산해주세요"
        
        result = await classifier.classify(query)
        
        # KoNLPy 없이도 작동해야 함
        assert "query_type" in result
        assert "entities" in result
        assert "intent_keywords" in result
        assert "complexity_score" in result
    
    def test_query_normalization(self, classifier):
        """쿼리 정규화 테스트"""
        original_query = "   고객   정보를   보여주세요!!!   "
        normalized = classifier._normalize_query(original_query)
        
        assert normalized.strip() == normalized
        assert "  " not in normalized  # 연속 공백 제거
        assert "보여줘" in normalized  # 존댓말 간소화
    
    def test_complexity_score_calculation(self, classifier):
        """복잡도 점수 계산 테스트"""
        simple_query = "고객 목록"
        complex_query = "홍길동님의 최근 3개월간 자동차보험과 건강보험 가입 내역을 분석하여 평균 보험료를 계산해주세요"
        
        # 간단한 쿼리
        simple_entities: EntityDict = {}
        simple_type: QueryTypeDict = {
            "main_type": QueryType.SIMPLE_QUERY,
            "confidence": 0.8,
            "reasoning": "test"
        }
        simple_score = classifier._calculate_complexity_score(
            simple_query, [], simple_entities, simple_type
        )
        
        # 복잡한 쿼리
        complex_entities: EntityDict = {
            "customer_names": ["홍길동"],
            "dates": ["최근 3개월"],
            "product_names": ["자동차보험", "건강보험"]
        }
        complex_type: QueryTypeDict = {
            "main_type": QueryType.AGGREGATION,
            "confidence": 0.9,
            "reasoning": "test"
        }
        complex_score = classifier._calculate_complexity_score(
            complex_query, [], complex_entities, complex_type
        )
        
        assert complex_score > simple_score
        assert 0.0 <= simple_score <= 1.0
        assert 0.0 <= complex_score <= 1.0


class TestIntentOutputParser:
    """IntentOutputParser 테스트"""
    
    def test_parse_valid_json(self):
        """유효한 JSON 파싱 테스트"""
        json_text = '''
        {
            "query_type": {
                "main_type": "simple_query",
                "confidence": 0.95,
                "reasoning": "단순 조회 패턴"
            },
            "entities": {
                "customer_names": ["홍길동"]
            },
            "intent_keywords": ["조회"],
            "complexity_score": 0.3
        }
        '''
        
        result = intent_output_parser.parse(json_text)
        
        assert result["query_type"]["main_type"] == "simple_query"
        assert result["query_type"]["confidence"] == 0.95
        assert "customer_names" in result["entities"]
        assert "조회" in result["intent_keywords"]
        assert result["complexity_score"] == 0.3
    
    def test_parse_invalid_json(self):
        """유효하지 않은 JSON 파싱 테스트"""
        invalid_text = "이것은 JSON이 아닙니다"
        
        result = intent_output_parser.parse(invalid_text)
        
        # 기본값이 반환되어야 함
        assert result["query_type"]["main_type"] == "simple_query"
        assert result["query_type"]["confidence"] == 0.5
        assert "entities" in result
        assert "intent_keywords" in result
        assert "complexity_score" in result
    
    def test_format_instructions(self):
        """포맷 지시사항 테스트"""
        instructions = intent_output_parser.get_format_instructions()
        
        assert "JSON" in instructions
        assert "query_type" in instructions
        assert "entities" in instructions
        assert "confidence" in instructions


class TestIntegrationWithKoNLPy:
    """KoNLPy 통합 테스트 (KoNLPy 설치된 경우만 실행)"""
    
    @pytest.fixture
    def konlpy_classifier(self):
        """KoNLPy를 사용하는 분류기"""
        return KoreanIntentClassifier(use_konlpy=True)
    
    @pytest.mark.asyncio
    async def test_morpheme_analysis_with_konlpy(self, konlpy_classifier):
        """KoNLPy 형태소 분석 테스트"""
        if not konlpy_classifier.use_konlpy:
            pytest.skip("KoNLPy가 설치되지 않음")
        
        query = "고객들의 정보를 조회해주세요"
        
        result = await konlpy_classifier.classify(query)
        
        # 형태소 분석 결과가 포함되어야 함
        assert "morphemes" in result
        if result["morphemes"]:
            assert len(result["morphemes"]) > 0
            assert all("word" in m and "pos" in m for m in result["morphemes"])


@pytest.mark.asyncio 
async def test_singleton_instance():
    """싱글톤 인스턴스 테스트"""
    query = "테스트 쿼리"
    
    result = await korean_intent_classifier.classify(query)
    
    assert "query_type" in result
    assert "entities" in result
    assert isinstance(result, dict)