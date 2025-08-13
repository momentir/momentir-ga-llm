"""
검색 결과 포맷팅 서비스

검색어 하이라이팅, 페이지네이션, 결과 요약 생성 등
검색 결과를 사용자 친화적으로 포맷팅하는 서비스입니다.
"""

import re
import html
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import math

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


@dataclass
class HighlightOptions:
    """하이라이팅 옵션"""
    tag: str = "mark"  # HTML 태그
    class_name: str = "search-highlight"  # CSS 클래스
    case_sensitive: bool = False  # 대소문자 구분
    whole_words_only: bool = False  # 전체 단어만 매치
    max_highlights_per_field: int = 10  # 필드당 최대 하이라이트 수


@dataclass
class PaginationInfo:
    """페이지네이션 정보"""
    current_page: int
    total_pages: int
    total_items: int
    page_size: int
    offset: int
    has_previous: bool = field(init=False)
    has_next: bool = field(init=False)
    
    def __post_init__(self):
        self.has_previous = self.current_page > 1
        self.has_next = self.current_page < self.total_pages


class FormattedSearchResult(BaseModel):
    """포맷팅된 검색 결과"""
    model_config = ConfigDict()
    
    # 원본 데이터
    original_data: List[Dict[str, Any]] = Field(..., description="원본 검색 결과")
    highlighted_data: List[Dict[str, Any]] = Field(..., description="하이라이팅 처리된 데이터")
    
    # 페이지네이션
    pagination: Dict[str, Any] = Field(..., description="페이지네이션 정보")
    
    # 요약 정보
    summary: Dict[str, Any] = Field(..., description="결과 요약")
    
    # 메타데이터
    formatting_info: Dict[str, Any] = Field(default_factory=dict, description="포맷팅 메타데이터")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="포맷팅 생성 시간")


class SearchResultFormatter:
    """검색 결과 포맷터 서비스"""
    
    def __init__(self):
        """포맷터 초기화"""
        self.default_highlight_options = HighlightOptions()
        logger.info("✅ SearchResultFormatter 초기화 완료")
    
    def format_search_results(
        self,
        data: List[Dict[str, Any]],
        query: str,
        total_count: int,
        page: int = 1,
        page_size: int = 20,
        highlight_options: Optional[HighlightOptions] = None
    ) -> FormattedSearchResult:
        """
        검색 결과를 종합적으로 포맷팅합니다.
        
        Args:
            data: 검색 결과 데이터
            query: 검색 쿼리
            total_count: 전체 결과 수
            page: 현재 페이지
            page_size: 페이지 크기
            highlight_options: 하이라이팅 옵션
            
        Returns:
            FormattedSearchResult: 포맷팅된 결과
        """
        try:
            logger.info(f"검색 결과 포맷팅 시작: {len(data)}행, 쿼리='{query}'")
            
            # 옵션 설정
            options = highlight_options or self.default_highlight_options
            
            # 1. 하이라이팅 처리
            highlighted_data = self.highlight_search_results(data, query, options)
            
            # 2. 페이지네이션 계산
            pagination_info = self._calculate_pagination(total_count, page, page_size)
            
            # 3. 결과 요약 생성
            summary = self._generate_result_summary(data, query, total_count)
            
            # 4. 포맷팅 메타데이터
            formatting_info = {
                "query": query,
                "highlight_options": {
                    "tag": options.tag,
                    "class_name": options.class_name,
                    "case_sensitive": options.case_sensitive,
                    "whole_words_only": options.whole_words_only
                },
                "processing_time_ms": 0,  # 실제 구현에서는 측정
                "total_highlights": self._count_highlights(highlighted_data, options.tag)
            }
            
            result = FormattedSearchResult(
                original_data=data,
                highlighted_data=highlighted_data,
                pagination=pagination_info.__dict__,
                summary=summary,
                formatting_info=formatting_info
            )
            
            logger.info(f"검색 결과 포맷팅 완료: {len(highlighted_data)}행 처리")
            return result
            
        except Exception as e:
            logger.error(f"검색 결과 포맷팅 실패: {e}")
            # 실패 시 기본 결과 반환
            return FormattedSearchResult(
                original_data=data,
                highlighted_data=data,  # 하이라이팅 실패 시 원본 반환
                pagination=self._calculate_pagination(total_count, page, page_size).__dict__,
                summary={"error": str(e), "total_results": len(data)},
                formatting_info={"error": str(e)}
            )
    
    def highlight_search_results(
        self,
        data: List[Dict[str, Any]],
        query: str,
        options: Optional[HighlightOptions] = None
    ) -> List[Dict[str, Any]]:
        """
        검색 결과에서 검색어를 하이라이팅합니다.
        
        Args:
            data: 검색 결과 데이터
            query: 검색 쿼리
            options: 하이라이팅 옵션
            
        Returns:
            하이라이팅 처리된 데이터
        """
        if not data or not query:
            return data
        
        options = options or self.default_highlight_options
        
        try:
            # 검색어 추출 및 정규화
            search_terms = self._extract_search_terms(query)
            if not search_terms:
                return data
            
            logger.debug(f"하이라이팅 대상 검색어: {search_terms}")
            
            highlighted_data = []
            
            for item in data:
                highlighted_item = {}
                
                for key, value in item.items():
                    if isinstance(value, str):
                        # 문자열 필드 하이라이팅
                        highlighted_value = self._highlight_text(
                            value, search_terms, options
                        )
                        highlighted_item[key] = highlighted_value
                    else:
                        # 비문자열 필드는 그대로 유지
                        highlighted_item[key] = value
                
                highlighted_data.append(highlighted_item)
            
            return highlighted_data
            
        except Exception as e:
            logger.warning(f"하이라이팅 처리 중 오류: {e}")
            return data  # 실패 시 원본 반환
    
    def paginate_results(
        self,
        data: List[Dict[str, Any]],
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], PaginationInfo]:
        """
        검색 결과를 페이지네이션합니다.
        
        Args:
            data: 검색 결과 데이터
            page: 현재 페이지 (1부터 시작)
            page_size: 페이지 크기
            
        Returns:
            Tuple[페이지네이션된 데이터, 페이지네이션 정보]
        """
        total_items = len(data)
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 1
        
        # 페이지 번호 검증
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        
        # 오프셋 계산
        offset = (page - 1) * page_size
        
        # 데이터 슬라이싱
        paginated_data = data[offset:offset + page_size]
        
        # 페이지네이션 정보 생성
        pagination_info = PaginationInfo(
            current_page=page,
            total_pages=total_pages,
            total_items=total_items,
            page_size=page_size,
            offset=offset
        )
        
        logger.debug(f"페이지네이션 처리: {total_items}행 → {len(paginated_data)}행 (페이지 {page}/{total_pages})")
        
        return paginated_data, pagination_info
    
    def generate_search_summary(
        self,
        data: List[Dict[str, Any]],
        query: str,
        total_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        검색 결과 요약을 생성합니다.
        
        Args:
            data: 검색 결과 데이터
            query: 검색 쿼리
            total_count: 전체 결과 수 (없으면 data 길이 사용)
            
        Returns:
            검색 결과 요약
        """
        return self._generate_result_summary(data, query, total_count or len(data))
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """검색어에서 하이라이팅할 용어들을 추출합니다."""
        # 한국어와 영어 단어 추출
        # 따옴표로 묶인 구문은 하나의 용어로 처리
        terms = []
        
        # 따옴표로 묶인 구문 추출
        quoted_pattern = r'"([^"]+)"'
        quoted_terms = re.findall(quoted_pattern, query)
        terms.extend(quoted_terms)
        
        # 따옴표를 제거한 나머지 부분에서 단어 추출
        remaining_query = re.sub(quoted_pattern, '', query)
        
        # 한국어, 영어, 숫자 단어 추출
        word_pattern = r'[가-힣a-zA-Z0-9]+\w*'
        words = re.findall(word_pattern, remaining_query)
        terms.extend(words)
        
        # 중복 제거 및 정리
        terms = [term.strip() for term in terms if term.strip()]
        terms = list(set(terms))  # 중복 제거
        
        # 너무 짧은 단어 제외 (한 글자 영어/숫자)
        terms = [term for term in terms if len(term) > 1 or re.match(r'[가-힣]', term)]
        
        return terms
    
    def _highlight_text(
        self,
        text: str,
        search_terms: List[str],
        options: HighlightOptions
    ) -> str:
        """텍스트에서 검색어를 하이라이팅합니다."""
        if not text or not search_terms:
            return text
        
        # HTML 이스케이프 (XSS 방지)
        escaped_text = html.escape(text)
        
        highlight_count = 0
        
        for term in search_terms:
            if highlight_count >= options.max_highlights_per_field:
                break
            
            # 검색어 이스케이프
            escaped_term = html.escape(term)
            
            # 정규식 플래그 설정
            flags = 0 if options.case_sensitive else re.IGNORECASE
            
            # 패턴 생성
            if options.whole_words_only:
                # 전체 단어만 매치 (한국어 고려)
                pattern = r'\b' + re.escape(escaped_term) + r'\b'
            else:
                # 부분 매치
                pattern = re.escape(escaped_term)
            
            # 하이라이트 태그 생성
            highlight_tag = f'<{options.tag} class="{options.class_name}">\\g<0></{options.tag}>'
            
            # 치환 수행
            escaped_text, count = re.subn(
                pattern, highlight_tag, escaped_text, flags=flags
            )
            highlight_count += count
        
        return escaped_text
    
    def _calculate_pagination(
        self,
        total_count: int,
        page: int,
        page_size: int
    ) -> PaginationInfo:
        """페이지네이션 정보를 계산합니다."""
        total_pages = math.ceil(total_count / page_size) if page_size > 0 else 1
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        offset = (page - 1) * page_size
        
        return PaginationInfo(
            current_page=page,
            total_pages=total_pages,
            total_items=total_count,
            page_size=page_size,
            offset=offset
        )
    
    def _generate_result_summary(
        self,
        data: List[Dict[str, Any]],
        query: str,
        total_count: int
    ) -> Dict[str, Any]:
        """검색 결과 요약을 생성합니다."""
        if not data:
            return {
                "total_results": total_count,
                "displayed_results": 0,
                "query": query,
                "message": "검색 결과가 없습니다.",
                "suggestions": self._generate_search_suggestions(query)
            }
        
        # 데이터 분석
        field_analysis = self._analyze_result_fields(data)
        
        # 검색어 빈도 분석
        term_frequency = self._analyze_term_frequency(data, query)
        
        summary = {
            "total_results": total_count,
            "displayed_results": len(data),
            "query": query,
            "message": f"총 {total_count:,}건의 검색 결과를 찾았습니다.",
            "field_analysis": field_analysis,
            "term_frequency": term_frequency,
            "query_complexity": self._assess_query_complexity(query),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # 추천 사항 추가
        if total_count == 0:
            summary["suggestions"] = self._generate_search_suggestions(query)
        elif total_count > 1000:
            summary["filter_suggestions"] = "결과가 많습니다. 더 구체적인 검색어를 사용해보세요."
        
        return summary
    
    def _analyze_result_fields(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """결과 필드들을 분석합니다."""
        if not data:
            return {}
        
        # 필드 통계
        field_stats = {}
        all_fields = set()
        
        for item in data:
            all_fields.update(item.keys())
        
        for field in all_fields:
            values = [item.get(field) for item in data if field in item]
            non_null_values = [v for v in values if v is not None]
            
            field_stats[field] = {
                "total_count": len(values),
                "non_null_count": len(non_null_values),
                "null_ratio": (len(values) - len(non_null_values)) / len(values) if values else 0,
                "data_types": list(set(type(v).__name__ for v in non_null_values))
            }
        
        return {
            "total_fields": len(all_fields),
            "field_statistics": field_stats,
            "common_fields": [f for f, stats in field_stats.items() if stats["non_null_count"] > len(data) * 0.8]
        }
    
    def _analyze_term_frequency(self, data: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        """검색어 빈도를 분석합니다."""
        search_terms = self._extract_search_terms(query)
        if not search_terms:
            return {}
        
        term_counts = {term: 0 for term in search_terms}
        total_text = ""
        
        # 모든 텍스트 필드에서 검색어 빈도 계산
        for item in data:
            for key, value in item.items():
                if isinstance(value, str):
                    total_text += " " + value.lower()
                    
                    for term in search_terms:
                        term_counts[term] += value.lower().count(term.lower())
        
        return {
            "search_terms": search_terms,
            "term_frequencies": term_counts,
            "most_frequent_term": max(term_counts.items(), key=lambda x: x[1])[0] if term_counts else None,
            "total_matches": sum(term_counts.values())
        }
    
    def _assess_query_complexity(self, query: str) -> Dict[str, Any]:
        """쿼리 복잡도를 평가합니다."""
        terms = self._extract_search_terms(query)
        
        complexity_score = 0
        features = []
        
        # 검색어 수
        term_count = len(terms)
        if term_count > 3:
            complexity_score += 1
            features.append("multiple_terms")
        
        # 따옴표 사용 (구문 검색)
        if '"' in query:
            complexity_score += 1
            features.append("phrase_search")
        
        # 긴 검색어
        if any(len(term) > 10 for term in terms):
            complexity_score += 1
            features.append("long_terms")
        
        # 복합 문자 (한영 혼합)
        has_korean = bool(re.search(r'[가-힣]', query))
        has_english = bool(re.search(r'[a-zA-Z]', query))
        if has_korean and has_english:
            complexity_score += 1
            features.append("mixed_language")
        
        complexity_levels = ["simple", "moderate", "complex", "very_complex"]
        complexity_level = complexity_levels[min(complexity_score, len(complexity_levels) - 1)]
        
        return {
            "score": complexity_score,
            "level": complexity_level,
            "features": features,
            "term_count": term_count
        }
    
    def _generate_search_suggestions(self, query: str) -> List[str]:
        """검색 결과가 없을 때 제안사항을 생성합니다."""
        suggestions = []
        
        # 기본 제안
        suggestions.extend([
            "검색어의 철자를 확인해보세요.",
            "더 일반적인 검색어를 사용해보세요.",
            "검색어를 줄여보세요."
        ])
        
        # 쿼리 분석 기반 제안
        if len(query) < 2:
            suggestions.append("더 긴 검색어를 입력해보세요.")
        
        if '"' in query:
            suggestions.append("따옴표를 제거하고 다시 검색해보세요.")
        
        # 한국어/영어 혼합 처리
        has_korean = bool(re.search(r'[가-힣]', query))
        has_english = bool(re.search(r'[a-zA-Z]', query))
        
        if has_korean and has_english:
            suggestions.append("한국어 또는 영어로만 검색해보세요.")
        
        return suggestions[:5]  # 최대 5개 제안
    
    def _count_highlights(self, data: List[Dict[str, Any]], tag: str) -> int:
        """하이라이트된 항목의 총 개수를 계산합니다."""
        count = 0
        pattern = f"<{tag}"
        
        for item in data:
            for key, value in item.items():
                if isinstance(value, str):
                    count += value.count(pattern)
        
        return count


# 싱글톤 인스턴스
search_formatter = SearchResultFormatter()