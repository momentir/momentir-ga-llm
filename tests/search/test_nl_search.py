#!/usr/bin/env python3
"""
Comprehensive Natural Language Search Test Suite
Tests the core NL to SQL functionality with realistic scenarios
"""
import pytest
import asyncio
import time
import sys
import os
from typing import Dict, Any
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.config.test_config import TestConfig
from scripts.test_db_seeder import TestDataSeeder
from app.models.search_models import NaturalLanguageSearchRequest, SearchOptions

# Configure test environment
TestConfig.override_env_vars()

class TestNLSearch:
    """Natural Language Search Test Suite"""
    
    @classmethod
    async def setup_class(cls):
        """Setup test database and seed data"""
        print("🚀 Setting up test database...")
        cls.seeder = TestDataSeeder()
        await cls.seeder.seed_all()
        
        # Test API base URL
        cls.base_url = "http://127.0.0.1:8000"
        cls.search_endpoint = f"{cls.base_url}/v1/api/search/natural-language"
    
    @classmethod
    async def teardown_class(cls):
        """Cleanup test database"""
        await cls.seeder.cleanup()
        print("🧹 Test database cleaned up")
    
    @pytest.mark.asyncio
    async def test_server_health(self):
        """Test 0: Verify server is running"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
    
    # === Basic Search Scenarios (10 tests) ===
    
    @pytest.mark.asyncio
    async def test_customer_name_search(self):
        """Test 1: '홍길동 고객 정보' - Customer name search"""
        request_data = {
            "query": "홍길동 고객 정보",
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            response = await client.post(self.search_endpoint, json=request_data)
            end_time = time.time()
            
            # Performance check
            response_time = end_time - start_time
            assert response_time < TestConfig.MAX_RESPONSE_TIME, f"Response too slow: {response_time:.2f}s"
            
            # Response validation
            assert response.status_code == 200
            result = response.json()
            
            assert "data" in result
            assert "sql_query" in result
            assert "execution_time" in result
            assert result["success"] is True
            
            # Content validation - should find 홍길동
            data = result["data"]
            assert len(data) > 0
            found_hong = any("홍길동" in str(row.get("name", "")) for row in data)
            assert found_hong, "홍길동 not found in results"
    
    @pytest.mark.asyncio
    async def test_insurance_product_search(self):
        """Test 2: '화재보험 가입 고객' - Insurance product search"""
        request_data = {
            "query": "화재보험 가입 고객",
            "options": {"strategy": "llm_first"},
            "limit": 20
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            response = await client.post(self.search_endpoint, json=request_data)
            end_time = time.time()
            
            # Performance check
            response_time = end_time - start_time
            assert response_time < TestConfig.MAX_RESPONSE_TIME
            
            # Response validation
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should involve JOIN with customer_products table
            sql_query = result["sql_query"].lower()
            assert "customer_products" in sql_query or "join" in sql_query
            assert "화재보험" in sql_query or "fire" in result["sql_query"]
    
    @pytest.mark.asyncio
    async def test_expiry_customers_search(self):
        """Test 3: '이번달 만기 고객' - Expiring policies search"""
        request_data = {
            "query": "이번달 만기 고객",
            "options": {"strategy": "llm_first"},
            "limit": 15
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            response = await client.post(self.search_endpoint, json=request_data)
            end_time = time.time()
            
            # Performance check
            response_time = end_time - start_time
            assert response_time < TestConfig.MAX_RESPONSE_TIME
            
            # Response validation
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should involve date filtering
            sql_query = result["sql_query"].lower()
            assert any(keyword in sql_query for keyword in [
                "expiry", "renewal", "date", "interval", "month"
            ]), f"Date filtering not found in: {sql_query}"
    
    @pytest.mark.asyncio
    async def test_gender_based_search(self):
        """Test 4: '30세 이상 남성 고객' - Age and gender filtering"""
        request_data = {
            "query": "30세 이상 남성 고객",
            "options": {"strategy": "llm_first"},
            "limit": 25
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should filter by gender and age
            sql_query = result["sql_query"].lower()
            assert "gender" in sql_query or "남성" in result["sql_query"]
            assert any(keyword in sql_query for keyword in [
                "age", "birth", "30", "interval"
            ])
    
    @pytest.mark.asyncio
    async def test_job_based_search(self):
        """Test 5: '의사 직업 고객 목록' - Job title search"""
        request_data = {
            "query": "의사 직업 고객 목록",
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should filter by job title
            sql_query = result["sql_query"].lower()
            assert "job" in sql_query or "의사" in result["sql_query"]
    
    @pytest.mark.asyncio
    async def test_contact_channel_search(self):
        """Test 6: '지역마케팅으로 유입된 고객' - Contact channel search"""
        request_data = {
            "query": "지역마케팅으로 유입된 고객",
            "options": {"strategy": "llm_first"},
            "limit": 20
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should filter by contact channel
            sql_query = result["sql_query"].lower()
            assert "contact" in sql_query or "지역마케팅" in result["sql_query"]
    
    @pytest.mark.asyncio
    async def test_recent_customers_search(self):
        """Test 7: '최근 3개월 가입 고객' - Date range search"""
        request_data = {
            "query": "최근 3개월 가입 고객",
            "options": {"strategy": "llm_first"},
            "limit": 30
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should use date filtering
            sql_query = result["sql_query"].lower()
            assert any(keyword in sql_query for keyword in [
                "created_at", "date", "interval", "month", "3"
            ])
    
    @pytest.mark.asyncio 
    async def test_policy_status_search(self):
        """Test 8: '증권교부 완료 고객' - Policy status search"""
        request_data = {
            "query": "증권교부 완료 고객",
            "options": {"strategy": "llm_first"},
            "limit": 15
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should check policy_issued status
            sql_query = result["sql_query"].lower()
            assert "policy" in sql_query or "증권" in result["sql_query"]
    
    @pytest.mark.asyncio
    async def test_coverage_amount_search(self):
        """Test 9: '가입금액 높은 고객 순으로' - Coverage amount ordering"""
        request_data = {
            "query": "가입금액 높은 고객 순으로",
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should include ordering
            sql_query = result["sql_query"].lower()
            assert any(keyword in sql_query for keyword in [
                "order", "desc", "coverage", "amount"
            ])
    
    @pytest.mark.asyncio
    async def test_multi_condition_search(self):
        """Test 10: '여성이면서 건강보험 가입한 고객' - Multiple conditions"""
        request_data = {
            "query": "여성이면서 건강보험 가입한 고객",
            "options": {"strategy": "llm_first"},
            "limit": 20
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            
            # Should have multiple conditions
            sql_query = result["sql_query"].lower()
            assert ("gender" in sql_query or "여성" in result["sql_query"]) and \
                   ("건강보험" in result["sql_query"] or "health" in sql_query)
    
    # === SQL Injection Defense Tests (3 tests) ===
    
    @pytest.mark.asyncio
    async def test_sql_injection_defense_1(self):
        """SQL Injection Test 1: Basic injection attempt"""
        malicious_query = "고객 정보'; DROP TABLE customers; --"
        
        request_data = {
            "query": malicious_query,
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            # Should not execute malicious SQL
            assert response.status_code in [200, 400, 422]  # Should be handled safely
            
            if response.status_code == 200:
                result = response.json()
                sql_query = result.get("sql_query", "").upper()
                
                # Should not contain dangerous SQL commands
                dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]
                for keyword in dangerous_keywords:
                    assert keyword not in sql_query, f"Dangerous keyword {keyword} found in generated SQL"
    
    @pytest.mark.asyncio
    async def test_sql_injection_defense_2(self):
        """SQL Injection Test 2: Union-based injection"""
        malicious_query = "홍길동' UNION SELECT password FROM users --"
        
        request_data = {
            "query": malicious_query,
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                result = response.json()
                sql_query = result.get("sql_query", "").upper()
                
                # Should not contain unauthorized table access
                assert "UNION" not in sql_query or "PASSWORD" not in sql_query
    
    @pytest.mark.asyncio
    async def test_sql_injection_defense_3(self):
        """SQL Injection Test 3: Comment-based injection"""
        malicious_query = "고객 /* comment */ WHERE 1=1 OR '1'='1"
        
        request_data = {
            "query": malicious_query,
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                result = response.json()
                # Should still return valid, safe results
                assert result.get("success", False)
    
    # === Performance and Concurrency Tests ===
    
    @pytest.mark.asyncio
    async def test_response_time_performance(self):
        """Performance Test: Response time under 3 seconds"""
        test_queries = [
            "홍길동 고객",
            "화재보험 고객", 
            "이번달 만기",
            "30세 이상 남성",
            "의사 직업 고객"
        ]
        
        for query in test_queries:
            request_data = {
                "query": query,
                "options": {"strategy": "llm_first"},
                "limit": 10
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                start_time = time.time()
                response = await client.post(self.search_endpoint, json=request_data)
                end_time = time.time()
                
                response_time = end_time - start_time
                assert response_time < TestConfig.MAX_RESPONSE_TIME, \
                    f"Query '{query}' too slow: {response_time:.2f}s"
                assert response.status_code == 200
    
    def test_concurrent_requests(self):
        """Concurrency Test: Handle 5 simultaneous requests"""
        def make_request(query_id: int) -> Dict[str, Any]:
            """Make a single search request"""
            import requests
            
            request_data = {
                "query": f"고객 정보 조회 {query_id}",
                "options": {"strategy": "llm_first"},
                "limit": 5
            }
            
            start_time = time.time()
            response = requests.post(
                self.search_endpoint, 
                json=request_data,
                timeout=30
            )
            end_time = time.time()
            
            return {
                "query_id": query_id,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=TestConfig.MAX_CONCURRENT_REQUESTS) as executor:
            futures = [
                executor.submit(make_request, i) 
                for i in range(TestConfig.MAX_CONCURRENT_REQUESTS)
            ]
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        # Validate all requests succeeded
        assert len(results) == TestConfig.MAX_CONCURRENT_REQUESTS
        
        for result in results:
            assert result["success"], f"Request {result['query_id']} failed"
            assert result["response_time"] < TestConfig.MAX_RESPONSE_TIME, \
                f"Request {result['query_id']} too slow: {result['response_time']:.2f}s"
        
        # Check average performance
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        assert avg_response_time < TestConfig.MAX_RESPONSE_TIME, \
            f"Average response time too high: {avg_response_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test graceful error handling"""
        # Test with empty query
        request_data = {
            "query": "",
            "options": {"strategy": "llm_first"},
            "limit": 10
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=request_data)
            assert response.status_code in [400, 422]  # Should validate input
        
        # Test with malformed request
        malformed_data = {
            "invalid_field": "test",
            "limit": "not_a_number"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.search_endpoint, json=malformed_data)
            assert response.status_code == 422  # Validation error


# Test execution helpers
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def setup_and_teardown():
    """Setup and teardown test environment"""
    await TestNLSearch.setup_class()
    yield
    await TestNLSearch.teardown_class()

if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--tb=short"])