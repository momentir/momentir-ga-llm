"""
자연어 쿼리 의도 분류기 - KoNLPy 기반 한국어 NLP
"""
import re
import logging
from typing import List, Dict, Any, Optional, Union, Set
from typing_extensions import TypedDict, NotRequired
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

from langchain_core.output_parsers import BaseOutputParser
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field, ConfigDict

# KoNLPy 한국어 형태소 분석기
try:
    from konlpy.tag import Okt, Kkma, Hannanum
    KONLPY_AVAILABLE = True
except ImportError:
    KONLPY_AVAILABLE = False
    logging.warning("KoNLPy가 설치되지 않았습니다. 기본 패턴 매칭을 사용합니다.")

logger = logging.getLogger(__name__)


# TypedDict로 타입 안전성 보장
class EntityDict(TypedDict):
    """추출된 엔티티 정보 타입 정의"""
    customer_names: NotRequired[List[str]]
    dates: NotRequired[List[str]]
    product_names: NotRequired[List[str]]
    amounts: NotRequired[List[str]]
    locations: NotRequired[List[str]]
    keywords: NotRequired[List[str]]


class QueryTypeDict(TypedDict):
    """쿼리 타입 분류 결과 타입 정의"""
    main_type: str  # 'simple_query', 'filtering', 'aggregation', 'join'
    sub_type: NotRequired[str]
    confidence: float
    reasoning: str


class ClassificationResultDict(TypedDict):
    """분류 결과 전체 타입 정의"""
    query_type: QueryTypeDict
    entities: EntityDict
    morphemes: NotRequired[List[Dict[str, str]]]
    intent_keywords: List[str]
    complexity_score: float


class QueryType(str, Enum):
    """쿼리 타입 열거형"""
    SIMPLE_QUERY = "simple_query"      # 단순 조회: "고객 목록", "홍길동 정보"
    FILTERING = "filtering"            # 필터링: "30대 고객", "최근 1개월"
    AGGREGATION = "aggregation"        # 집계: "고객 수", "평균", "합계"
    JOIN = "join"                      # 조인: "고객과 상품", "메모와 이벤트"


class EntityType(str, Enum):
    """엔티티 타입 열거형"""
    CUSTOMER_NAME = "customer_name"
    DATE = "date"
    PRODUCT_NAME = "product_name"
    AMOUNT = "amount"
    LOCATION = "location"
    KEYWORD = "keyword"


@dataclass
class ExtractedEntity:
    """추출된 엔티티 정보"""
    text: str
    entity_type: EntityType
    start_pos: int
    end_pos: int
    confidence: float


class IntentClassificationResult(BaseModel):
    """Pydantic을 이용한 결과 검증 모델"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    query_type: QueryTypeDict
    entities: EntityDict
    morphemes: Optional[List[Dict[str, str]]] = None
    intent_keywords: List[str]
    complexity_score: float = Field(ge=0.0, le=1.0)


class IntentOutputParser(BaseOutputParser[ClassificationResultDict]):
    """LangChain OutputParser를 확장한 의도 분류 결과 파서"""
    
    def parse(self, text: str) -> ClassificationResultDict:
        """분류 결과를 파싱하여 TypedDict 형태로 반환"""
        try:
            # 기본 구조 생성
            result: ClassificationResultDict = {
                "query_type": {
                    "main_type": "simple_query",
                    "confidence": 0.5,
                    "reasoning": "기본 분류"
                },
                "entities": {},
                "intent_keywords": [],
                "complexity_score": 0.0
            }
            
            # JSON 형태의 text를 파싱하려고 시도
            import json
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    result.update(parsed)
            except json.JSONDecodeError:
                # JSON이 아닌 경우 기본값 사용
                pass
            
            return result
            
        except Exception as e:
            raise OutputParserException(f"의도 분류 결과 파싱 실패: {e}")
    
    def get_format_instructions(self) -> str:
        """파서가 기대하는 출력 형식 설명"""
        return """
결과를 다음 JSON 형식으로 반환해주세요:
{
    "query_type": {
        "main_type": "simple_query|filtering|aggregation|join",
        "sub_type": "선택사항",
        "confidence": 0.95,
        "reasoning": "분류 근거"
    },
    "entities": {
        "customer_names": ["홍길동"],
        "dates": ["2024-01-01", "최근 1개월"],
        "product_names": ["건강보험", "자동차보험"],
        "amounts": ["100만원", "50%"],
        "locations": ["서울", "강남구"],
        "keywords": ["가입", "해지", "조회"]
    },
    "intent_keywords": ["조회", "검색", "찾기"],
    "complexity_score": 0.7
}
"""


class KoreanIntentClassifier:
    """한국어 자연어 쿼리 의도 분류기"""
    
    def __init__(self, use_konlpy: bool = True):
        """
        분류기 초기화
        
        Args:
            use_konlpy: KoNLPy 사용 여부 (False면 패턴 매칭만 사용)
        """
        self.use_konlpy = use_konlpy and KONLPY_AVAILABLE
        
        # KoNLPy 형태소 분석기 초기화
        if self.use_konlpy:
            try:
                self.okt = Okt()  # 빠르고 정확한 형태소 분석
                self.kkma = None  # 필요시 사용 (느리지만 정확)
                logger.info("✅ KoNLPy Okt 형태소 분석기 초기화 완료")
            except Exception as e:
                logger.warning(f"KoNLPy 초기화 실패: {e}, 패턴 매칭 사용")
                self.use_konlpy = False
        
        # 의도 분류를 위한 키워드 패턴들
        self.query_patterns = {
            QueryType.SIMPLE_QUERY: [
                r'.*목록.*', r'.*정보.*', r'.*보여.*', r'.*알려.*', r'.*뭐.*', r'.*무엇.*',
                r'.*이름.*', r'.*연락처.*', r'.*주소.*', r'.*전화번호.*'
            ],
            QueryType.FILTERING: [
                r'.*조건.*', r'.*\d+세.*', r'.*\d+대.*', r'.*최근.*', r'.*지난.*', 
                r'.*이상.*', r'.*이하.*', r'.*포함.*', r'.*제외.*', r'.*해당.*'
            ],
            QueryType.AGGREGATION: [
                r'.*개수.*', r'.*수.*', r'.*총.*', r'.*평균.*', r'.*최대.*', r'.*최소.*',
                r'.*합계.*', r'.*통계.*', r'.*분석.*', r'.*비율.*', r'.*퍼센트.*'
            ],
            QueryType.JOIN: [
                r'.*와.*', r'.*과.*', r'.*관련.*', r'.*연결.*', r'.*함께.*', 
                r'.*매칭.*', r'.*결합.*', r'.*연관.*'
            ]
        }
        
        # 엔티티 추출 패턴들
        self.entity_patterns = {
            EntityType.CUSTOMER_NAME: [
                r'[가-힣]{2,4}(?:씨|님|고객|분)?',
                r'[가-힣]+\s*[가-힣]+'  # 성명 패턴
            ],
            EntityType.DATE: [
                r'\d{4}[-./]\d{1,2}[-./]\d{1,2}',
                r'\d{1,2}월\s*\d{1,2}일',
                r'최근\s*\d+\s*[일주월년]',
                r'지난\s*\d+\s*[일주월년]',
                r'오늘|어제|내일|이번주|지난주|다음주|이번달|지난달|다음달'
            ],
            EntityType.PRODUCT_NAME: [
                r'[가-힣]*보험',
                r'[가-힣]*상품',
                r'[가-힣]*플랜',
                r'건강보험|자동차보험|생명보험|화재보험|여행자보험'
            ],
            EntityType.AMOUNT: [
                r'\d+[만억]\s*원?',
                r'\d+\s*[원달러]',
                r'\d+\s*[%퍼센트]',
                r'\d+\s*개?'
            ],
            EntityType.LOCATION: [
                r'[가-힣]+[시도]',
                r'[가-힣]+[구군]',
                r'서울|부산|대구|인천|광주|대전|울산|세종',
                r'강남|서초|마포|종로|중구|영등포'
            ],
            EntityType.KEYWORD: [
                r'가입|해지|변경|조회|검색|찾기|확인|신청|취소|연장|갱신'
            ]
        }
        
        # 복잡도 점수 계산용 가중치
        self.complexity_weights = {
            'morpheme_count': 0.1,
            'entity_count': 0.2,
            'query_type': {
                QueryType.SIMPLE_QUERY: 0.1,
                QueryType.FILTERING: 0.3,
                QueryType.AGGREGATION: 0.6,
                QueryType.JOIN: 0.8
            },
            'special_keywords': 0.2
        }
        
        logger.info("✅ KoreanIntentClassifier 초기화 완료")
    
    async def classify(self, query: str) -> ClassificationResultDict:
        """
        자연어 쿼리를 분석하여 의도를 분류합니다.
        
        Args:
            query: 분류할 자연어 쿼리
            
        Returns:
            ClassificationResultDict: 분류 결과
        """
        try:
            logger.info(f"쿼리 의도 분류 시작: {query}")
            
            # 1. 전처리
            normalized_query = self._normalize_query(query)
            
            # 2. 형태소 분석 (KoNLPy 사용 시)
            morphemes = []
            if self.use_konlpy:
                morphemes = await self._analyze_morphemes(normalized_query)
            
            # 3. 쿼리 타입 분류
            query_type = self._classify_query_type(normalized_query, morphemes)
            
            # 4. 엔티티 추출
            entities = self._extract_entities(normalized_query)
            
            # 5. 의도 키워드 추출
            intent_keywords = self._extract_intent_keywords(normalized_query, morphemes)
            
            # 6. 복잡도 점수 계산
            complexity_score = self._calculate_complexity_score(
                normalized_query, morphemes, entities, query_type
            )
            
            # 7. 결과 조합
            result: ClassificationResultDict = {
                "query_type": query_type,
                "entities": entities,
                "intent_keywords": intent_keywords,
                "complexity_score": complexity_score
            }
            
            if morphemes:
                result["morphemes"] = morphemes
            
            logger.info(f"의도 분류 완료: {query_type['main_type']} (신뢰도: {query_type['confidence']:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"쿼리 의도 분류 실패: {e}")
            # 기본값 반환
            return {
                "query_type": {
                    "main_type": QueryType.SIMPLE_QUERY,
                    "confidence": 0.1,
                    "reasoning": f"분류 실패로 기본값 사용: {str(e)}"
                },
                "entities": {},
                "intent_keywords": [],
                "complexity_score": 0.1
            }
    
    def _normalize_query(self, query: str) -> str:
        """쿼리 전처리 및 정규화"""
        # 공백 정리
        normalized = re.sub(r'\s+', ' ', query.strip())
        
        # 특수문자 정리 (한글, 숫자, 기본 문장부호만 유지)
        normalized = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ.,!?%()-]', '', normalized)
        
        # 불필요한 존댓말 간소화
        replacements = [
            ('주세요', '줘'), ('해주세요', '해줘'), ('알려주세요', '알려줘'),
            ('보여주세요', '보여줘'), ('해주시겠어요', '해줘')
        ]
        
        for old, new in replacements:
            normalized = normalized.replace(old, new)
        
        return normalized
    
    async def _analyze_morphemes(self, query: str) -> List[Dict[str, str]]:
        """KoNLPy를 이용한 형태소 분석"""
        if not self.use_konlpy:
            return []
        
        try:
            # 비동기 처리를 위해 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            morphemes = await loop.run_in_executor(
                None, self.okt.pos, query, True, True
            )
            
            # 결과 변환
            result = []
            for word, pos in morphemes:
                result.append({
                    'word': word,
                    'pos': pos,
                    'meaning': self._get_pos_meaning(pos)
                })
            
            return result
            
        except Exception as e:
            logger.warning(f"형태소 분석 실패: {e}")
            return []
    
    def _get_pos_meaning(self, pos: str) -> str:
        """형태소 품사 태그의 의미를 반환"""
        pos_meanings = {
            'Noun': '명사', 'Verb': '동사', 'Adjective': '형용사',
            'Adverb': '부사', 'Josa': '조사', 'Eomi': '어미',
            'Modifier': '관형사', 'Number': '수사', 'Punctuation': '구두점'
        }
        return pos_meanings.get(pos, pos)
    
    def _classify_query_type(self, query: str, morphemes: List[Dict[str, str]]) -> QueryTypeDict:
        """쿼리 타입 분류"""
        scores = {}
        
        # 패턴 매칭으로 점수 계산
        for query_type, patterns in self.query_patterns.items():
            score = 0.0
            matched_patterns = []
            
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    score += 1.0
                    matched_patterns.append(pattern)
            
            # 형태소 정보가 있으면 추가 점수
            if morphemes:
                for morpheme in morphemes:
                    word = morpheme['word']
                    pos = morpheme['pos']
                    
                    if query_type == QueryType.AGGREGATION:
                        if pos == 'Noun' and any(kw in word for kw in ['수', '개수', '총', '평균']):
                            score += 0.5
                    elif query_type == QueryType.FILTERING:
                        if pos == 'Modifier' and any(kw in word for kw in ['최근', '지난', '특정']):
                            score += 0.5
                    elif query_type == QueryType.JOIN:
                        if pos == 'Josa' and word in ['와', '과', '랑']:
                            score += 0.5
            
            scores[query_type] = score / max(len(patterns), 1)  # 정규화
        
        # 최고 점수 쿼리 타입 선택
        if scores:
            best_type = max(scores, key=scores.get)
            confidence = min(scores[best_type], 1.0)
        else:
            best_type = QueryType.SIMPLE_QUERY
            confidence = 0.1
        
        # 추론 근거 생성
        reasoning_parts = []
        if confidence > 0.7:
            reasoning_parts.append(f"강한 패턴 매칭 ({confidence:.2f})")
        elif confidence > 0.4:
            reasoning_parts.append(f"중간 패턴 매칭 ({confidence:.2f})")
        else:
            reasoning_parts.append(f"약한 패턴 매칭 ({confidence:.2f})")
        
        if morphemes:
            reasoning_parts.append(f"형태소 분석 활용 ({len(morphemes)}개)")
        
        return {
            "main_type": best_type.value,
            "confidence": confidence,
            "reasoning": ", ".join(reasoning_parts)
        }
    
    def _extract_entities(self, query: str) -> EntityDict:
        """엔티티 추출"""
        entities: EntityDict = {}
        
        for entity_type, patterns in self.entity_patterns.items():
            extracted = []
            
            for pattern in patterns:
                matches = re.finditer(pattern, query)
                for match in matches:
                    text = match.group().strip()
                    if text and len(text) > 1:  # 너무 짧은 매칭 제외
                        extracted.append(text)
            
            # 중복 제거
            extracted = list(set(extracted))
            
            if extracted:
                # TypedDict 키 매핑
                if entity_type == EntityType.CUSTOMER_NAME:
                    entities["customer_names"] = extracted
                elif entity_type == EntityType.DATE:
                    entities["dates"] = extracted
                elif entity_type == EntityType.PRODUCT_NAME:
                    entities["product_names"] = extracted
                elif entity_type == EntityType.AMOUNT:
                    entities["amounts"] = extracted
                elif entity_type == EntityType.LOCATION:
                    entities["locations"] = extracted
                elif entity_type == EntityType.KEYWORD:
                    entities["keywords"] = extracted
        
        return entities
    
    def _extract_intent_keywords(self, query: str, morphemes: List[Dict[str, str]]) -> List[str]:
        """의도를 나타내는 핵심 키워드 추출"""
        keywords = set()
        
        # 기본 의도 키워드들
        intent_words = [
            '조회', '검색', '찾기', '보기', '확인', '알아보기',
            '가입', '해지', '변경', '신청', '취소', '연장',
            '분석', '통계', '비교', '계산', '합계', '평균'
        ]
        
        for word in intent_words:
            if word in query:
                keywords.add(word)
        
        # 형태소 분석 결과에서 동사, 명사 추출
        if morphemes:
            for morpheme in morphemes:
                word = morpheme['word']
                pos = morpheme['pos']
                
                if pos in ['Verb', 'Noun'] and len(word) >= 2:
                    # 의미 있는 동사, 명사만 선택
                    if any(intent in word for intent in intent_words):
                        keywords.add(word)
        
        return sorted(list(keywords))
    
    def _calculate_complexity_score(
        self, 
        query: str, 
        morphemes: List[Dict[str, str]], 
        entities: EntityDict, 
        query_type: QueryTypeDict
    ) -> float:
        """쿼리 복잡도 점수 계산 (0.0 ~ 1.0)"""
        score = 0.0
        
        # 1. 형태소 개수 기반 점수
        morpheme_score = min(len(morphemes) * self.complexity_weights['morpheme_count'], 0.3)
        
        # 2. 엔티티 개수 기반 점수  
        total_entities = sum(len(v) for v in entities.values() if isinstance(v, list))
        entity_score = min(total_entities * self.complexity_weights['entity_count'], 0.3)
        
        # 3. 쿼리 타입 기반 점수
        main_type = QueryType(query_type['main_type'])
        type_score = self.complexity_weights['query_type'][main_type]
        
        # 4. 특수 키워드 기반 점수
        special_keywords = ['그리고', '또는', '하지만', '포함', '제외', '조건']
        special_count = sum(1 for keyword in special_keywords if keyword in query)
        special_score = min(special_count * self.complexity_weights['special_keywords'], 0.2)
        
        # 총합 계산
        total_score = morpheme_score + entity_score + type_score + special_score
        
        return min(total_score, 1.0)


# 싱글톤 인스턴스
korean_intent_classifier = KoreanIntentClassifier()

# LangChain OutputParser 인스턴스  
intent_output_parser = IntentOutputParser()