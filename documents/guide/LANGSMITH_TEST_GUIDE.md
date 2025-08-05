# LangSmith 통합 테스트 가이드

## 🔍 개요
LangSmith가 통합되어 모든 LLM 호출을 추적할 수 있게 되었습니다. 이 가이드에서는 LangSmith 설정 방법과 테스트 방법을 안내합니다.

## ⚙️ 설정

### 1. LangSmith API 키 설정

1. [LangSmith 웹사이트](https://smith.langchain.com)에 접속하여 계정을 생성합니다.
2. 프로젝트를 생성하고 API 키를 발급받습니다.
3. `.env` 파일에서 다음 환경변수를 설정합니다:

```bash
# LangSmith 설정 (LLM 호출 추적)
LANGSMITH_API_KEY=your-actual-langsmith-api-key-here
LANGSMITH_PROJECT=momentir-cx-llm
LANGSMITH_TRACING=true
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 2. 의존성 설치

```bash
# 가상환경 활성화
source venv/bin/activate

# 새로운 의존성 설치
pip install -r requirements.txt
```

## 🚀 추적 가능한 기능들

### 1. 메모 정제 서비스 (MemoRefinerService)
- **메모 정제**: `refine_memo()` - GPT-4를 사용한 메모 구조화
- **임베딩 생성**: `create_embedding()` - 벡터 검색용 임베딩
- **조건부 분석**: `perform_enhanced_conditional_analysis()` - 고객 맞춤 분석

### 2. 고객 서비스 (CustomerService)
- **엑셀 컬럼 매핑**: `map_excel_columns()` - 엑셀 컬럼을 표준 스키마로 매핑

## 🧪 테스트 방법

### 1. 기본 서버 실행
```bash
./scripts/02-start-local.sh
```

서버 시작 시 다음과 같은 LangSmith 관련 로그를 확인할 수 있습니다:
- `✅ LangSmith 추적이 활성화되었습니다. 프로젝트: momentir-cx-llm`
- `ℹ️ LangSmith 추적이 비활성화되어 있습니다.` (API 키가 없는 경우)

### 2. API 테스트 스크립트 실행
```bash
./scripts/03-test-api.sh
```

### 3. 개별 기능 테스트

#### A. 메모 정제 테스트
```bash
curl -X POST "http://127.0.0.1:8000/api/memo/refine" \
  -H "Content-Type: application/json" \
  -d '{
    "memo": "고객이 건강보험 가입을 문의했습니다. 다음 주에 상세 상담 예정입니다."
  }'
```

#### B. 엑셀 컬럼 매핑 테스트
```bash
curl -X POST "http://127.0.0.1:8000/api/customer/column-mapping" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_columns": ["성함", "전화번호", "직장", "성별", "생일", "관심분야"]
  }'
```

#### C. 조건부 분석 테스트
```bash
# 먼저 고객과 메모 생성 후
curl -X POST "http://127.0.0.1:8000/api/memo/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "memo_id": "your-memo-id",
    "conditions": {
      "customer_type": "신규고객",
      "contract_status": "미가입",
      "analysis_focus": ["보험니즈분석", "상품추천"]
    }
  }'
```

## 📊 LangSmith 대시보드에서 확인할 수 있는 정보

### 1. 추적되는 정보
- **Function Name**: 호출된 함수명 (예: `refine_memo`, `map_excel_columns`)
- **Model**: 사용된 AI 모델 (예: `gpt-4`, `text-embedding-ada-002`)
- **Input/Output**: 프롬프트와 응답 내용
- **Metadata**: 
  - 함수별 메타데이터 (길이, 신뢰도, 매핑 결과 등)
  - 성능 지표 (응답 시간, 토큰 사용량)
  - 에러 정보

### 2. 대시보드 접속
1. https://smith.langchain.com 접속
2. 설정한 프로젝트 (`momentir-cx-llm`) 선택
3. `Traces` 탭에서 실시간 LLM 호출 추적 확인

### 3. 추적 정보 예시

#### 메모 정제 추적
```
Function: refine_memo
Model: gpt-4
Input: "고객이 건강보험 가입을 문의했습니다..."
Output: {"summary": "건강보험 가입 문의", "keywords": [...]}
Metadata:
  - memo_length: 45
  - response_length: 234
  - execution_time: 1.2s
```

#### 컬럼 매핑 추적
```
Function: map_excel_columns
Model: gpt-4
Input: ["성함", "전화번호", "직장"]
Output: {"mapping": {"성함": "name", ...}}
Metadata:
  - input_columns: 3
  - mapped_count: 3
  - unmapped_count: 0
  - confidence_score: 0.95
```

## 🔧 문제 해결

### 1. LangSmith 추적이 작동하지 않는 경우
- API 키가 올바르게 설정되었는지 확인
- `LANGSMITH_TRACING=true`로 설정되었는지 확인
- 서버 재시작 후 테스트

### 2. 로그 확인 방법
```bash
# 서버 로그에서 LangSmith 관련 메시지 확인
tail -f logs/app.log | grep -i langsmith
```

### 3. 환경변수 확인
```bash
# 환경변수가 올바르게 로드되었는지 확인
python -c "import os; print('LANGSMITH_API_KEY:', os.getenv('LANGSMITH_API_KEY', 'NOT_SET'))"
```

## 📈 성능 모니터링

LangSmith를 통해 다음을 모니터링할 수 있습니다:

1. **LLM 호출 빈도**: 어떤 기능이 가장 많이 사용되는지
2. **응답 시간**: 각 LLM 호출의 성능
3. **토큰 사용량**: 비용 최적화를 위한 사용량 추적
4. **에러율**: 실패한 호출 비율과 원인
5. **품질 평가**: 응답의 품질과 일관성

## 🎯 다음 단계

1. **프로덕션 배포**: 프로덕션 환경에서도 동일하게 추적 설정
2. **알림 설정**: 에러율이 높아지면 알림 받도록 설정
3. **대시보드 커스터마이징**: 팀에 맞는 모니터링 대시보드 구성
4. **A/B 테스트**: 다른 모델이나 프롬프트의 성능 비교

## 💡 팁

- LangSmith 무료 플랜은 월 5,000개의 추적이 가능합니다
- 개발 환경에서만 추적을 활성화하려면 `LANGSMITH_TRACING=false`로 설정
- 민감한 데이터가 포함된 경우 추적을 비활성화하거나 데이터 마스킹 적용