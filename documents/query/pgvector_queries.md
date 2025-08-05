# pgvector 임베딩 데이터 조회 가이드

DBeaver에서 pgvector를 사용한 임베딩 데이터를 조회하고 분석하기 위한 유용한 SQL 쿼리 모음입니다.

## 기본 데이터 확인

### 1. 임베딩이 있는 메모 개수 확인
```sql
SELECT COUNT(*) as total_memos_with_embeddings
FROM customer_memos 
WHERE embedding IS NOT NULL;
```

### 2. 임베딩 차원 확인
```sql
SELECT 
    id,
    customer_id,
    SUBSTRING(original_memo, 1, 50) as memo_preview,
    array_length(embedding::float[], 1) as embedding_dimension,
    created_at
FROM customer_memos 
WHERE embedding IS NOT NULL
LIMIT 10;
```

### 3. 최근 임베딩 데이터 조회
```sql
SELECT 
    id,
    customer_id,
    original_memo,
    refined_memo,
    status,
    author,
    created_at,
    CASE 
        WHEN embedding IS NOT NULL THEN '✅ 임베딩 있음'
        ELSE '❌ 임베딩 없음'
    END as embedding_status
FROM customer_memos 
ORDER BY created_at DESC
LIMIT 20;
```

## pgvector 유사도 검색

### 4. 특정 텍스트와 유사한 메모 찾기 (수동 벡터 입력)
```sql
-- 주의: 실제 1536차원 벡터를 입력해야 합니다
SELECT 
    id,
    customer_id,
    original_memo,
    refined_memo,
    1 - (embedding <=> '[0.1, 0.2, 0.3, ...]'::vector) as similarity_score,
    created_at
FROM customer_memos 
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, 0.3, ...]'::vector
LIMIT 10;
```

### 5. 코사인 거리 기반 유사도 분포 확인
```sql
WITH similarity_stats AS (
    SELECT 
        a.id as memo1_id,
        b.id as memo2_id,
        1 - (a.embedding <=> b.embedding) as similarity_score
    FROM customer_memos a, customer_memos b
    WHERE a.embedding IS NOT NULL 
      AND b.embedding IS NOT NULL
      AND a.id < b.id  -- 중복 제거
    LIMIT 100  -- 성능을 위해 제한
)
SELECT 
    ROUND(similarity_score::numeric, 2) as similarity_range,
    COUNT(*) as count
FROM similarity_stats
GROUP BY ROUND(similarity_score::numeric, 2)
ORDER BY similarity_range DESC;
```

### 6. 특정 메모와 가장 유사한 메모들 찾기
```sql
WITH target_memo AS (
    SELECT embedding
    FROM customer_memos 
    WHERE id = 1  -- 대상 메모 ID
)
SELECT 
    cm.id,
    cm.customer_id,
    SUBSTRING(cm.original_memo, 1, 100) as memo_preview,
    1 - (cm.embedding <=> tm.embedding) as similarity_score,
    cm.created_at
FROM customer_memos cm, target_memo tm
WHERE cm.embedding IS NOT NULL
  AND cm.id != 1  -- 자기 자신 제외
ORDER BY cm.embedding <=> tm.embedding
LIMIT 10;
```

## 벡터 분석 및 통계

### 7. 임베딩 벡터의 통계 정보
```sql
SELECT 
    COUNT(*) as total_vectors,
    AVG(array_length(embedding::float[], 1)) as avg_dimension,
    MIN(array_length(embedding::float[], 1)) as min_dimension,
    MAX(array_length(embedding::float[], 1)) as max_dimension
FROM customer_memos 
WHERE embedding IS NOT NULL;
```

### 8. 벡터 노름(크기) 분석
```sql
SELECT 
    id,
    customer_id,
    SUBSTRING(original_memo, 1, 50) as memo_preview,
    sqrt(
        (SELECT SUM(val * val) 
         FROM unnest(embedding::float[]) AS val)
    ) as vector_norm,
    created_at
FROM customer_memos 
WHERE embedding IS NOT NULL
ORDER BY vector_norm DESC
LIMIT 20;
```

### 9. 고객별 임베딩 데이터 통계
```sql
SELECT 
    customer_id,
    COUNT(*) as memo_count,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embeddings_count,
    ROUND(
        COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as embedding_coverage_percent
FROM customer_memos
GROUP BY customer_id
ORDER BY embeddings_count DESC;
```

## 인덱스 및 성능 확인

### 10. pgvector 인덱스 상태 확인
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'customer_memos' 
  AND indexdef LIKE '%embedding%';
```

### 11. 인덱스 사용량 통계
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes 
WHERE tablename = 'customer_memos'
  AND indexname LIKE '%embedding%';
```

### 12. 테이블 크기 및 인덱스 크기 확인
```sql
SELECT 
    'customer_memos' as table_name,
    pg_size_pretty(pg_total_relation_size('customer_memos')) as total_size,
    pg_size_pretty(pg_relation_size('customer_memos')) as table_size,
    pg_size_pretty(
        pg_total_relation_size('customer_memos') - pg_relation_size('customer_memos')
    ) as indexes_size;
```

## 데이터 검증 및 품질 확인

### 13. NULL 또는 빈 임베딩 확인
```sql
SELECT 
    'NULL 임베딩' as issue_type,
    COUNT(*) as count
FROM customer_memos 
WHERE embedding IS NULL

UNION ALL

SELECT 
    '빈 배열 임베딩' as issue_type,
    COUNT(*) as count
FROM customer_memos 
WHERE embedding IS NOT NULL 
  AND array_length(embedding::float[], 1) = 0

UNION ALL

SELECT 
    '차원 불일치' as issue_type,
    COUNT(*) as count
FROM customer_memos 
WHERE embedding IS NOT NULL 
  AND array_length(embedding::float[], 1) != 1536;
```

### 14. 중복 임베딩 검출
```sql
WITH duplicate_embeddings AS (
    SELECT 
        embedding,
        COUNT(*) as count,
        array_agg(id) as memo_ids
    FROM customer_memos 
    WHERE embedding IS NOT NULL
    GROUP BY embedding
    HAVING COUNT(*) > 1
)
SELECT 
    count as duplicate_count,
    memo_ids,
    array_length(embedding::float[], 1) as dimension
FROM duplicate_embeddings
ORDER BY duplicate_count DESC;
```

## 성능 최적화 쿼리

### 15. 유사도 검색 실행 계획 확인
```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT id, original_memo, 1 - (embedding <=> '[0.1,0.2,0.3,...]'::vector) as similarity
FROM customer_memos 
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1,0.2,0.3,...]'::vector
LIMIT 10;
```

### 16. 배치 처리용 임베딩 업데이트 확인
```sql
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_memos,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
    COUNT(CASE WHEN embedding IS NULL THEN 1 END) as without_embeddings
FROM customer_memos
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

## 사용 팁

1. **벡터 입력**: 실제 유사도 검색을 위해서는 OpenAI API를 통해 생성된 1536차원 벡터를 사용해야 합니다.

2. **성능**: 큰 데이터셋에서는 LIMIT을 사용하여 결과를 제한하세요.

3. **인덱스**: IVFFLAT 인덱스가 생성되어 있는지 확인하고, 필요시 재생성하세요:
   ```sql
   CREATE INDEX CONCURRENTLY idx_customer_memos_embedding_cosine 
   ON customer_memos USING ivfflat (embedding vector_cosine_ops) 
   WITH (lists = 100);
   ```

4. **모니터링**: 정기적으로 인덱스 사용량과 쿼리 성능을 모니터링하세요.