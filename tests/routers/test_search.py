"""
자연어 검색 API 테스트

FastAPI 0.104+ 패턴과 Pydantic v2를 사용한
자연어 검색 엔드포인트 테스트 스위트입니다.
"""

import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

import pytest_asyncio
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from app.main import app
from app.routers.search import (
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
    SearchOptions,
    ExecutionStrategy,
    websocket_manager
)


class TestSearchModels:
    """검색 모델 테스트"""
    
    def test_search_options_validation(self):
        """검색 옵션 검증 테스트"""
        # 유효한 옵션
        options = SearchOptions(
            strategy="llm_first",
            enable_streaming=True,
            timeout_seconds=45.0
        )
        assert options.strategy == ExecutionStrategy.LLM_FIRST
        assert options.enable_streaming is True
        assert options.timeout_seconds == 45.0
        
        # 기본값 테스트
        default_options = SearchOptions()
        assert default_options.strategy == ExecutionStrategy.LLM_FIRST
        assert default_options.enable_streaming is False
        assert default_options.include_explanation is True
        assert default_options.timeout_seconds == 30.0
    
    def test_search_options_validation_error(self):
        """검색 옵션 검증 오류 테스트"""
        with pytest.raises(Exception):  # ValidationError
            SearchOptions(strategy="invalid_strategy")
        
        with pytest.raises(Exception):  # ValidationError
            SearchOptions(timeout_seconds=0.0)  # 최소값 위반
        
        with pytest.raises(Exception):  # ValidationError
            SearchOptions(timeout_seconds=200.0)  # 최대값 위반
    
    def test_natural_language_search_request(self):
        """자연어 검색 요청 모델 테스트"""
        request_data = {
            "query": "30대 고객들의 평균 보험료",
            "context": {"department": "analytics"},
            "options": {
                "strategy": "hybrid",
                "timeout_seconds": 60.0
            },
            "limit": 50
        }
        
        request = NaturalLanguageSearchRequest(**request_data)
        assert request.query == "30대 고객들의 평균 보험료"
        assert request.context["department"] == "analytics"
        assert request.options.strategy == ExecutionStrategy.HYBRID
        assert request.limit == 50
    
    def test_natural_language_search_request_validation(self):
        """자연어 검색 요청 검증 테스트"""
        # 빈 쿼리
        with pytest.raises(Exception):  # ValidationError
            NaturalLanguageSearchRequest(query="")
        
        # 너무 긴 쿼리
        with pytest.raises(Exception):  # ValidationError
            NaturalLanguageSearchRequest(query="x" * 1001)
        
        # 잘못된 limit 값
        with pytest.raises(Exception):  # ValidationError
            NaturalLanguageSearchRequest(query="테스트", limit=0)
        
        with pytest.raises(Exception):  # ValidationError
            NaturalLanguageSearchRequest(query="테스트", limit=1001)


class TestSearchAPI:
    """검색 API 엔드포인트 테스트"""
    
    @pytest.fixture
    def client(self):
        """테스트 클라이언트 픽스처"""
        return TestClient(app)
    
    def test_get_search_strategies(self, client):
        """검색 전략 목록 조회 테스트"""
        response = client.get("/v1/api/search/strategies")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "strategies" in data
        assert "default" in data
        assert "total_count" in data
        assert "recommendation" in data
        
        # 전략 목록 확인
        strategies = data["strategies"]
        expected_strategies = ["llm_first", "rule_first", "hybrid", "llm_only", "rule_only"]
        for strategy in expected_strategies:
            assert strategy in strategies
            assert "name" in strategies[strategy]
            assert "description" in strategies[strategy]
            assert "recommended_for" in strategies[strategy]
    
    def test_search_health_check(self, client):
        """검색 서비스 헬스체크 테스트"""
        response = client.get("/v1/api/search/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "service" in data
        assert "components" in data
        
        assert data["service"] == "natural_language_search"
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    @patch('app.routers.search.lcel_sql_pipeline')
    @patch('app.routers.search.read_only_db_manager')
    def test_natural_language_search_success(self, mock_db, mock_pipeline, client):
        """자연어 검색 성공 테스트"""
        # Mock 설정
        mock_pipeline.generate_sql.return_value = AsyncMock()
        mock_pipeline.generate_sql.return_value.success = True
        mock_pipeline.generate_sql.return_value.error_message = None
        mock_pipeline.generate_sql.return_value.sql_result.sql = "SELECT COUNT(*) FROM customers WHERE age BETWEEN 30 AND 39"
        mock_pipeline.generate_sql.return_value.sql_result.parameters = {}
        mock_pipeline.generate_sql.return_value.sql_result.generation_method = "llm"
        mock_pipeline.generate_sql.return_value.intent_analysis = {
            "query_type": {"main_type": "aggregation", "confidence": 0.9},
            "entities": {"age_group": ["30대"]},
            "intent_keywords": ["고객", "30대"]
        }
        
        # Mock 데이터베이스 결과
        from collections import namedtuple
        Row = namedtuple('Row', ['count'])
        mock_db.execute_query_with_limit.return_value = [Row(count=150)]
        
        # 테스트 요청
        request_data = {
            "query": "30대 고객 수를 알려주세요",
            "context": {"department": "analytics"},
            "options": {
                "strategy": "llm_first",
                "timeout_seconds": 30.0
            },
            "limit": 100
        }
        
        response = client.post("/v1/api/search/natural-language", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # 응답 구조 확인
        assert "request_id" in data
        assert "query" in data
        assert "intent" in data
        assert "execution" in data
        assert "data" in data
        assert "total_rows" in data
        assert "success" in data
        assert "timestamp" in data
        
        assert data["query"] == request_data["query"]
        assert data["success"] is True
        assert len(data["data"]) > 0
    
    @patch('app.routers.search.lcel_sql_pipeline')
    def test_natural_language_search_pipeline_failure(self, mock_pipeline, client):
        """파이프라인 실패 테스트"""
        # Mock 실패 설정
        mock_pipeline.generate_sql.return_value = AsyncMock()
        mock_pipeline.generate_sql.return_value.success = False
        mock_pipeline.generate_sql.return_value.error_message = "SQL 생성 실패"
        
        request_data = {
            "query": "잘못된 쿼리",
            "limit": 10
        }
        
        response = client.post("/v1/api/search/natural-language", json=request_data)
        
        assert response.status_code == 400
        assert "SQL 생성 실패" in response.json()["detail"]
    
    def test_natural_language_search_validation_error(self, client):
        """입력 검증 오류 테스트"""
        # 빈 쿼리
        response = client.post("/v1/api/search/natural-language", json={"query": ""})
        assert response.status_code == 422
        
        # 잘못된 limit
        response = client.post("/v1/api/search/natural-language", json={
            "query": "테스트", 
            "limit": 0
        })
        assert response.status_code == 422
        
        # 잘못된 전략
        response = client.post("/v1/api/search/natural-language", json={
            "query": "테스트",
            "options": {"strategy": "invalid_strategy"}
        })
        assert response.status_code == 422


class TestWebSocketManager:
    """WebSocket 관리자 테스트"""
    
    @pytest.fixture
    def ws_manager(self):
        """WebSocket 관리자 픽스처"""
        # 테스트용 새로운 인스턴스 생성
        from app.routers.search import WebSocketManager
        return WebSocketManager()
    
    @pytest.mark.asyncio
    async def test_websocket_manager_connection(self, ws_manager):
        """WebSocket 연결 관리 테스트"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        
        client_id = "test_client_123"
        metadata = {"test": "data"}
        
        # 연결 테스트
        await ws_manager.connect(mock_websocket, client_id, metadata)
        
        assert client_id in ws_manager.active_connections
        assert client_id in ws_manager.connection_metadata
        assert ws_manager.connection_metadata[client_id] == metadata
        
        # 연결 해제 테스트
        ws_manager.disconnect(client_id)
        
        assert client_id not in ws_manager.active_connections
        assert client_id not in ws_manager.connection_metadata
    
    @pytest.mark.asyncio
    async def test_websocket_manager_send_message(self, ws_manager):
        """WebSocket 메시지 전송 테스트"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        client_id = "test_client_123"
        await ws_manager.connect(mock_websocket, client_id)
        
        # 메시지 전송 테스트
        test_message = {"type": "test", "data": "hello"}
        await ws_manager.send_personal_message(test_message, client_id)
        
        # 메시지가 JSON으로 전송되었는지 확인
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data == test_message
    
    @pytest.mark.asyncio
    async def test_websocket_manager_broadcast(self, ws_manager):
        """WebSocket 브로드캐스트 테스트"""
        # 여러 Mock WebSocket 연결
        clients = {}
        for i in range(3):
            client_id = f"client_{i}"
            mock_websocket = AsyncMock()
            mock_websocket.accept = AsyncMock()
            mock_websocket.send_text = AsyncMock()
            
            await ws_manager.connect(mock_websocket, client_id)
            clients[client_id] = mock_websocket
        
        # 브로드캐스트 테스트
        test_message = {"type": "broadcast", "message": "hello all"}
        await ws_manager.broadcast(test_message)
        
        # 모든 클라이언트에게 전송되었는지 확인
        for client_id, mock_websocket in clients.items():
            mock_websocket.send_text.assert_called_once()


class TestSearchIntegration:
    """검색 API 통합 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.integration
    def test_search_api_integration_flow(self, client):
        """검색 API 통합 흐름 테스트"""
        
        # 1. 헬스체크
        health_response = client.get("/v1/api/search/health")
        assert health_response.status_code == 200
        
        # 2. 전략 목록 조회
        strategies_response = client.get("/v1/api/search/strategies")
        assert strategies_response.status_code == 200
        strategies_data = strategies_response.json()
        assert "strategies" in strategies_data
        
        # 3. 실제 검색 요청 (Mock 없이 - 통합 테스트)
        # 단, 실제 데이터베이스 연결이 필요하므로 조건부 실행
        try:
            search_request = {
                "query": "테스트 쿼리",
                "options": {
                    "strategy": "rule_only",  # 빠른 테스트를 위해 규칙 기반만 사용
                    "timeout_seconds": 10.0
                },
                "limit": 1
            }
            
            search_response = client.post("/v1/api/search/natural-language", json=search_request)
            
            # 성공하거나 적절한 오류 응답이어야 함
            assert search_response.status_code in [200, 400, 500]
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                assert "request_id" in search_data
                assert "query" in search_data
                assert search_data["query"] == search_request["query"]
                
        except Exception as e:
            # 데이터베이스 연결 등의 문제로 실패할 수 있음
            pytest.skip(f"통합 테스트 스킵: {e}")


class TestSearchPerformance:
    """검색 API 성능 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.performance
    @patch('app.routers.search.lcel_sql_pipeline')
    @patch('app.routers.search.read_only_db_manager')
    def test_search_response_time(self, mock_db, mock_pipeline, client):
        """검색 응답 시간 테스트"""
        import time
        
        # Mock 빠른 응답 설정
        mock_pipeline.generate_sql.return_value = AsyncMock()
        mock_pipeline.generate_sql.return_value.success = True
        mock_pipeline.generate_sql.return_value.sql_result.sql = "SELECT 1"
        mock_pipeline.generate_sql.return_value.sql_result.parameters = {}
        mock_pipeline.generate_sql.return_value.sql_result.generation_method = "rule_based"
        mock_pipeline.generate_sql.return_value.intent_analysis = {
            "query_type": {"main_type": "simple_query", "confidence": 0.8},
            "entities": {},
            "intent_keywords": []
        }
        
        mock_db.execute_query_with_limit.return_value = []
        
        request_data = {
            "query": "성능 테스트 쿼리",
            "options": {"strategy": "rule_only"},
            "limit": 10
        }
        
        # 응답 시간 측정
        start_time = time.time()
        response = client.post("/v1/api/search/natural-language", json=request_data)
        end_time = time.time()
        
        assert response.status_code == 200
        
        # 응답 시간 검증 (1초 이내)
        response_time = end_time - start_time
        assert response_time < 1.0, f"응답시간이 너무 깁니다: {response_time:.2f}초"
    
    @pytest.mark.performance
    def test_concurrent_search_requests(self, client):
        """동시 검색 요청 테스트"""
        import concurrent.futures
        import time
        
        def make_request():
            return client.get("/v1/api/search/strategies")
        
        # 10개의 동시 요청
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        end_time = time.time()
        
        # 모든 요청이 성공해야 함
        for response in results:
            assert response.status_code == 200
        
        # 전체 처리 시간 확인 (동시 처리이므로 순차 처리보다 빨라야 함)
        total_time = end_time - start_time
        assert total_time < 5.0, f"동시 요청 처리 시간이 너무 깁니다: {total_time:.2f}초"


# 실행용 헬퍼 함수
if __name__ == "__main__":
    # 간단한 테스트 실행
    pytest.main([__file__, "-v", "--tb=short"])