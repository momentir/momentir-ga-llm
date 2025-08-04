# 🚀 프롬프트 관리 시스템 사용 매뉴얼

## 📋 개요

동적 프롬프트 관리 시스템을 통해 LLM 프롬프트를 데이터베이스에서 관리하고, 버전 관리, A/B 테스트를 수행할 수 있습니다.

## 🔧 시스템 구성

### 1. 핵심 기능
- **동적 프롬프트 로딩**: 데이터베이스에서 프롬프트를 실시간으로 로드
- **버전 관리**: 프롬프트의 여러 버전을 관리하고 추적
- **A/B 테스트**: 두 개의 프롬프트 버전을 비교 테스트
- **성능 분석**: A/B 테스트 결과를 통한 프롬프트 최적화

### 2. API 엔드포인트
- **프롬프트 관리**: `/api/prompts/`
- **API 문서**: `http://localhost:8000/docs#/prompts`

## 📚 API 사용 가이드

### 1. 프롬프트 템플릿 생성

```bash
curl -X POST "http://localhost:8000/api/prompts/templates" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "memo_refine_v2",
    "category": "memo_refinement",
    "description": "개선된 메모 정제 프롬프트",
    "default_version": "1.0"
  }'
```

### 2. 프롬프트 버전 생성

```bash
curl -X POST "http://localhost:8000/api/prompts/templates/{template_id}/versions" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "2.0",
    "content": "당신은 보험 고객 메모를 정제하는 AI입니다...",
    "variables": ["memo", "customer_type"],
    "is_active": true
  }'
```

### 3. 프롬프트 렌더링 (실제 사용)

```bash
curl -X POST "http://localhost:8000/api/prompts/render" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "memo_refine_v2",
    "category": "memo_refinement",
    "variables": {
      "memo": "고객이 보험료 인상에 대해 불만을 표현했습니다.",
      "customer_type": "기존고객"
    },
    "user_session": "user123"
  }'
```

### 4. A/B 테스트 생성

```bash
curl -X POST "http://localhost:8000/api/prompts/ab-tests" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "memo_refine_test",
    "template_id": "{template_id}",
    "version_a": "1.0",
    "version_b": "2.0",
    "traffic_split": 0.5,
    "start_date": "2024-08-04T00:00:00Z",
    "end_date": "2024-08-11T00:00:00Z"
  }'
```

### 5. A/B 테스트 결과 기록

```bash
curl -X POST "http://localhost:8000/api/prompts/ab-tests/{test_id}/results" \
  -H "Content-Type: application/json" \
  -d '{
    "version_used": "2.0",
    "user_session": "user123",
    "success": true,
    "response_time": 1.5,
    "user_feedback": 4.5,
    "metadata": {
      "memo_length": 150,
      "processing_time": 2.3
    }
  }'
```

## 🎯 실제 사용 예시

### 시나리오 1: 기존 프롬프트 개선

1. **현재 프롬프트 확인**
```bash
curl -X GET "http://localhost:8000/api/prompts/templates?category=memo_refinement"
```

2. **새 버전 생성**
```bash
curl -X POST "http://localhost:8000/api/prompts/templates/memo_refine/versions" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "2.1",
    "content": "개선된 프롬프트 내용...",
    "variables": ["memo", "customer_type", "context"],
    "is_active": false
  }'
```

3. **A/B 테스트 설정**
```bash
curl -X POST "http://localhost:8000/api/prompts/ab-tests" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "memo_refine_improvement_test",
    "template_id": "{template_id}",
    "version_a": "2.0",
    "version_b": "2.1",
    "traffic_split": 0.3
  }'
```

### 시나리오 2: 프롬프트 성능 모니터링

1. **A/B 테스트 통계 확인**
```bash
curl -X GET "http://localhost:8000/api/prompts/ab-tests/{test_id}/stats"
```

**응답 예시:**
```json
{
  "test_name": "memo_refine_improvement_test",
  "total_requests": 1000,
  "version_a_stats": {
    "requests": 700,
    "success_rate": 0.94,
    "avg_response_time": 1.8,
    "avg_user_feedback": 4.2
  },
  "version_b_stats": {
    "requests": 300,
    "success_rate": 0.97,
    "avg_response_time": 1.6,
    "avg_user_feedback": 4.6
  },
  "winner": "version_b",
  "confidence": 0.95
}
```

## 🔄 자동화된 프롬프트 로딩

### 기존 서비스 통합

시스템이 자동으로 다음 서비스들에 동적 프롬프트를 적용합니다:

1. **메모 정제 서비스** (`memo_refiner.py`)
   - 카테고리: `memo_refinement`
   - 템플릿: `memo_refine`

2. **고객 서비스** (`customer_service.py`)  
   - 카테고리: `column_mapping`
   - 템플릿: `column_mapping`

3. **조건부 분석** (`memo_refiner.py`)
   - 카테고리: `conditional_analysis`
   - 템플릿: `conditional_analysis`

### 동적 로딩 동작

```python
# 자동으로 실행되는 코드
if self.use_dynamic_prompts:
    system_prompt = await get_memo_refine_prompt(memo, user_session, db_session)
else:
    system_prompt = "하드코딩된 기본 프롬프트..."
```

## 📊 모니터링 및 분석

### 1. 프롬프트 사용량 추적

```bash
curl -X GET "http://localhost:8000/api/prompts/templates/{template_id}/usage-stats"
```

### 2. A/B 테스트 결과 분석

```bash
curl -X GET "http://localhost:8000/api/prompts/ab-tests/active"
```

### 3. 성능 지표 확인

```bash
curl -X GET "http://localhost:8000/api/prompts/performance-metrics?days=7"
```

## 🛠️ 고급 사용법

### 1. 프롬프트 변수 동적 설정

```python
# 사용자 정보에 따른 동적 변수
variables = {
    "memo": memo_content,
    "customer_type": customer.type,
    "contract_status": customer.contract_status,
    "time_context": datetime.now().strftime("%Y-%m-%d %H:%M")
}
```

### 2. 조건부 프롬프트 로딩

```python
# 고객 유형에 따른 다른 프롬프트 사용
if customer.type == "VIP":
    template_name = "memo_refine_vip"
else:
    template_name = "memo_refine_standard"
```

### 3. A/B 테스트 세그멘테이션

```bash
# 특정 고객군에만 적용되는 A/B 테스트
curl -X POST "http://localhost:8000/api/prompts/ab-tests" \
  -d '{
    "name": "vip_customer_test",
    "template_id": "{template_id}",
    "version_a": "1.0",
    "version_b": "2.0",
    "traffic_split": 0.5,
    "segment_filter": {"customer_type": "VIP"}
  }'
```

## 🚨 주의사항

### 1. 프롬프트 변경 시 주의점
- A/B 테스트 진행 중인 프롬프트는 함부로 수정하지 마세요
- 버전 변경 시 기존 결과에 영향을 줄 수 있습니다

### 2. 성능 고려사항
- 프롬프트 로딩은 캐시되므로 즉시 반영되지 않을 수 있습니다
- 대량의 A/B 테스트는 성능에 영향을 줄 수 있습니다

### 3. 데이터 일관성
- A/B 테스트 결과는 충분한 샘플 수집 후 판단하세요
- 통계적 유의성을 확인한 후 프롬프트를 변경하세요

## 📈 베스트 프랙티스

### 1. 프롬프트 개발 워크플로우
1. 기존 프롬프트 성능 분석
2. 새 버전 개발 및 테스트
3. A/B 테스트 설정 (30% 트래픽)
4. 1주일간 데이터 수집
5. 통계 분석 후 우수 버전 적용

### 2. 네이밍 컨벤션
- 템플릿: `{service}_{purpose}_v{major}`
- 버전: `{major}.{minor}.{patch}`
- A/B 테스트: `{template}_{purpose}_test_{date}`

### 3. 버전 관리
- 메이저 변경: 프롬프트 구조 변경
- 마이너 변경: 내용 개선
- 패치: 오타 수정, 소규모 개선

이제 프롬프트 관리 시스템을 통해 AI 모델의 성능을 지속적으로 개선할 수 있습니다! 🎉