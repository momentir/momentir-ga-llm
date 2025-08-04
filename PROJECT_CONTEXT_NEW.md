# 보험계약자 고객 메모 정제 시스템

## 프로젝트 개요
보험 설계사(개인사업자/프리랜서)가 고객 메모를 LLM을 통해 정제하고 분석하는 CRM 시스템입니다.

### 핵심 기능
1. **메모 정제**: 입력된 고객 메모를 구조화된 형태로 정제
2. **조건부 분석**: DB 데이터와 조건에 따른 LLM 해석 제공
3. **엑셀 일괄 처리**: 다수의 메모를 엑셀로 업로드하여 일괄 정제
4. **이벤트 트리거**: 메모 분석 후 전화하기, 메시지 보내기, 알림, 캘린더 저장 등 액션 제안

## 기술 스택
- **백엔드**: Python 3.11, FastAPI
- **LLM 오케스트레이션**: LangChain, LangGraph
- **데이터베이스**: PostgreSQL + pgvector
- **모니터링**: LangSmith
- **AI 모델**: OpenAI GPT-4 (또는 Claude API)
- **인프라**: AWS (Lambda, API Gateway, RDS PostgreSQL)

## Phase별 개발 계획

### Phase 1: 기본 메모 정제 API 구현 ✅ (완료)
**목표**: 단일 메모를 입력받아 정제하는 핵심 기능 구현

#### Step 1: FastAPI 기본 구조 설정 ✅ (완료)
```bash
# Claude Code 명령
"FastAPI로 기본 메모 정제 API를 만들어줘. /api/memo/refine 엔드포인트와 /api/memo/quick-save 엔드포인트를 구현해줘"
```

#### Step 2: LangChain 통합 ✅ (완료)
```bash
# Claude Code 명령
"LangChain을 사용해서 메모 정제 체인을 구현해줘. GPT-4 모델 사용하고 고객 정보 추출 프롬프트를 만들어줘"
```

#### Step 3: 기본 DB 연결 및 저장 ✅ (완료)
```bash
# Claude Code 명령
"PostgreSQL 연결 설정하고 원본 메모와 정제된 메모를 분리하여 저장하는 기능을 구현해줘"
```

### Phase 2: 고객 데이터 통합 및 조건부 분석 ✅ (완료)
**목표**: 엑셀 업로드, LLM 기반 데이터 매핑, 조건부 분석 구현

#### Step 4: 엑셀 업로드 및 LLM 매핑 ✅ (완료)
```bash
# Claude Code 명령
"엑셀 파일 업로드 API를 만들고, LLM을 사용해 다양한 컬럼명을 표준 스키마로 매핑하는 기능을 구현해줘"
```

#### Step 5: 고객 스키마 구현 ✅ (완료)
```bash
# Claude Code 명령
"planner_input.json 스키마를 참고해서 고객 데이터 모델을 구현하고 CRUD API를 만들어줘"
```

#### Step 6: 조건부 분석 체인 ✅ (완료)
```bash
# Claude Code 명령
"고객 타입, 보험 가입 현황 등 조건에 따른 메모 분석 체인을 구현해줘. /api/memo/analyze 엔드포인트 추가"
```

### Phase 3: 이벤트 시스템 및 고도화 ✅ (완료)
**목표**: 메모 기반 이벤트 트리거, 알림 시스템, LangSmith 모니터링

#### Step 7: 이벤트 트리거 시스템 ✅ (완료)
```bash
# Claude Code 명령
"메모 분석 결과에서 시간 표현을 파싱하고 이벤트(전화하기, 메시지보내기, 알림)를 생성하는 시스템을 구현해줘"
```

#### Step 8: 규칙 기반 이벤트 추가 ✅ (완료)
```bash
# Claude Code 명령
"생일, 기념일 등 규칙 기반 이벤트 트리거를 추가하고 우선순위 시스템을 구현해줘"
```

#### Step 9: LangSmith 통합 ✅ (완료)
```bash
# Claude Code 명령
"LangSmith를 설정하고 모든 LLM 호출을 추적하도록 통합해줘"
```

### Phase 4: 프롬프트 관리 시스템 구축 ✅ (완료)
**목표**: 프롬프트 버전 관리, A/B 테스트, 동적 로딩

#### Step 10: 프롬프트 관리 시스템 설계 ✅ (완료)
```bash
# Claude Code 명령
"프롬프트를 파일이나 DB에서 관리하고 동적으로 로드하는 시스템을 설계해줘. 버전 관리와 A/B 테스트가 가능하도록 구현해줘"
```

#### Step 11: 프롬프트 테스트 인터페이스 ✅ (완료)
```bash
# Claude Code 명령
"프롬프트를 수정하고 실시간으로 테스트할 수 있는 API 엔드포인트를 만들어줘. Swagger 화면에서 테스트할 계획이니깐 여기서 확인하기 용이하게 Swagger 관련 설명을 추가해줘."
```

#### Step 12: 프롬프트 성능 평가 시스템 ✅ (완료)
```bash
# Claude Code 명령
"프롬프트 변경에 따른 출력 품질을 평가하고 비교할 수 있는 시스템을 구현해줘. LangSmith와 연동해서 추적해줘"
```

### Phase 5: 벡터 DB 최적화 및 이벤트 고도화
**목표**: pgvector 활용, 이벤트 파이프라인 개선

#### Step 13: pgvector 전환
```bash
# Claude Code 명령
"현재 JSONB로 저장된 임베딩을 pgvector의 vector 타입으로 전환하고, 효율적인 유사도 검색을 구현해줘"
```

#### Step 14: 이벤트 파이프라인 분리
```bash
# Claude Code 명령
"메모 저장과 이벤트 생성을 분리된 프로세스로 구현해줘. 큐 시스템이나 비동기 처리를 사용해서 확장 가능하게 만들어줘"
```

#### Step 15: 이벤트 워크플로우 엔진
```bash
# Claude Code 명령
"LangGraph를 활용해서 복잡한 이벤트 워크플로우를 관리하는 시스템을 구현해줘. 조건부 분기와 상태 관리를 포함해줘"
```

## AWS 인프라 구축 지침

### 단계별 스크립트 작성 원칙
1. **각 리소스별 독립 스크립트**: 생성 → 확인 → 성공/실패 분기 처리
2. **프리티어 우선**: 모든 리소스는 무료 티어 내에서 구성
3. **버전 확인**: 선택 가능한 최신 버전 자동 선택
4. **퍼블릭 액세스**: RDS는 퍼블릭 액세스 가능하도록 설정
5. **페이저 비활성화**: `--no-cli-pager` 옵션 사용

### 인프라 구축 스크립트 예시
```bash
#!/bin/bash

# 1. RDS PostgreSQL 생성
echo "Creating RDS PostgreSQL instance..."
aws rds create-db-instance \
    --db-instance-identifier insurance-memo-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version $(aws rds describe-db-engine-versions --engine postgres --query 'DBEngineVersions[-1].EngineVersion' --output text) \
    --allocated-storage 20 \
    --master-username admin \
    --master-user-password ${DB_PASSWORD} \
    --publicly-accessible \
    --no-cli-pager

# 2. 생성 확인
echo "Waiting for RDS instance to be available..."
aws rds wait db-instance-available \
    --db-instance-identifier insurance-memo-db \
    --no-cli-pager

# 3. 성공 여부 확인
if [ $? -eq 0 ]; then
    echo "RDS instance created successfully"
    # 엔드포인트 저장
    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier insurance-memo-db \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --no-cli-pager)
    echo "DB Endpoint: $DB_ENDPOINT"
else
    echo "Failed to create RDS instance"
    exit 1
fi
```

## 주요 API 엔드포인트

### 1. 메모 관련 API
```
POST /api/memo/quick-save
{
  "customer_id": "123",
  "content": "고객이 전화로 보험료 인상에 대해 문의함. 2주 후 다시 연락하기로 함"
}

POST /api/memo/refine
{
  "memo_id": "456",
  "confirm": true  // AI 추론 결과 확인 후 저장
}
```

### 2. 고객 데이터 API
```
POST /api/customer/create
{
  // planner_input.json 스키마 참조
}

POST /api/customer/excel-upload
Form-data: file (Excel file)
```

### 3. 이벤트 API
```
GET /api/events/upcoming
{
  "customer_id": "123",
  "days": 7  // 향후 7일간 이벤트
}
```

## 데이터 플로우 및 아키텍처

### 메모 처리 프로세스
1. **메모 입력** → `/api/memo/quick-save` (원본 저장)
2. **LLM 정제** → `/api/memo/refine` (프롬프트 기반 정제)
3. **데이터 저장**:
   - PostgreSQL 일반 테이블: 원본 메모, 정제된 JSON 데이터
   - 임베딩 벡터: JSONB 형태로 저장 (추후 pgvector로 전환 예정)
4. **이벤트 생성** → `/api/events/process-memo` (별도 API 호출)
5. **이벤트 실행** → 우선순위 기반 스케줄링

### 프롬프트 관리 현황 ✅ (완료)
- **현재**: 동적 프롬프트 관리 시스템 완료
  - ✅ DB 기반 저장 (PostgreSQL)
  - ✅ 버전 관리 시스템
  - ✅ A/B 테스트 프레임워크
  - ✅ 실시간 수정 및 테스트 API
  - ✅ Jinja2 템플릿 엔진 통합
  - ✅ 기존 서비스와 동적 연동

## 데이터베이스 스키마

### customers 테이블
```sql
CREATE TABLE customers (
                          customer_id UUID PRIMARY KEY,
                          name VARCHAR(100),
                          contact VARCHAR(50),
                          affiliation VARCHAR(200),
                          occupation VARCHAR(100),
                          gender VARCHAR(10),
                          date_of_birth DATE,
                          interests JSONB,
                          life_events JSONB,
                          insurance_products JSONB,
                          created_at TIMESTAMP,
                          updated_at TIMESTAMP
);
```

### memos 테이블
```sql
CREATE TABLE memos (
                      memo_id UUID PRIMARY KEY,
                      customer_id UUID REFERENCES customers(customer_id),
                      original_content TEXT,
                      refined_content JSONB,
                      status VARCHAR(20), -- 'draft', 'refined', 'confirmed'
                      created_at TIMESTAMP,
                      author VARCHAR(100)
);
```

### events 테이블
```sql
CREATE TABLE events (
                       event_id UUID PRIMARY KEY,
                       customer_id UUID REFERENCES customers(customer_id),
                       memo_id UUID REFERENCES memos(memo_id),
                       event_type VARCHAR(50), -- 'call', 'message', 'reminder', 'calendar'
                       scheduled_date DATE,
                       priority INTEGER,
                       status VARCHAR(20),
                       created_at TIMESTAMP
);
```

## 프롬프트 템플릿 가이드

### 메모 정제 프롬프트
```
당신은 보험회사의 고객 메모를 분석하는 전문가입니다.
다음 고객 메모에서 중요한 정보를 추출해주세요:

메모: {memo}

다음 정보를 추출하세요:
1. 고객 상태/감정
2. 주요 키워드 (관심사, 니즈)
3. 시간 관련 표현 (예: "2주 후", "다음 달")
4. 필요한 후속 조치
5. 보험 관련 정보 (상품명, 보험료, 관심 상품)

출력 형식:
{
  "status": "...",
  "keywords": [...],
  "time_expressions": [{
    "expression": "2주 후",
    "parsed_date": "2024-01-15"
  }],
  "required_actions": [...],
  "insurance_info": {...}
}
```

### 엑셀 컬럼 매핑 프롬프트
```
다음 엑셀 컬럼명을 표준 고객 스키마로 매핑해주세요:

엑셀 컬럼: {columns}
표준 스키마: {standard_schema}

각 엑셀 컬럼이 어떤 표준 필드에 해당하는지 매핑하고,
매핑할 수 없는 컬럼은 'unmapped'로 표시하세요.
```

## 개발 가이드라인

1. **빠른 저장 우선**: 현장에서는 빠른 저장을 많이 사용하므로 성능 최적화
2. **원본 보존**: 원본 메모와 정제된 메모를 항상 분리하여 저장
3. **단계별 확인**: AI 추론 결과는 사용자 확인 후 저장
4. **유연한 스키마**: 다양한 엑셀 형식을 수용할 수 있도록 LLM 매핑 활용

## 환경 설정

### 필수 환경 변수
```
OPENAI_API_KEY=your-api-key
DATABASE_URL=postgresql://admin:password@your-rds-endpoint/insurance_memo
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=insurance-memo-refiner
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=ap-northeast-2
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
uvicorn app.main:app --reload --port 8000
```

## 테스트 시나리오

1. **빠른 저장 → AI 정제 플로우**
   - 메모 빠른 저장
   - AI 추론 결과 확인
   - 사용자 승인 후 정제된 데이터 저장

2. **엑셀 업로드 테스트**
   - 다양한 컬럼명의 엑셀 파일 업로드
   - LLM 매핑 정확도 확인
   - 대량 데이터 처리 성능 측정

3. **이벤트 트리거 테스트**
   - "2주 후 연락" 같은 시간 표현 파싱
   - 생일 기반 자동 이벤트 생성
   - 우선순위에 따른 알림 순서 확인