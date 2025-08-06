# 테스트 데이터 및 마이그레이션 스크립트 가이드

이 디렉토리(`/tests/excel-upload/db`)는 보험설계사 엑셀 업로드 시스템의 테스트 데이터 생성 및 데이터베이스 마이그레이션을 위한 스크립트들을 포함합니다.

## 📁 디렉토리 구조
```
/tests/excel-upload/
├── db/                    # 데이터베이스 관련 스크립트 (현재 위치)
│   ├── create_test_data.py
│   ├── create_test_excel_files.py
│   ├── run_full_test_scenario.py
│   └── README.md
├── api/                   # API 테스트 스크립트
│   ├── run_all_tests.py
│   ├── test_enhanced_excel_upload.py
│   ├── test_customer_products_api.py
│   └── test_user_permissions.py
└── test_excel_files/      # 생성된 테스트 엑셀 파일들
    ├── 01_기본형태.xlsx
    ├── 02_복잡한컬럼매핑.xlsx
    └── ...
```

## 📁 스크립트 구성

### 🗄️ 데이터 관리 스크립트

#### 1. `create_test_data.py`
**샘플 설계사 및 고객 데이터 생성**

- **기능**:
  - 5명의 샘플 설계사 데이터 생성
  - 각 설계사별 10-20명의 고객 데이터 생성
  - 고객별 1-3개의 가입상품 데이터 생성
  
- **생성 데이터**:
  - 설계사: 실명과 이메일을 가진 5명의 보험설계사
  - 고객: 한국어 이름, 전화번호, 주소, 직업 등 현실적인 고객 정보
  - 상품: 다양한 보험상품 (생명보험, 건강보험, 자동차보험 등)

- **실행 방법**:
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
python create_test_data.py
```

#### 2. `create_test_excel_files.py` 
**다양한 형태의 테스트용 엑셀 파일 생성**

- **생성되는 파일들**:
  - `01_기본형태.xlsx` - 표준 형태의 엑셀 파일
  - `02_복잡한컬럼매핑.xlsx` - LLM 매핑이 필요한 복잡한 컬럼명
  - `03_고객당여러상품.xlsx` - 동일 고객의 여러 상품 데이터
  - `04_데이터검증테스트.xlsx` - 다양한 데이터 형식 검증용
  - `05_대용량파일_1000행.xlsx` - 대용량 파일 처리 테스트용
  - `06_혼합형식.xlsx` - 여러 형식이 혼재된 파일
  - `07_빈파일.xlsx` - 오류 시나리오 테스트용
  - `08_헤더만.xlsx` - 헤더만 있는 파일
  - `09_잘못된형식.txt` - 잘못된 파일 형식
  - `10_실제시나리오_종합.xlsx` - 실제 사용 시나리오를 반영한 종합 파일

- **실행 방법**:
```bash
python create_test_excel_files.py
```

### 🚀 통합 실행 스크립트

#### 3. `run_full_test_scenario.py`
**전체 테스트 시나리오 자동 실행**

- **실행 단계**:
  1. 전제조건 확인 (DATABASE_URL, 필수 패키지, 파일들)
  2. 데이터베이스 마이그레이션 실행
  3. 테스트 데이터 생성 (설계사, 고객, 상품)
  4. 테스트용 엑셀 파일 생성
  5. API 통합 테스트 실행

- **실행 방법**:
```bash
# 전체 시나리오 실행
export DATABASE_URL="postgresql://user:password@host:port/database"
python run_full_test_scenario.py

# 개별 단계 실행
python run_full_test_scenario.py --skip-migrations  # 마이그레이션 건너뛰기
python run_full_test_scenario.py --skip-data        # 데이터 생성 건너뛰기  
python run_full_test_scenario.py --skip-excel       # 엑셀 파일 생성 건너뛰기
python run_full_test_scenario.py --skip-api-tests   # API 테스트 건너뛰기
```

## 🔧 사용 전 준비사항

### 1. 환경 설정
```bash
# DATABASE_URL 환경변수 설정
export DATABASE_URL="postgresql://user:password@host:port/database"

# 또는 Production DB 사용시
export DATABASE_URL="postgresql://dbadmin:5JYbqQeiuQI7tYNaDoFAnp0oL@momentir-cx.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com:5432/momentir-cx-llm"
```

### 2. 필수 Python 패키지
```bash
pip install alembic pandas faker aiohttp openpyxl sqlalchemy psycopg2-binary
```

### 3. 데이터베이스 마이그레이션 확인
```bash
# 현재 마이그레이션 상태 확인
alembic current

# 최신 마이그레이션으로 업그레이드
alembic upgrade head
```

## 📊 생성되는 테스트 데이터 구조

### 설계사 (Users)
```json
{
  "name": "김민수",
  "email": "minsu.kim@momentir.com", 
  "phone": "010-1234-5678",
  "sign_up_status": "COMPLETED"
}
```

### 고객 (Customers)  
```json
{
  "name": "홍길동",
  "phone": "010-1234-5678",
  "customer_type": "가입",
  "contact_channel": "소개",
  "address": "서울시 강남구...",
  "job_title": "회사원",
  "resident_number": "801011-1******"
}
```

### 가입상품 (Customer Products)
```json
{
  "product_name": "종합보험",
  "coverage_amount": "1,000만원", 
  "subscription_date": "2024-01-15",
  "policy_issued": true
}
```

## 🧪 테스트 시나리오

### 1. 기본 시나리오
- 표준 형태의 엑셀 파일 업로드
- 설계사별 권한 검증
- 고객 및 상품 CRUD 작업

### 2. 복잡한 매핑 시나리오  
- 다양한 컬럼명 (성명, 핸드폰, 분류 등)
- LLM 매핑 정확도 80% 이상 목표
- 동의어 및 유사 표현 인식

### 3. 대용량 처리 시나리오
- 1000행 이상 데이터 처리
- 성능 및 메모리 사용량 테스트
- 배치 처리 검증

### 4. 오류 처리 시나리오
- 잘못된 파일 형식
- 빈 파일 또는 헤더만 있는 파일
- 존재하지 않는 사용자 ID

## 📈 성공 기준

### 전체 시스템
- **전체 성공률**: 80% 이상
- **핵심 기능 성공률**: 90% 이상
- **보안 테스트 성공률**: 95% 이상

### Excel Upload API
- **매핑 정확도**: 80% 이상
- **데이터 처리 성공률**: 95% 이상
- **대용량 처리**: 1000행 중 80% 이상 처리

### Customer Products API
- **CRUD 완전성**: 100%
- **데이터 무결성**: 100%

### User Permissions
- **접근 권한 차단률**: 95% 이상
- **데이터 격리**: 100%

## 🔍 문제 해결

### 일반적인 오류들

#### 1. 데이터베이스 연결 오류
```bash
# PostgreSQL 서버 상태 확인
pg_ctl status

# 연결 테스트
psql -h host -p 5432 -U username -d database
```

#### 2. 마이그레이션 오류
```bash
# 마이그레이션 히스토리 확인
alembic history

# 특정 버전으로 다운그레이드
alembic downgrade revision_id
```

#### 3. Python 패키지 오류
```bash
# 가상환경 사용 권장
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

#### 4. 메모리 부족 오류
- 대용량 파일 테스트 시 행 수 조정
- `create_test_excel_files.py`의 `large_file_excel()` 함수에서 행 수 변경

## 📋 체크리스트

테스트 실행 전 확인사항:

- [ ] DATABASE_URL 환경변수 설정됨
- [ ] 필수 Python 패키지 설치됨  
- [ ] 데이터베이스 연결 가능
- [ ] Alembic 마이그레이션 최신 상태
- [ ] API 서버 실행 중 (API 테스트시)
- [ ] 충분한 디스크 공간 (엑셀 파일 생성용)

## 📞 지원

문제 발생시:
1. 각 스크립트의 오류 메시지 확인
2. 로그 파일 확인 (`*.log`)
3. 데이터베이스 연결 상태 확인
4. API 서버 상태 확인

---

**⚡ 빠른 시작**:
```bash
export DATABASE_URL="your_database_url"
python run_full_test_scenario.py
```