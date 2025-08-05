```sql
-- 기본 조회
SELECT
id as prompt_id,
prompt_content,
memo_content,
llm_response,
created_at as request_datetime
FROM prompt_test_logs
ORDER BY created_at DESC
LIMIT 100;

-- 성공한 테스트만
SELECT * FROM prompt_test_logs WHERE success = true;

-- 날짜 범위 조회
SELECT * FROM prompt_test_logs
WHERE created_at >= NOW() - INTERVAL '7 days';
```