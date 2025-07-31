# 보험계약자 고객 메모 정제 시스템

## 프로젝트 개요
보험계약자의 고객 메모를 LLM을 통해 정제하고 분석하는 시스템입니다.

### 핵심 기능
1. **메모 정제**: 입력된 고객 메모를 구조화된 형태로 정제
2. **조건부 분석**: DB 데이터와 조건에 따른 LLM 해석 제공
3. **엑셀 일괄 처리**: 다수의 메모를 엑셀로 업로드하여 일괄 정제

## 기술 스택
- **백엔드**: Python 3.11, FastAPI
- **LLM 오케스트레이션**: LangChain, LangGraph
- **데이터베이스**: PostgreSQL + pgvector
- **모니터링**: LangSmith
- **AI 모델**: OpenAI GPT-4 (또는 Claude API)

## 주요 API 엔드포인트

### 1. 메모 정제 API
```
POST /api/memo/refine
{
  "memo": "고객이 전화로 보험료 인상에 대해 문의함. 가족 구성원 변경 고려중"
}
```

### 2. 조건부 분석 API
```
POST /api/memo/analyze
{
  "memo_id": "123",
  "conditions": {
    "customer_type": "VIP",
    "contract_status": "active"
  }
}
```

### 3. 엑셀 일괄 처리 API
```
POST /api/excel/process
Form-data: file (Excel file)
```

## 프롬프트 템플릿 가이드

### 메모 정제 프롬프트
```
당신은 보험회사의 고객 메모를 정제하는 전문가입니다.
다음 고객 메모를 구조화된 형태로 정제해주세요:

입력 메모: {memo}

다음 형식으로 출력하세요:
- 요약: 
- 주요 키워드:
- 고객 상태:
- 필요 조치:
```

### DB 조건 분석 프롬프트
```
고객 정보와 메모를 분석하여 적절한 대응 방안을 제시하세요.

고객 유형: {customer_type}
계약 상태: {contract_status}
정제된 메모: {refined_memo}

분석 결과:
```

## 데이터베이스 스키마

### customer_memos 테이블
- id: UUID
- original_memo: TEXT
- refined_memo: JSONB
- embedding: vector(1536)
- created_at: TIMESTAMP

### analysis_results 테이블
- id: UUID
- memo_id: UUID (FK)
- conditions: JSONB
- analysis: TEXT
- created_at: TIMESTAMP

## 개발 가이드라인

1. **에러 처리**: 모든 API는 적절한 에러 메시지와 상태 코드 반환
2. **로깅**: 모든 LLM 호출은 LangSmith로 추적
3. **보안**: API 키는 환경 변수로 관리, 민감 정보 마스킹
4. **성능**: 유사 메모는 벡터 검색으로 캐싱된 결과 활용

## 환경 설정

### 필수 환경 변수
```
OPENAI_API_KEY=your-api-key
DATABASE_URL=postgresql://user:pass@localhost/insurance_memo
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=insurance-memo-refiner
```

### 로컬 개발 실행
```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload
```

## 프로젝트 구현 우선순위

1. **Phase 1**: 기본 메모 정제 API 구현
    - FastAPI 설정
    - 단순 LangChain 체인 구성
    - 기본 프롬프트 템플릿

2. **Phase 2**: DB 연동 및 조건부 분석
    - PostgreSQL 연결
    - pgvector 설정
    - 조건부 분석 체인 구현

3. **Phase 3**: 엑셀 처리 및 고도화
    - 엑셀 파싱 기능
    - 배치 처리 최적화
    - LangSmith 모니터링 설정

## 테스트 시나리오

1. **단일 메모 정제 테스트**
   ```python
   # 입력: "고객이 보험료 문의, 가족 추가 검토중"
   # 예상 출력: 구조화된 JSON 응답
   ```

2. **조건부 분석 테스트**
   ```python
   # VIP 고객 + 활성 계약 조건으로 분석
   # 예상: 맞춤형 대응 방안 제시
   ```

3. **대량 처리 테스트**
   ```python
   # 100개 메모 엑셀 업로드
   # 성능 목표: 5분 이내 처리
   ```