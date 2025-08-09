# 자연어 검색 API 사용 가이드

## 개요

자연어 검색 API는 FastAPI 0.104+ 패턴과 Pydantic v2를 사용하여 구현된 고급 자연어 처리 검색 시스템입니다. 한국어 자연어 쿼리를 SQL로 변환하고 실행하여 원하는 데이터를 검색할 수 있습니다.

## 주요 특징

### 🚀 FastAPI 0.104+ 최신 패턴
- **의존성 주입**: 타입 힌트 기반의 현대적인 의존성 주입 패턴
- **Annotated 타입**: 명확한 타입 정의와 검증
- **자동 문서화**: OpenAPI 3.1 스키마 자동 생성
- **비동기 처리**: 완전 비동기 기반 고성능 처리

### 🎯 Pydantic v2 Field 검증
- **엄격한 타입 검증**: 입력 데이터의 완전한 검증
- **자동 변환**: 타입 자동 변환 및 정규화
- **상세한 오류 메시지**: 검증 실패 시 구체적인 오류 정보
- **성능 최적화**: Pydantic v2의 향상된 성능

### 🔄 실시간 WebSocket 스트리밍
- **실시간 검색**: WebSocket을 통한 실시간 검색 처리
- **진행률 추적**: 검색 과정의 실시간 모니터링
- **연결 관리**: 자동 연결 관리 및 오류 처리
- **다중 클라이언트**: 여러 클라이언트 동시 지원

### 🛡️ 고급 보안 및 권한 관리
- **선택적 인증**: Bearer 토큰 기반 인증 (선택적)
- **권한 검증**: 세밀한 권한 관리 시스템
- **요청 추적**: 모든 요청의 고유 ID 추적
- **감사 로그**: 검색 활동의 완전한 로깅

## API 엔드포인트

### 1. 자연어 검색
```http
POST /api/search/natural-language
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN  # 선택적

{
    "query": "30대 고객들의 평균 보험료를 지역별로 분석해주세요",
    "context": {
        "department": "analytics",
        "user_level": "advanced"
    },
    "options": {
        "strategy": "hybrid",
        "include_explanation": true,
        "timeout_seconds": 45.0
    },
    "limit": 100
}
```

**응답:**
```json
{
    "request_id": "req_20240115_103000_123456",
    "query": "30대 고객들의 평균 보험료를 지역별로 분석해주세요",
    "intent": {
        "intent_type": "data_analysis",
        "confidence": 0.92,
        "keywords": ["30대", "고객", "평균", "보험료", "지역별", "분석"],
        "entities": {
            "age_group": ["30대"],
            "metric": ["평균", "보험료"],
            "dimension": ["지역별"]
        }
    },
    "execution": {
        "sql_query": "SELECT region, AVG(premium_amount) as avg_premium FROM customers WHERE age BETWEEN 30 AND 39 GROUP BY region",
        "parameters": {},
        "execution_time_ms": 156.7,
        "rows_affected": 5,
        "strategy_used": "hybrid"
    },
    "data": [
        {"region": "서울", "avg_premium": 125000},
        {"region": "부산", "avg_premium": 118000},
        {"region": "대구", "avg_premium": 112000}
    ],
    "total_rows": 5,
    "success": true,
    "timestamp": "2024-01-15T10:30:00Z",
    "has_data": true,
    "execution_summary": "hybrid 전략으로 156.7ms에 5행 검색"
}
```

### 2. 검색 전략 목록
```http
GET /api/search/strategies
```

**응답:**
```json
{
    "strategies": {
        "llm_first": {
            "name": "LLM 우선",
            "description": "LLM을 우선 사용하고, 실패시 규칙 기반으로 Fallback",
            "accuracy": "높음",
            "speed": "중간",
            "cost": "중간",
            "recommended_for": ["복잡한 쿼리", "높은 정확도가 필요한 경우", "일반적인 사용"]
        },
        "rule_first": {
            "name": "규칙 우선",
            "description": "규칙 기반을 우선 사용하고, 실패시 LLM으로 Fallback",
            "accuracy": "중간",
            "speed": "빠름",
            "cost": "낮음",
            "recommended_for": ["간단한 쿼리", "빠른 응답이 필요한 경우", "정형화된 패턴"]
        },
        "hybrid": {
            "name": "하이브리드",
            "description": "LLM과 규칙 기반을 병렬 실행 후 최적 결과 선택",
            "accuracy": "최고",
            "speed": "느림",
            "cost": "높음",
            "recommended_for": ["중요한 쿼리", "최고 품질이 필요한 경우", "정확도 우선"]
        }
    },
    "default": "llm_first",
    "total_count": 5,
    "recommendation": {
        "general_use": "llm_first",
        "high_performance": "rule_first",
        "best_quality": "hybrid",
        "cost_effective": "rule_only"
    }
}
```

### 3. 서비스 상태 확인
```http
GET /api/search/health
```

**응답:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "service": "natural_language_search",
    "version": "2.0.0",
    "components": {
        "lcel_pipeline": "healthy",
        "database": "healthy",
        "websocket_manager": {
            "status": "healthy",
            "active_connections": 3
        }
    }
}
```

### 4. WebSocket 실시간 검색
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/search/stream?client_id=my_client_123');

ws.onopen = function() {
    console.log('WebSocket 연결됨');
    
    // 검색 요청 전송
    ws.send(JSON.stringify({
        type: "search_request",
        query: "최근 1개월 신규 가입 고객 분석",
        options: {
            strategy: "llm_first",
            timeout_seconds: 30.0
        },
        context: {
            user_id: "analyst_001"
        }
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.event_type) {
        case 'connection_established':
            console.log('연결 확인:', data.message);
            break;
        case 'search_started':
            console.log('검색 시작:', data.query);
            break;
        case 'stage_start':
            console.log('단계 시작:', data.data.stage);
            break;
        case 'token':
            process.stdout.write(data.data.content); // 실시간 토큰
            break;
        case 'pipeline_complete':
            console.log('검색 완료:', data.data.result);
            break;
        case 'error':
            console.error('오류:', data.message);
            break;
    }
};
```

## Python 클라이언트 사용법

### 기본 검색 예제
```python
import httpx
import asyncio

async def search_example():
    async with httpx.AsyncClient() as client:
        # 검색 요청
        response = await client.post(
            "http://localhost:8000/api/search/natural-language",
            json={
                "query": "30대 여성 고객들의 평균 보험료",
                "context": {
                    "department": "analytics",
                    "region": "seoul"
                },
                "options": {
                    "strategy": "llm_first",
                    "include_explanation": True,
                    "timeout_seconds": 30.0
                },
                "limit": 50
            },
            headers={
                "Authorization": "Bearer your_token_here"  # 선택적
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"검색 성공: {data['total_rows']}행")
            print(f"실행 시간: {data['execution']['execution_time_ms']:.1f}ms")
            print(f"사용된 전략: {data['execution']['strategy_used']}")
            
            for row in data['data']:
                print(row)
        else:
            print(f"검색 실패: {response.status_code} - {response.text}")

asyncio.run(search_example())
```

### 전략별 검색 비교
```python
import asyncio
import httpx
from typing import List, Dict, Any

async def compare_strategies(query: str) -> Dict[str, Any]:
    """다양한 전략으로 같은 쿼리 실행하고 비교"""
    strategies = ["rule_only", "llm_first", "hybrid"]
    results = {}
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for strategy in strategies:
            request_data = {
                "query": query,
                "options": {
                    "strategy": strategy,
                    "timeout_seconds": 30.0
                },
                "limit": 10
            }
            
            task = client.post(
                "http://localhost:8000/api/search/natural-language",
                json=request_data
            )
            tasks.append((strategy, task))
        
        # 병렬 실행
        for strategy, task in tasks:
            try:
                response = await task
                if response.status_code == 200:
                    data = response.json()
                    results[strategy] = {
                        "success": True,
                        "execution_time": data['execution']['execution_time_ms'],
                        "rows": data['total_rows'],
                        "confidence": data['intent']['confidence'],
                        "sql": data['execution']['sql_query'][:100] + "..."
                    }
                else:
                    results[strategy] = {
                        "success": False,
                        "error": response.text
                    }
            except Exception as e:
                results[strategy] = {
                    "success": False,
                    "error": str(e)
                }
    
    return results

# 사용 예제
async def main():
    results = await compare_strategies("고객 수를 세어주세요")
    
    print("전략별 성능 비교:")
    for strategy, result in results.items():
        if result["success"]:
            print(f"{strategy:10}: {result['execution_time']:6.1f}ms, {result['rows']}행, 신뢰도 {result['confidence']:.2f}")
        else:
            print(f"{strategy:10}: 실패 - {result['error']}")

asyncio.run(main())
```

### WebSocket 클라이언트
```python
import asyncio
import websockets
import json

async def websocket_search_client():
    uri = "ws://localhost:8000/ws/search/stream?client_id=python_client_123"
    
    async with websockets.connect(uri) as websocket:
        # 연결 확인 메시지 수신
        response = await websocket.recv()
        print("연결 응답:", json.loads(response))
        
        # 검색 요청 전송
        search_request = {
            "type": "search_request",
            "query": "지난달 신규 가입 고객들의 연령대별 분포",
            "options": {
                "strategy": "hybrid",
                "timeout_seconds": 45.0
            },
            "context": {
                "user_id": "python_user"
            }
        }
        
        await websocket.send(json.dumps(search_request))
        
        # 실시간 응답 수신
        async for message in websocket:
            data = json.loads(message)
            event_type = data.get("event_type")
            
            if event_type == "search_started":
                print(f"🔍 검색 시작: {data['query']}")
            elif event_type == "stage_start":
                print(f"📋 단계 시작: {data['data']['stage']}")
            elif event_type == "token":
                print(data['data']['content'], end='', flush=True)
            elif event_type == "search_completed":
                print(f"\n✅ 검색 완료: {data['query']}")
                break
            elif event_type == "error":
                print(f"❌ 오류: {data['message']}")
                break

asyncio.run(websocket_search_client())
```

## 고급 사용법

### 1. 컨텍스트 활용
```python
# 사용자별 맞춤 검색
context = {
    "user_id": "analyst_001",
    "department": "sales",
    "region": "seoul",
    "access_level": "manager",
    "preferred_language": "ko"
}

request_data = {
    "query": "우리 지역 실적 분석해줘",
    "context": context,
    "options": {"strategy": "llm_first"}
}
```

### 2. 배치 검색
```python
async def batch_search(queries: List[str]) -> List[Dict]:
    """여러 쿼리를 배치로 처리"""
    async with httpx.AsyncClient() as client:
        tasks = []
        for query in queries:
            request_data = {
                "query": query,
                "options": {"strategy": "rule_first"},  # 빠른 처리를 위해
                "limit": 20
            }
            
            task = client.post(
                "http://localhost:8000/api/search/natural-language",
                json=request_data
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                results.append({
                    "query": queries[i],
                    "success": False,
                    "error": str(response)
                })
            elif response.status_code == 200:
                data = response.json()
                results.append({
                    "query": queries[i],
                    "success": True,
                    "rows": data['total_rows'],
                    "execution_time": data['execution']['execution_time_ms']
                })
            else:
                results.append({
                    "query": queries[i],
                    "success": False,
                    "error": response.text
                })
        
        return results

# 사용 예제
queries = [
    "고객 수",
    "평균 연령",
    "지역별 분포",
    "월별 가입 추이"
]

results = await batch_search(queries)
for result in results:
    print(f"{result['query']:15}: {result}")
```

### 3. 오류 처리 및 재시도
```python
import time
from typing import Optional

async def robust_search(
    query: str, 
    max_retries: int = 3,
    backoff_factor: float = 1.0
) -> Optional[Dict]:
    """견고한 검색 (재시도 로직 포함)"""
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/search/natural-language",
                    json={
                        "query": query,
                        "options": {
                            "strategy": "llm_first",
                            "timeout_seconds": 30.0
                        },
                        "limit": 100
                    },
                    timeout=35.0
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    wait_time = backoff_factor * (2 ** attempt)
                    print(f"Rate limit 도달, {wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"검색 실패 (시도 {attempt + 1}): {response.status_code}")
                    if attempt == max_retries - 1:
                        return None
                    
                    await asyncio.sleep(backoff_factor * attempt)
                    
        except asyncio.TimeoutError:
            print(f"타임아웃 (시도 {attempt + 1})")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(backoff_factor * attempt)
            
        except Exception as e:
            print(f"예외 발생 (시도 {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(backoff_factor * attempt)
    
    return None

# 사용 예제
result = await robust_search("복잡한 분석 쿼리", max_retries=3)
if result:
    print("검색 성공:", result['total_rows'], "행")
else:
    print("검색 실패: 모든 재시도 실패")
```

## 성능 최적화

### 1. 전략 선택 가이드
```python
def choose_strategy(query_complexity: str, response_time_req: str, accuracy_req: str) -> str:
    """상황별 최적 전략 선택"""
    
    if accuracy_req == "highest":
        return "hybrid"
    elif response_time_req == "fastest":
        return "rule_only"
    elif query_complexity == "simple":
        return "rule_first"
    elif query_complexity == "complex":
        return "llm_first"
    else:
        return "llm_first"  # 기본값

# 사용 예제
strategy = choose_strategy(
    query_complexity="complex",
    response_time_req="normal", 
    accuracy_req="high"
)
print(f"권장 전략: {strategy}")
```

### 2. 연결 풀링
```python
import httpx

# 글로벌 클라이언트 인스턴스 (연결 재사용)
client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=100)
)

async def optimized_search(query: str) -> Dict:
    """최적화된 검색 (연결 재사용)"""
    global client
    
    response = await client.post(
        "http://localhost:8000/api/search/natural-language",
        json={
            "query": query,
            "options": {"strategy": "rule_first"},
            "limit": 50
        }
    )
    
    return response.json() if response.status_code == 200 else None

# 애플리케이션 종료 시 정리
async def cleanup():
    await client.aclose()
```

## 모니터링 및 디버깅

### 1. 요청 추적
```python
import uuid

async def tracked_search(query: str) -> Dict:
    """요청 추적이 가능한 검색"""
    request_id = str(uuid.uuid4())
    
    headers = {
        "X-Request-ID": request_id,
        "User-Agent": "MyApp/1.0"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/search/natural-language",
            json={"query": query},
            headers=headers
        )
        
        result = response.json() if response.status_code == 200 else None
        
        # 로깅
        print(f"Request ID: {request_id}")
        print(f"Query: {query}")
        print(f"Status: {response.status_code}")
        if result:
            print(f"Response ID: {result.get('request_id')}")
            print(f"Execution Time: {result['execution']['execution_time_ms']}ms")
        
        return result
```

### 2. 성능 메트릭 수집
```python
import time
from dataclasses import dataclass
from typing import List

@dataclass
class SearchMetric:
    query: str
    strategy: str
    success: bool
    execution_time_ms: float
    rows_returned: int
    timestamp: float

class MetricsCollector:
    def __init__(self):
        self.metrics: List[SearchMetric] = []
    
    async def measured_search(self, query: str, strategy: str = "llm_first") -> Dict:
        """메트릭 수집이 포함된 검색"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/search/natural-language",
                    json={
                        "query": query,
                        "options": {"strategy": strategy}
                    }
                )
                
                success = response.status_code == 200
                result = response.json() if success else None
                
                # 메트릭 기록
                metric = SearchMetric(
                    query=query,
                    strategy=strategy,
                    success=success,
                    execution_time_ms=result['execution']['execution_time_ms'] if result else 0,
                    rows_returned=result['total_rows'] if result else 0,
                    timestamp=time.time()
                )
                
                self.metrics.append(metric)
                return result
                
        except Exception as e:
            # 오류 메트릭도 기록
            metric = SearchMetric(
                query=query,
                strategy=strategy,
                success=False,
                execution_time_ms=0,
                rows_returned=0,
                timestamp=time.time()
            )
            self.metrics.append(metric)
            raise
    
    def get_stats(self) -> Dict:
        """메트릭 통계 반환"""
        if not self.metrics:
            return {}
        
        successful = [m for m in self.metrics if m.success]
        
        return {
            "total_requests": len(self.metrics),
            "successful_requests": len(successful),
            "success_rate": len(successful) / len(self.metrics) * 100,
            "avg_execution_time": sum(m.execution_time_ms for m in successful) / len(successful) if successful else 0,
            "total_rows_returned": sum(m.rows_returned for m in successful)
        }

# 사용 예제
collector = MetricsCollector()

# 여러 검색 수행
for query in ["고객 수", "평균 나이", "지역별 분포"]:
    await collector.measured_search(query)

# 통계 확인
stats = collector.get_stats()
print(f"성공률: {stats['success_rate']:.1f}%")
print(f"평균 실행시간: {stats['avg_execution_time']:.1f}ms")
```

## 문제 해결

### 일반적인 오류 및 해결책

1. **422 Unprocessable Entity**
   - 원인: 입력 데이터 검증 실패
   - 해결: 요청 데이터 형식 확인, 필수 필드 누락 확인

2. **400 Bad Request**
   - 원인: SQL 생성 실패
   - 해결: 다른 전략 시도, 쿼리 단순화

3. **500 Internal Server Error**
   - 원인: 서버 내부 오류
   - 해결: 로그 확인, 헬스체크 API로 상태 확인

4. **WebSocket 연결 실패**
   - 원인: 네트워크 문제, 서버 과부하
   - 해결: 재연결 로직 구현, 연결 상태 모니터링

### 디버깅 도구

```python
# 디버깅 헬퍼 함수
async def debug_search(query: str):
    """디버깅을 위한 상세 검색"""
    
    # 1. 헬스체크
    health_response = await client.get("/api/search/health")
    print("서비스 상태:", health_response.json()["status"])
    
    # 2. 전략별 테스트
    strategies = ["rule_only", "llm_first"]
    for strategy in strategies:
        try:
            response = await client.post(
                "/api/search/natural-language",
                json={
                    "query": query,
                    "options": {"strategy": strategy, "timeout_seconds": 10.0},
                    "limit": 5
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"{strategy}: ✅ {data['total_rows']}행, {data['execution']['execution_time_ms']}ms")
            else:
                print(f"{strategy}: ❌ {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"{strategy}: 💥 {e}")

await debug_search("테스트 쿼리")
```

## 참고 자료

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Pydantic v2 가이드](https://docs.pydantic.dev/latest/)
- [WebSocket 클라이언트 구현](https://websockets.readthedocs.io/)
- [LCEL SQL 파이프라인 가이드](./LCEL_SQL_PIPELINE_GUIDE.md)
- [Intent Classifier 가이드](./INTENT_CLASSIFIER_GUIDE.md)

## 업데이트 로그

- **v2.0**: FastAPI 0.104+ 패턴과 Pydantic v2로 전면 업그레이드
- **v2.1**: WebSocket 실시간 스트리밍 추가
- **v2.2**: 고급 보안 및 권한 관리 추가
- **v2.3**: OpenAPI 3.1 스키마 자동 생성 최적화