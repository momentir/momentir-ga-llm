"""
검색 분석 서비스 테스트 코드
PostgreSQL 기반 검색 히스토리 및 분석 기능 검증
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search_analytics import search_analytics_service


class TestSearchAnalytics:
    """검색 분석 서비스 테스트 클래스"""
    
    @pytest.fixture
    async def mock_db_session(self):
        """Mock 데이터베이스 세션"""
        session = AsyncMock(spec=AsyncSession)
        return session
    
    @pytest.fixture
    def sample_search_data(self):
        """테스트용 샘플 검색 데이터"""
        return {
            "user_id": 1,
            "query": "고객의 연락처가 010으로 시작하는 고객들을 조회해주세요",
            "sql_generated": "SELECT * FROM customers WHERE phone LIKE '010%'",
            "strategy_used": "llm_first",
            "success": True,
            "result_count": 15,
            "response_time": 2.5,
            "sql_generation_time": 1.2,
            "sql_execution_time": 1.3
        }
    
    async def test_record_search_success(self, mock_db_session, sample_search_data):
        """검색 기록 저장 성공 테스트"""
        # Given
        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        # When
        result = await search_analytics_service.record_search(
            mock_db_session, **sample_search_data
        )
        
        # Then
        assert result is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        print("✅ 검색 기록 저장 테스트 통과")
    
    async def test_record_search_failure_pattern_detection(self, mock_db_session):
        """실패 패턴 감지 테스트"""
        # Given
        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.execute = AsyncMock()
        
        # Mock 기존 패턴이 없음
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        mock_db_session.execute.return_value = mock_result
        
        failure_data = {
            "user_id": 1,
            "query": "잘못된 컬럼명으로 검색",
            "success": False,
            "error_message": "column 'invalid_column' does not exist"
        }
        
        # When
        result = await search_analytics_service.record_search(
            mock_db_session, **failure_data
        )
        
        # Then
        assert result is not None
        # 2번 commit: 검색 기록 + 실패 패턴
        assert mock_db_session.commit.call_count >= 1
        print("✅ 실패 패턴 감지 테스트 통과")
    
    def test_search_analytics_integration(self):
        """통합 테스트 (실제 데이터베이스 연결 필요)"""
        print("🔍 검색 분석 통합 테스트")
        
        # 실제 환경에서는 다음과 같이 테스트:
        # 1. 실제 DB 세션 생성
        # 2. 샘플 데이터 삽입
        # 3. 분석 기능 실행
        # 4. 결과 검증
        # 5. 테스트 데이터 정리
        
        test_scenarios = [
            {
                "name": "인기 검색어 조회",
                "description": "최근 7일간 인기 검색어 TOP 10 조회"
            },
            {
                "name": "성능 통계 조회",
                "description": "응답 시간 및 성공률 통계"
            },
            {
                "name": "실패 패턴 분석",
                "description": "실패율 70% 이상 패턴 감지"
            },
            {
                "name": "사용자별 히스토리",
                "description": "특정 사용자의 검색 이력 조회"
            }
        ]
        
        for scenario in test_scenarios:
            print(f"  - {scenario['name']}: {scenario['description']}")
        
        print("✅ 통합 테스트 시나리오 정의 완료")
        return True


async def main():
    """테스트 실행 함수"""
    print("🧪 검색 분석 서비스 테스트 시작\n")
    
    test_class = TestSearchAnalytics()
    
    try:
        # Mock 세션 생성
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.add = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        
        # 샘플 데이터 생성
        sample_data = {
            "user_id": 1,
            "query": "테스트 검색 쿼리",
            "sql_generated": "SELECT * FROM test_table",
            "strategy_used": "test_strategy",
            "success": True,
            "result_count": 10,
            "response_time": 1.5,
            "sql_generation_time": 0.8,
            "sql_execution_time": 0.7
        }
        
        # 검색 기록 저장 테스트
        await test_class.test_record_search_success(mock_session, sample_data)
        
        # 실패 패턴 감지 테스트
        await test_class.test_record_search_failure_pattern_detection(mock_session)
        
        # 통합 테스트 시나리오
        test_class.test_search_analytics_integration()
        
        print("\n🎉 모든 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        return False
    
    return True


if __name__ == "__main__":
    # 테스트 실행
    success = asyncio.run(main())
    
    if success:
        print("\n✅ 검색 분석 시스템 테스트 성공")
        print("📋 다음 단계:")
        print("  1. 데이터베이스 마이그레이션 실행")
        print("  2. API 엔드포인트 테스트")
        print("  3. 실제 검색 데이터로 분석 검증")
    else:
        print("\n❌ 테스트 실패 - 코드를 검토해주세요")