#!/bin/bash

# 검색 분석 시스템 테스트 스크립트
echo "🔍 검색 분석 시스템 테스트 시작"
echo "=================================="

# 1. 서버 상태 확인
echo "1. 서버 상태 확인 중..."
if curl -s http://127.0.0.1:8000/health > /dev/null; then
    echo "✅ 서버가 실행 중입니다"
else
    echo "❌ 서버가 실행 중이지 않습니다. 먼저 서버를 시작하세요:"
    echo "   ./scripts/02-environment/02-start-local.sh"
    exit 1
fi

# 2. API 엔드포인트 테스트
echo ""
echo "2. API 엔드포인트 테스트 중..."

# 2-1. 대시보드 데이터 조회
echo "  - 대시보드 데이터 조회..."
dashboard_response=$(curl -s "http://127.0.0.1:8000/v1/api/search-analytics/dashboard?days=7")
if [[ $? -eq 0 ]]; then
    echo "  ✅ 대시보드 API 응답 성공"
    echo "     응답: ${dashboard_response:0:100}..."
else
    echo "  ❌ 대시보드 API 실패"
fi

# 2-2. 인기 검색어 조회
echo "  - 인기 검색어 조회..."
popular_response=$(curl -s "http://127.0.0.1:8000/v1/api/search-analytics/popular-queries?limit=5&days=7")
if [[ $? -eq 0 ]]; then
    echo "  ✅ 인기 검색어 API 응답 성공"
    echo "     응답: ${popular_response:0:100}..."
else
    echo "  ❌ 인기 검색어 API 실패"
fi

# 2-3. 성능 통계 조회
echo "  - 성능 통계 조회..."
performance_response=$(curl -s "http://127.0.0.1:8000/v1/api/search-analytics/performance-stats?days=7")
if [[ $? -eq 0 ]]; then
    echo "  ✅ 성능 통계 API 응답 성공"
    echo "     응답: ${performance_response:0:100}..."
else
    echo "  ❌ 성능 통계 API 실패"
fi

# 2-4. 실패 패턴 조회
echo "  - 실패 패턴 조회..."
failure_response=$(curl -s "http://127.0.0.1:8000/v1/api/search-analytics/failure-patterns?limit=5&min_failure_rate=0.5")
if [[ $? -eq 0 ]]; then
    echo "  ✅ 실패 패턴 API 응답 성공"
    echo "     응답: ${failure_response:0:100}..."
else
    echo "  ❌ 실패 패턴 API 실패"
fi

# 3. 데이터베이스 테이블 확인
echo ""
echo "3. 데이터베이스 테이블 확인 중..."

# PostgreSQL 연결 테스트
if command -v psql &> /dev/null; then
    echo "  - search_history 테이블 확인..."
    table_check=$(PGPASSWORD="5JYbqQeiuQI7tYNaDoFAnp0oL" psql -h momentir-cx.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com -U dbadmin -d momentir-cx-llm -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'search_history';" 2>/dev/null)
    
    if [[ $table_check =~ [1-9] ]]; then
        echo "  ✅ search_history 테이블 존재"
    else
        echo "  ❌ search_history 테이블 없음 - 마이그레이션 필요"
        echo "     실행: alembic upgrade head"
    fi
    
    echo "  - search_analytics 테이블 확인..."
    table_check2=$(PGPASSWORD="5JYbqQeiuQI7tYNaDoFAnp0oL" psql -h momentir-cx.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com -U dbadmin -d momentir-cx-llm -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'search_analytics';" 2>/dev/null)
    
    if [[ $table_check2 =~ [1-9] ]]; then
        echo "  ✅ search_analytics 테이블 존재"
    else
        echo "  ❌ search_analytics 테이블 없음 - 마이그레이션 필요"
    fi
else
    echo "  ⚠️  psql 명령어가 설치되지 않았습니다. 테이블 확인 건너뛰기"
fi

# 4. 샘플 데이터 생성 및 테스트
echo ""
echo "4. 샘플 검색 기록 생성 테스트..."

sample_data='{
  "user_id": 1,
  "query": "최근 가입한 고객들의 목록을 보여주세요",
  "sql_generated": "SELECT * FROM customers WHERE created_at >= CURRENT_DATE - INTERVAL '\''7 days'\''",
  "strategy_used": "llm_first",
  "success": true,
  "result_count": 15,
  "response_time": 2.5,
  "sql_generation_time": 1.2,
  "sql_execution_time": 1.3,
  "metadata_info": {"test": true}
}'

echo "  - 샘플 검색 기록 생성..."
record_response=$(curl -s -X POST "http://127.0.0.1:8000/v1/api/search-analytics/record" \
  -H "Content-Type: application/json" \
  -d "$sample_data")

if [[ $? -eq 0 ]] && [[ $record_response == *"queued"* ]]; then
    echo "  ✅ 검색 기록 생성 성공"
    echo "     응답: $record_response"
else
    echo "  ❌ 검색 기록 생성 실패"
    echo "     응답: $record_response"
fi

# 5. 결과 요약
echo ""
echo "=================================="
echo "🎉 검색 분석 시스템 테스트 완료"
echo ""
echo "📋 다음 단계:"
echo "  1. 데이터베이스 마이그레이션: alembic upgrade head"
echo "  2. 검색 API와 연동하여 실제 데이터 수집 시작"
echo "  3. CloudWatch 대시보드 설정 (선택사항)"
echo "  4. 성능 임계값 알림 설정"
echo ""
echo "📊 API 엔드포인트:"
echo "  - 대시보드: GET /v1/api/search-analytics/dashboard"
echo "  - 인기 검색어: GET /v1/api/search-analytics/popular-queries"
echo "  - 성능 통계: GET /v1/api/search-analytics/performance-stats"
echo "  - 실패 패턴: GET /v1/api/search-analytics/failure-patterns"
echo "  - 기록 저장: POST /v1/api/search-analytics/record"