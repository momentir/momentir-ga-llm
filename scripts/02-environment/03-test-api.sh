#!/bin/bash

# API 테스트 스크립트
# 로컬 서버의 주요 기능들을 테스트합니다

set -e

echo "🧪 보험계약자 메모 정제 시스템 API 테스트"
echo "=============================================="

# 서버 주소 설정
SERVER_URL="http://127.0.0.1:8000"

# 서버 연결 확인
echo ""
echo "📡 서버 연결 확인 중..."
if curl -s --fail "${SERVER_URL}/health" > /dev/null; then
    echo "   ✅ 서버 연결 성공"
else
    echo "   ❌ 서버에 연결할 수 없습니다."
    echo "   ➤ 서버를 먼저 시작하세요: ./scripts/start-local.sh"
    exit 1
fi

# 기본 정보 확인
echo ""
echo "ℹ️  서버 정보 확인 중..."
curl -s "${SERVER_URL}/" | python3 -m json.tool
echo ""

# 헬스체크
echo ""
echo "💓 헬스체크..."
curl -s "${SERVER_URL}/health" | python3 -m json.tool
echo ""

# 고객 생성 테스트
echo ""
echo "👤 고객 생성 테스트..."
CUSTOMER_RESPONSE=$(curl -s -X POST "${SERVER_URL}/api/customer/create" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "김테스트",
    "contact": "010-1234-5678",
    "occupation": "개발자",
    "gender": "남성",
    "interests": ["IT", "보험"],
    "insurance_products": [
      {
        "product_type": "생명보험",
        "provider": "테스트보험",
        "premium": 50000
      }
    ]
  }')

echo "$CUSTOMER_RESPONSE" | python3 -m json.tool

# 고객 ID 추출
CUSTOMER_ID=$(echo "$CUSTOMER_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['customer_id'])
except:
    print('error')
")

if [ "$CUSTOMER_ID" = "error" ]; then
    echo "   ❌ 고객 생성 실패"
    exit 1
else
    echo "   ✅ 고객 생성 성공 (ID: $CUSTOMER_ID)"
fi

# 메모 빠른 저장 테스트
echo ""
echo "📝 메모 빠른 저장 테스트..."
MEMO_RESPONSE=$(curl -s -X POST "${SERVER_URL}/api/memo/quick-save" \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_id\": \"$CUSTOMER_ID\",
    \"content\": \"고객이 건강보험 가입을 문의했습니다. 다음 주에 상세 상담 예정입니다.\"
  }")

echo "$MEMO_RESPONSE" | python3 -m json.tool

# 메모 ID 추출
MEMO_ID=$(echo "$MEMO_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['memo_id'])
except:
    print('error')
")

if [ "$MEMO_ID" = "error" ]; then
    echo "   ❌ 메모 저장 실패"
else
    echo "   ✅ 메모 저장 성공 (ID: $MEMO_ID)"
fi

# 컬럼 매핑 테스트
echo ""
echo "🗂️  컬럼 매핑 테스트..."
curl -s -X POST "${SERVER_URL}/api/customer/column-mapping" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_columns": ["성함", "전화번호", "직장", "성별", "생일", "관심분야"]
  }' | python3 -m json.tool
echo ""

# 고객 목록 조회 테스트
echo ""
echo "📋 고객 목록 조회 테스트..."
curl -s "${SERVER_URL}/api/customer/?limit=5" | python3 -m json.tool
echo ""

# 고객 분석 통계 테스트
echo ""
echo "📊 고객 분석 통계 테스트..."
curl -s "${SERVER_URL}/api/customer/${CUSTOMER_ID}/analytics" | python3 -m json.tool
echo ""

# 메모 조건부 분석 테스트 (OpenAI API 키가 있는 경우에만)
echo ""
echo "🧠 메모 조건부 분석 테스트..."
if [ "$OPENAI_API_KEY" != "test-key-for-local-development" ] && [ ! -z "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "your-openai-api-key-here" ]; then
    echo "   ➤ OpenAI API 키가 설정되어 있습니다. 실제 분석을 수행합니다..."
    
    # 먼저 메모를 정제
    curl -s -X POST "${SERVER_URL}/api/memo/refine" \
      -H "Content-Type: application/json" \
      -d '{
        "memo": "고객이 건강보험 가입을 문의했습니다. 다음 주에 상세 상담 예정입니다."
      }' | python3 -m json.tool
    echo ""
    
    # 조건부 분석 수행
    if [ "$MEMO_ID" != "error" ]; then
        curl -s -X POST "${SERVER_URL}/api/memo/analyze" \
          -H "Content-Type: application/json" \
          -d "{
            \"memo_id\": \"$MEMO_ID\",
            \"conditions\": {
              \"customer_type\": \"신규고객\",
              \"contract_status\": \"미가입\",
              \"analysis_focus\": [\"보험니즈분석\", \"상품추천\"]
            }
          }" | python3 -m json.tool
        echo ""
    fi
else
    echo "   ⚠️  OpenAI API 키가 설정되지 않았습니다."
    echo "   ➤ .env 파일에서 OPENAI_API_KEY를 설정하면 실제 AI 분석을 테스트할 수 있습니다."
fi

echo ""
echo "🎉 API 테스트 완료!"
echo "=============================================="
echo ""
echo "📖 추가 테스트를 원하시면:"
echo "   • API 문서: ${SERVER_URL}/docs"
echo "   • Swagger UI에서 직접 테스트 가능"
echo ""
echo "📁 테스트 파일 업로드:"
echo "   • 엑셀 파일 업로드는 웹 브라우저에서 테스트하세요"
echo "   • ${SERVER_URL}/docs#/customer/upload_excel_file_api_customer_excel_upload_post"
echo ""