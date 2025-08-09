# LCEL SQL 생성 파이프라인 사용 가이드

## 개요

LangChain Expression Language (LCEL) 기반의 고급 SQL 생성 파이프라인은 자연어 쿼리를 안전하고 정확한 SQL로 변환하는 시스템입니다.

## 주요 특징

### 🔗 LCEL 체인 아키텍처
- **자연어 → 의도 파싱 → SQL 생성 → 검증** 순서의 완전 자동화된 체인
- 각 단계별 독립적 처리와 결과 전달
- 병렬 처리 및 조건부 분기 지원

### 🔄 Fallback 체인 구성
- **LLM 우선**: LLM 실패 시 규칙 기반으로 자동 전환
- **규칙 우선**: 규칙 기반 실패 시 LLM으로 자동 전환  
- **하이브리드**: 두 방법을 병렬 실행 후 최적 결과 선택

### ⚡ Retry 로직 & Exponential Backoff
- 설정 가능한 최대 재시도 횟수
- 지수 백오프로 대기 시간 증가
- 재시도 가능한 예외 타입 지정
- 지터(Jitter) 추가로 Thunder Herd 문제 방지

### 📊 LangSmith 추적 통합
- 전체 파이프라인 실행 과정 추적
- 각 체인별 성능 메트릭 수집
- 오류 발생 지점 정확한 로깅
- 프로젝트별 분리된 추적

### 🌊 스트리밍 응답 지원
- Server-Sent Events (SSE) 기반
- 실시간 처리 단계 확인
- LLM 토큰 생성 과정 스트리밍
- 클라이언트 취소 지원

## API 엔드포인트

### 1. 기본 SQL 생성
```http
POST /api/lcel-sql/generate
Content-Type: application/json

{
    "query": "30대 고객들의 평균 보험료를 계산해주세요",
    "strategy": "llm_first",
    "context": {"department": "analytics"},
    "timeout_seconds": 30.0,
    "retry_config": {
        "max_attempts": 3,
        "base_delay": 1.0,
        "exponential_base": 2.0
    }
}
```

**응답:**
```json
{
    "intent_analysis": {
        "query_type": {"main_type": "aggregation", "confidence": 0.92},
        "entities": {"dates": ["30대"], "amounts": ["평균"]},
        "complexity_score": 0.7
    },
    "sql_result": {
        "sql": "SELECT AVG(premium_amount) FROM customers WHERE age_range = '30-39'",
        "parameters": {"age_range": "30-39"},
        "explanation": "30대 고객들의 평균 보험료 계산 쿼리",
        "confidence": 0.92,
        "generation_method": "llm"
    },
    "success": true,
    "metrics": {
        "total_duration": 2.34,
        "strategy_used": "llm_first"
    }
}
```

### 2. 스트리밍 SQL 생성
```http
POST /api/lcel-sql/generate-streaming
Content-Type: application/json

{
    "query": "지난 분기 신규 가입 고객 수 분석",
    "strategy": "hybrid",
    "enable_streaming": true
}
```

**스트리밍 응답 (SSE):**
```
data: {"type": "start", "data": {"query": "...", "timestamp": "..."}}

data: {"type": "stage_start", "stage": "intent_analysis", "timestamp": "..."}

data: {"type": "token", "content": "SELECT", "stage": "llm_sql_generation"}

data: {"type": "stage_end", "stage": "sql_validation", "timestamp": "..."}

data: {"type": "pipeline_complete", "result": {...}}
```

### 3. SQL 생성 및 즉시 실행
```http
POST /api/lcel-sql/execute-and-run
Content-Type: application/json

{
    "query": "최근 가입한 고객 10명 목록",
    "strategy": "rule_first",
    "limit": 10
}
```

### 4. 실행 전략 목록 조회
```http
GET /api/lcel-sql/strategies
```

### 5. 파이프라인 상태 확인
```http
GET /api/lcel-sql/health
```

## 실행 전략 상세

### LLM First (추천)
```python
request = EnhancedSQLGenerationRequest(
    query="복잡한 자연어 쿼리",
    strategy=ExecutionStrategy.LLM_FIRST
)
```
- **장점**: 높은 정확도, 복잡한 쿼리 처리 가능
- **단점**: LLM 비용 발생, 응답 시간 다소 느림
- **사용 사례**: 복잡한 분석 쿼리, 높은 정확도 필요

### Rule First
```python
request = EnhancedSQLGenerationRequest(
    query="간단한 조회 쿼리",
    strategy=ExecutionStrategy.RULE_FIRST
)
```
- **장점**: 빠른 응답, 비용 절약
- **단점**: 제한적인 쿼리 패턴만 처리
- **사용 사례**: 정형화된 쿼리, 대량 처리

### Hybrid (최고 품질)
```python
request = EnhancedSQLGenerationRequest(
    query="중요한 분석 쿼리",
    strategy=ExecutionStrategy.HYBRID
)
```
- **장점**: 최고 품질 보장, LLM과 규칙의 장점 결합
- **단점**: 응답 시간 증가, 비용 증가
- **사용 사례**: 중요한 비즈니스 쿼리, 품질 우선

### LLM Only
```python
request = EnhancedSQLGenerationRequest(
    query="창의적 쿼리",
    strategy=ExecutionStrategy.LLM_ONLY
)
```
- **장점**: 창의적 쿼리 생성, LLM 성능 최대 활용
- **단점**: Fallback 없음, 실패 위험
- **사용 사례**: 실험적 쿼리, LLM 성능 테스트

### Rule Only
```python
request = EnhancedSQLGenerationRequest(
    query="표준 패턴 쿼리",
    strategy=ExecutionStrategy.RULE_ONLY
)
```
- **장점**: 비용 없음, 빠른 응답, 예측 가능
- **단점**: 제한된 기능, 복잡한 쿼리 불가
- **사용 사례**: 대량 배치 처리, 비용 최적화

## Python 클라이언트 사용법

### 기본 사용
```python
import asyncio
from app.services.lcel_sql_pipeline import (
    lcel_sql_pipeline, 
    EnhancedSQLGenerationRequest, 
    ExecutionStrategy
)

async def generate_sql_example():
    request = EnhancedSQLGenerationRequest(
        query="홍길동 고객의 최근 3개월 거래 내역",
        strategy=ExecutionStrategy.LLM_FIRST,
        context={"user_id": "analyst_123"},
        timeout_seconds=30.0
    )
    
    result = await lcel_sql_pipeline.generate_sql(request)
    
    if result.success:
        print(f"생성된 SQL: {result.sql_result.sql}")
        print(f"설명: {result.sql_result.explanation}")
        print(f"신뢰도: {result.sql_result.confidence:.2f}")
    else:
        print(f"오류: {result.error_message}")

# 실행
asyncio.run(generate_sql_example())
```

### 스트리밍 사용
```python
async def streaming_example():
    request = EnhancedSQLGenerationRequest(
        query="월별 매출 트렌드 분석",
        strategy=ExecutionStrategy.HYBRID,
        enable_streaming=True
    )
    
    async for event in lcel_sql_pipeline.generate_sql_streaming(request):
        event_type = event.get("type")
        
        if event_type == "stage_start":
            print(f"🔄 단계 시작: {event['stage']}")
        elif event_type == "token":
            print(f"🔤 토큰: {event['content']}", end="")
        elif event_type == "pipeline_complete":
            print("\n✅ 완료!")
            result = event["result"]
            print(f"최종 SQL: {result['sql_result']['sql']}")

asyncio.run(streaming_example())
```

### 재시도 설정
```python
from app.services.lcel_sql_pipeline import RetryConfig

async def retry_example():
    retry_config = RetryConfig(
        max_attempts=5,           # 최대 5회 시도
        base_delay=0.5,          # 첫 번째 재시도 0.5초 후
        max_delay=30.0,          # 최대 30초 대기
        exponential_base=2.0,    # 2배씩 증가
        jitter=True,             # 랜덤 지터 추가
        retriable_exceptions=[   # 재시도 가능한 예외들
            "RateLimitError",
            "APITimeoutError", 
            "ServiceUnavailableError"
        ]
    )
    
    request = EnhancedSQLGenerationRequest(
        query="복잡한 분석 쿼리",
        strategy=ExecutionStrategy.LLM_FIRST,
        retry_config=retry_config
    )
    
    result = await lcel_sql_pipeline.generate_sql(request)
    return result

asyncio.run(retry_example())
```

## 성능 최적화

### 1. 적절한 전략 선택
- **간단한 쿼리**: `rule_first` 또는 `rule_only`
- **복잡한 쿼리**: `llm_first` 또는 `hybrid`
- **중요한 쿼리**: `hybrid`로 품질 보장

### 2. 타임아웃 설정
```python
request = EnhancedSQLGenerationRequest(
    query="쿼리",
    timeout_seconds=10.0  # 10초 타임아웃
)
```

### 3. 캐싱 활용
```python
request = EnhancedSQLGenerationRequest(
    query="반복 쿼리",
    enable_caching=True  # 캐싱 활성화
)
```

### 4. 스트리밍으로 사용자 경험 개선
```python
# 긴 처리시간 예상 시 스트리밍 사용
request = EnhancedSQLGenerationRequest(
    query="복잡한 쿼리",
    enable_streaming=True
)
```

## 모니터링 & 디버깅

### LangSmith 추적 확인
1. LangSmith 대시보드 접속
2. 프로젝트: `lcel-sql-pipeline` 확인
3. 각 체인별 실행 시간과 결과 분석
4. 오류 발생 지점 상세 로그 확인

### 로그 레벨 설정
```python
import logging
logging.getLogger('app.services.lcel_sql_pipeline').setLevel(logging.DEBUG)
```

### 메트릭 수집
```python
# 응답에서 메트릭 확인
result = await lcel_sql_pipeline.generate_sql(request)
metrics = result.metrics

print(f"실행 시간: {metrics['total_duration']:.2f}초")
print(f"사용된 전략: {metrics['strategy_used']}")
print(f"생성 방법: {result.sql_result.generation_method}")
```

## 보안 고려사항

### SQL 검증
- 모든 생성된 SQL은 자동으로 보안 검증
- 위험한 쿼리는 기본 안전 쿼리로 대체
- SQL Injection 패턴 자동 탐지

### 파라미터화 쿼리
```python
# 생성된 SQL은 파라미터화됨
result = await lcel_sql_pipeline.generate_sql(request)
sql = result.sql_result.sql          # "SELECT * FROM users WHERE name = %(name)s"
params = result.sql_result.parameters # {"name": "홍길동"}
```

### 읽기 전용 실행
- `execute-and-run` 엔드포인트는 읽기 전용 DB 사용
- SELECT 쿼리만 실행 가능
- 자동 LIMIT 적용 (최대 100행)

## 문제 해결

### 일반적인 오류

1. **파이프라인 실행 시간 초과**
```python
# 타임아웃 증가
request = EnhancedSQLGenerationRequest(
    query="복잡한 쿼리",
    timeout_seconds=60.0  # 1분으로 증가
)
```

2. **LLM 호출 실패**
```python
# Rule-based 전략으로 우회
request = EnhancedSQLGenerationRequest(
    query="쿼리",
    strategy=ExecutionStrategy.RULE_FIRST
)
```

3. **의도 분류 정확도 낮음**
```python
# 하이브리드 전략으로 품질 향상
request = EnhancedSQLGenerationRequest(
    query="모호한 쿼리",
    strategy=ExecutionStrategy.HYBRID
)
```

### 디버깅 도구

#### 파이프라인 상태 확인
```bash
curl http://localhost:8000/api/lcel-sql/health
```

#### 단계별 실행 추적
```python
# 스트리밍으로 각 단계 확인
async for event in lcel_sql_pipeline.generate_sql_streaming(request):
    print(f"[{event['type']}] {event.get('stage', '')}: {event.get('data', '')}")
```

## 성능 벤치마크

| 전략 | 평균 응답시간 | 성공률 | 정확도 | 비용 |
|------|-------------|--------|--------|------|
| LLM First | 3-5초 | 95% | 높음 | 높음 |
| Rule First | 0.1-0.5초 | 85% | 중간 | 낮음 |
| Hybrid | 4-6초 | 98% | 최고 | 최고 |
| LLM Only | 2-4초 | 90% | 높음 | 높음 |
| Rule Only | 0.1초 | 80% | 낮음 | 없음 |

## FAQ

**Q: 어떤 전략을 선택해야 하나요?**
A: 일반적으로 `llm_first`를 추천합니다. 간단한 쿼리가 많다면 `rule_first`, 최고 품질이 필요하면 `hybrid`를 사용하세요.

**Q: 스트리밍이 필요한가요?**
A: 복잡한 쿼리나 사용자 대기 시간이 긴 경우 스트리밍으로 사용자 경험을 개선할 수 있습니다.

**Q: 재시도 설정은 어떻게 하나요?**
A: 네트워크 불안정하거나 외부 API 의존성이 높은 환경에서는 재시도 설정을 늘리는 것을 권장합니다.

**Q: LangSmith 추적이 필수인가요?**
A: 필수는 아니지만, 프로덕션 환경에서는 모니터링과 디버깅을 위해 활성화를 강력히 권장합니다.

## 업데이트 로그

- **v2.0**: LCEL 파이프라인 아키텍처 도입
- **v2.1**: 스트리밍 응답 지원 추가
- **v2.2**: Hybrid 전략 성능 개선
- **v2.3**: 재시도 로직 안정성 향상

## 참고 자료

- [LangChain Expression Language 공식 문서](https://python.langchain.com/docs/expression_language/)
- [LangSmith 추적 가이드](https://docs.smith.langchain.com/)
- [의도 분류기 가이드](./INTENT_CLASSIFIER_GUIDE.md)
- [자연어 검색 프롬프트 가이드](./NL_SEARCH_PROMPTS_GUIDE.md)