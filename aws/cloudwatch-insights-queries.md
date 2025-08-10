# CloudWatch Insights 쿼리 템플릿

## 📊 ECS Fargate 환경용 CloudWatch Insights 쿼리 모음

이 문서는 Momentir GA LLM 서비스의 CloudWatch Logs 분석을 위한 Insights 쿼리 템플릿을 제공합니다.

### 전제 조건
- ECS Fargate 로그 그룹: `/ecs/momentir-cx-llm`
- JSON 구조화 로깅 활성화
- CloudWatch Logs 보존 기간 설정

---

## 🔍 자주 사용하는 검색어 분석

### 1. 최근 24시간 인기 검색어 TOP 10
```sql
fields @timestamp, message.query, message.result_count, message.response_time
| filter message.event_type = "search_query"
| filter message.success = true
| filter @timestamp > now() - 24h
| stats count() as search_count, avg(message.response_time) as avg_response_time by message.query
| sort search_count desc
| limit 10
```

### 2. 검색 성공률이 낮은 쿼리 (80% 미만)
```sql
fields @timestamp, message.query, message.success, message.error_message
| filter message.event_type = "search_query"
| filter @timestamp > now() - 7d
| stats count() as total_attempts, sum(case when message.success = true then 1 else 0 end) as successful_attempts by message.query
| filter total_attempts >= 5
| eval success_rate = successful_attempts / total_attempts * 100
| filter success_rate < 80
| sort success_rate asc
| limit 20
```

### 3. 사용자별 검색 패턴 분석
```sql
fields @timestamp, message.user_id, message.query, message.strategy, message.response_time
| filter message.event_type = "search_query"
| filter @timestamp > now() - 7d
| stats count() as search_count, 
        avg(message.response_time) as avg_response_time,
        countDistinct(message.query) as unique_queries by message.user_id
| sort search_count desc
| limit 50
```

---

## ⚡ 성능 분석

### 4. 응답 시간 분포 분석 (P50, P90, P99)
```sql
fields @timestamp, message.response_time, message.strategy
| filter message.event_type = "search_query"
| filter message.success = true
| filter @timestamp > now() - 24h
| stats count() as request_count,
        pct(message.response_time, 50) as p50_response_time,
        pct(message.response_time, 90) as p90_response_time,
        pct(message.response_time, 99) as p99_response_time,
        avg(message.response_time) as avg_response_time,
        max(message.response_time) as max_response_time by message.strategy
| sort avg_response_time desc
```

### 5. 성능 이상 요청 (3초 초과)
```sql
fields @timestamp, message.query, message.strategy, message.response_time, message.result_count
| filter message.event_type = "search_query"
| filter message.response_time > 3
| filter @timestamp > now() - 24h
| sort @timestamp desc
| limit 100
```

### 6. 시간대별 응답 시간 트렌드
```sql
fields @timestamp, message.response_time
| filter message.event_type = "search_query"
| filter message.success = true
| filter @timestamp > now() - 24h
| bin(@timestamp, 1h) as hour_bucket
| stats avg(message.response_time) as avg_response_time,
        count() as request_count by hour_bucket
| sort hour_bucket asc
```

---

## 🚨 에러 패턴 분석

### 7. 에러 타입별 집계
```sql
fields @timestamp, message.error_message, message.query
| filter message.event_type = "search_query"
| filter message.success = false
| filter @timestamp > now() - 7d
| stats count() as error_count by message.error_message
| sort error_count desc
| limit 20
```

### 8. SQL 생성 실패 패턴
```sql
fields @timestamp, message.query, message.error_message, message.strategy
| filter message.event_type = "search_query"
| filter message.success = false
| filter message.error_message like /SQL 생성/
| filter @timestamp > now() - 7d
| stats count() as failure_count by message.strategy, message.error_message
| sort failure_count desc
```

### 9. 데이터베이스 연결 오류
```sql
fields @timestamp, message.error_message, ecs_metadata.task_arn
| filter message.error_message like /database|connection|timeout/
| filter @timestamp > now() - 24h
| stats count() as error_count by ecs_metadata.task_arn, bin(@timestamp, 10m)
| sort @timestamp desc
```

---

## 📈 비즈니스 분석

### 10. 검색 카테고리별 사용 빈도
```sql
fields @timestamp, message.query, message.result_count
| filter message.event_type = "search_query"
| filter message.success = true
| filter @timestamp > now() - 7d
| eval category = case
    when message.query like /고객|customer/ then "고객조회"
    when message.query like /보험|insurance/ then "보험상품"
    when message.query like /만기|expiry/ then "만기관리"
    when message.query like /분석|analysis/ then "데이터분석"
    else "기타"
| stats count() as search_count,
        avg(message.result_count) as avg_results,
        avg(message.response_time) as avg_response_time by category
| sort search_count desc
```

### 11. 시간대별 사용량 패턴
```sql
fields @timestamp, message.user_id
| filter message.event_type = "search_query"
| filter @timestamp > now() - 7d
| eval hour_of_day = datefloor(@timestamp, 1h)
| eval hour = strftime(hour_of_day, "%H")
| stats count() as search_count,
        countDistinct(message.user_id) as active_users by hour
| sort hour asc
```

### 12. 검색 결과 크기별 분포
```sql
fields @timestamp, message.query, message.result_count
| filter message.event_type = "search_query"
| filter message.success = true
| filter @timestamp > now() - 24h
| eval result_category = case
    when message.result_count = 0 then "결과없음"
    when message.result_count <= 10 then "소량(1-10)"
    when message.result_count <= 100 then "중량(11-100)"
    when message.result_count <= 1000 then "대량(101-1000)"
    else "초대량(1000+)"
| stats count() as query_count,
        avg(message.response_time) as avg_response_time by result_category
| sort query_count desc
```

---

## 🏗️ 시스템 모니터링

### 13. ECS Task별 성능 메트릭
```sql
fields @timestamp, ecs_metadata.task_arn, message.response_time
| filter message.event_type = "performance_metrics"
| filter @timestamp > now() - 4h
| stats avg(message.cpu_percent) as avg_cpu,
        avg(message.memory_percent) as avg_memory,
        count() as metric_points by ecs_metadata.task_arn
| sort avg_cpu desc
```

### 14. API 엔드포인트별 사용량
```sql
fields @timestamp, message.endpoint, message.method, message.success
| filter message.event_type = "api_request_detailed"
| filter @timestamp > now() - 24h
| stats count() as request_count,
        sum(case when message.success = true then 1 else 0 end) as successful_requests,
        avg(message.response_time) as avg_response_time by message.endpoint, message.method
| eval success_rate = successful_requests / request_count * 100
| sort request_count desc
| limit 20
```

### 15. 메모리 사용량 추이
```sql
fields @timestamp, message.memory_used_mb, message.memory_percent
| filter message.event_type = "performance_metrics"
| filter @timestamp > now() - 6h
| bin(@timestamp, 5m) as time_bucket
| stats avg(message.memory_used_mb) as avg_memory_mb,
        max(message.memory_percent) as max_memory_percent by time_bucket
| sort time_bucket asc
```

---

## 🔧 트러블슈팅

### 16. 특정 시간대 로그 집중 분석
```sql
fields @timestamp, @message, level
| filter @timestamp > "2024-01-15T10:00:00.000Z" 
| filter @timestamp < "2024-01-15T11:00:00.000Z"
| filter level = "ERROR" or level = "WARNING"
| sort @timestamp desc
| limit 500
```

### 17. 동시 요청 부하 패턴
```sql
fields @timestamp, message.endpoint
| filter message.event_type = "api_request_detailed"
| filter @timestamp > now() - 1h
| bin(@timestamp, 1m) as minute_bucket
| stats count() as concurrent_requests by minute_bucket
| sort concurrent_requests desc
| limit 60
```

### 18. CloudWatch 메트릭 플러시 실패
```sql
fields @timestamp, message.message, message.error_message
| filter message.message like /Failed to flush metrics to CloudWatch/
| filter @timestamp > now() - 24h
| stats count() as failure_count by bin(@timestamp, 1h)
| sort @timestamp desc
```

---

## 📊 대시보드 생성용 쿼리

### 19. 실시간 KPI 요약 (5분 간격)
```sql
fields @timestamp, message.success, message.response_time, message.result_count
| filter message.event_type = "search_query"
| filter @timestamp > now() - 1h
| bin(@timestamp, 5m) as time_bucket
| stats count() as total_requests,
        sum(case when message.success = true then 1 else 0 end) as successful_requests,
        avg(message.response_time) as avg_response_time,
        avg(message.result_count) as avg_result_count by time_bucket
| eval success_rate = successful_requests / total_requests * 100
| sort time_bucket asc
```

### 20. 서비스 헬스 체크 요약
```sql
fields @timestamp, message.event_type, message.success, level
| filter @timestamp > now() - 10m
| stats count() as total_events,
        sum(case when level = "ERROR" then 1 else 0 end) as error_count,
        sum(case when level = "WARNING" then 1 else 0 end) as warning_count,
        sum(case when message.success = true then 1 else 0 end) as success_count by bin(@timestamp, 1m)
| sort @timestamp desc
| limit 10
```

---

## 🎯 사용 방법

### CloudWatch Insights에서 쿼리 실행하기

1. **AWS 콘솔에서 CloudWatch 서비스 접근**
2. **Insights 메뉴 선택**
3. **로그 그룹 선택**: `/ecs/momentir-cx-llm`
4. **시간 범위 설정**: 원하는 분석 기간
5. **쿼리 입력**: 위의 템플릿 중 하나 복사/붙여넣기
6. **실행**: "Run query" 버튼 클릭

### 주의사항

- 쿼리 실행 시 로그 양에 따라 비용이 발생할 수 있습니다
- 대량 데이터 분석 시 시간 범위를 적절히 조정하세요
- JSON 필드명이 변경될 경우 쿼리를 업데이트해야 합니다

### 자주 사용하는 필터

```sql
# 성공한 검색만
| filter message.success = true

# 특정 사용자의 요청만
| filter message.user_id = 123

# 응답 시간이 느린 요청만
| filter message.response_time > 2.0

# 특정 전략 사용 요청만
| filter message.strategy = "llm_first"

# 에러가 발생한 요청만
| filter level = "ERROR"
```