# 보험계약자 메모 정제 시스템 사용법

## 🚀 빠른 시작 가이드

### 1. 시스템 실행
```bash
# 프로젝트 디렉토리로 이동
cd momentir-cx-llm

# 서버 시작 (최초 실행 시 자동으로 환경 설정)
./scripts/02-envrinment/02-start-local.sh
```

### 2. 브라우저에서 API 문서 열기
http://127.0.0.1:8000/docs

## 📝 주요 사용 시나리오

### 시나리오 1: 고객 등록 및 메모 작성

#### 1단계: 고객 생성
```bash
curl -X POST "http://127.0.0.1:8000/api/customer/create" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "김보험",
    "contact": "010-1234-5678",
    "occupation": "회사원",
    "gender": "남성",
    "interests": ["건강", "투자"],
    "insurance_products": []
  }'
```

#### 2단계: 메모 빠른 저장
```bash
curl -X POST "http://127.0.0.1:8000/api/memo/quick-save" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "생성된_고객_ID",
    "content": "고객이 건강보험에 관심을 보였습니다. 다음 주 화요일에 상세 상담 예정"
  }'
```

#### 3단계: 메모 AI 정제
```bash
curl -X POST "http://127.0.0.1:8000/api/memo/refine" \
  -H "Content-Type: application/json" \
  -d '{
    "memo": "고객이 건강보험에 관심을 보였습니다. 다음 주 화요일에 상세 상담 예정"
  }'
```

### 시나리오 2: 엑셀 파일로 고객 일괄 등록

#### 1단계: 엑셀 파일 준비
```
| 이름   | 전화번호      | 직업     | 성별 | 관심분야        |
|--------|---------------|----------|------|-----------------|
| 홍길동 | 010-1111-2222 | 의사     | 남성 | 의료, 투자      |
| 김영희 | 010-3333-4444 | 교사     | 여성 | 교육, 저축      |
```

#### 2단계: 컬럼 매핑 확인
```bash
curl -X POST "http://127.0.0.1:8000/api/customer/column-mapping" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_columns": ["이름", "전화번호", "직업", "성별", "관심분야"]
  }'
```

#### 3단계: 엑셀 파일 업로드 (웹 브라우저 사용 권장)
1. http://127.0.0.1:8000/docs 접속
2. `POST /api/customer/excel-upload` 엔드포인트 찾기
3. "Try it out" 클릭
4. 파일 선택 후 실행

### 시나리오 3: 고급 메모 분석

#### 1단계: 조건부 분석 실행
```bash
curl -X POST "http://127.0.0.1:8000/api/memo/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "memo_id": "메모_ID",
    "conditions": {
      "customer_type": "신규고객",
      "contract_status": "미가입",
      "analysis_focus": ["보험니즈분석", "상품추천", "리스크평가"]
    }
  }'
```

#### 2단계: 고객 분석 통계 확인
```bash
curl -X GET "http://127.0.0.1:8000/api/customer/{customer_id}/analytics"
```

## 🔍 데이터 조회 및 검색

### 고객 목록 조회
```bash
# 전체 고객 목록
curl "http://127.0.0.1:8000/api/customer/"

# 검색으로 고객 찾기
curl "http://127.0.0.1:8000/api/customer/?search=김"

# 페이징
curl "http://127.0.0.1:8000/api/customer/?limit=10&offset=0"
```

### 특정 고객 상세 정보
```bash
curl "http://127.0.0.1:8000/api/customer/{customer_id}"
```

### 메모 및 분석 결과 조회
```bash
curl "http://127.0.0.1:8000/api/memo/memo/{memo_id}"
```

## 📊 API 응답 예시

### 메모 정제 결과
```json
{
  "memo_id": "uuid-string",
  "summary": "고객이 건강보험 가입을 문의하고 다음 주 상담 예정",
  "status": "관심 고객",
  "keywords": ["건강보험", "상담", "가입문의"],
  "time_expressions": [
    {
      "expression": "다음 주 화요일",
      "parsed_date": "2024-01-16"
    }
  ],
  "required_actions": ["상담 일정 확정", "보험 상품 자료 준비"],
  "insurance_info": {
    "products": [],
    "interest_products": ["건강보험"],
    "policy_changes": []
  },
  "similar_memos_count": 3,
  "processed_at": "2024-01-09T10:30:00"
}
```

### 고객 분석 통계
```json
{
  "customer_id": "uuid-string",
  "customer_name": "김보험",
  "statistics": {
    "total_memos": 5,
    "refined_memos": 3,
    "total_analyses": 2,
    "refinement_rate": 0.6
  },
  "recent_activity": {
    "last_memo_date": "2024-01-09T10:30:00",
    "last_analysis_date": "2024-01-08T15:20:00"
  },
  "customer_profile": {
    "age": 35,
    "occupation": "회사원",
    "interests_count": 2,
    "insurance_products_count": 0
  }
}
```

## ⚙️ 고급 설정

### 환경변수 설정
```bash
# .env 파일 편집
USE_MOCK_MODE=true                    # 개발 모드 (SQLite 사용)
OPENAI_API_KEY=your-api-key-here     # OpenAI API 키
MOCK_DATABASE_URL=sqlite+aiosqlite:///./dev_memo.db
```

### 데이터베이스 관리
```bash
# 새 마이그레이션 생성
alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
alembic upgrade head

# 데이터베이스 리셋
rm dev_memo.db
alembic upgrade head
```

## 🐛 문제 해결

### 일반적인 오류 및 해결법

#### 1. "서버에 연결할 수 없습니다"
```bash
# 서버가 실행 중인지 확인
curl http://127.0.0.1:8000/health

# 서버 재시작
./scripts/02-envrinment/02-start-local.sh
```

#### 2. "OpenAI API 오류"
```bash
# API 키 설정 확인
echo $OPENAI_API_KEY

# .env 파일에서 키 설정
nano .env
```

#### 3. "데이터베이스 오류"
```bash
# 데이터베이스 파일 재생성
rm dev_memo.db
alembic upgrade head
```

#### 4. "엑셀 업로드 실패"
- 파일 형식이 .xlsx 또는 .xls인지 확인
- 파일 크기가 너무 크지 않은지 확인 (10MB 이하 권장)
- 첫 번째 행이 컬럼명인지 확인

## 📞 지원

추가 도움이 필요하시면:
1. API 문서 확인: http://127.0.0.1:8000/docs
2. 프로젝트 문서: PROJECT_CONTEXT_NEW.md
3. 이슈 등록: GitHub Issues