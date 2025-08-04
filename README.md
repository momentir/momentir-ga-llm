# 보험계약자 메모 정제 시스템

보험 설계사가 고객 메모를 LLM을 통해 정제하고 분석하는 CRM 시스템입니다.

## 🎯 프로젝트 개요

### 핵심 기능
- **메모 정제**: 입력된 고객 메모를 구조화된 형태로 정제
- **조건부 분석**: 고객 데이터와 조건에 따른 LLM 해석 제공
- **엑셀 일괄 처리**: 다수의 고객 데이터를 엑셀로 업로드하여 일괄 처리
- **고객 데이터 관리**: 완전한 CRUD API와 지능형 검색
- **이벤트 관리**: 메모 분석 후 액션 아이템 생성 및 관리

### 기술 스택
- **백엔드**: Python 3.11, FastAPI
- **LLM**: OpenAI GPT-4, LangChain
- **데이터베이스**: PostgreSQL + pgvector (프로덕션), SQLite (개발)
- **인프라**: AWS (ECS, RDS, ALB)

## 🚀 빠른 시작

### 1. 프로젝트 클론 및 초기 설정

```bash
# 프로젝트 클론
git clone <repository-url>
cd momentir-cx-llm

# 개발 환경 자동 설정
./scripts/01-setup-development.sh
```

### 2. 환경변수 설정

`.env` 파일에서 OpenAI API 키 설정:

```bash
# .env 파일 편집
nano .env

# OPENAI_API_KEY를 실제 키로 변경
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

### 3. 로컬 서버 실행

```bash
# 서버 시작 (자동으로 가상환경 활성화, DB 초기화, 서버 실행)
./scripts/02-envrinment/02-start-local.sh
```

### 4. API 테스트

```bash
# 새 터미널에서 API 테스트 실행
./scripts/02-envrinment/03-test-api.sh
```

## 📖 API 문서

서버 실행 후 다음 URL에서 확인:

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **기본 정보**: http://127.0.0.1:8000/

## ☁️ AWS 배포

### 전체 배포 가이드
상세한 AWS 배포 과정은 [DEPLOYMENT.md](DEPLOYMENT.md)를 참조하세요.

### 빠른 배포 (요약)

1. **AWS 인프라 구성**
   ```bash
   cd aws
   ./setup-infrastructure-v3.sh ap-northeast-2 YOUR_AWS_ACCOUNT_ID
   ```

2. **GitHub Secrets 설정**
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

3. **코드 푸시** → 자동 배포 시작

## 🔧 주요 API 엔드포인트

### 메모 관리
```http
POST /api/memo/quick-save      # 메모 빠른 저장
POST /api/memo/refine          # 메모 AI 정제
POST /api/memo/analyze         # 조건부 분석
GET  /api/memo/memo/{memo_id}  # 메모 조회
```

### 고객 관리
```http
POST /api/customer/create           # 고객 생성
GET  /api/customer/{customer_id}    # 고객 조회
PUT  /api/customer/{customer_id}    # 고객 수정
DELETE /api/customer/{customer_id}  # 고객 삭제
GET  /api/customer/                 # 고객 목록 (검색, 페이징)
```

### 엑셀 처리
```http
POST /api/customer/excel-upload     # 엑셀 파일 업로드
POST /api/customer/column-mapping   # 컬럼명 매핑
```

### 분석 및 통계
```http
GET /api/customer/{customer_id}/analytics  # 고객 분석 통계
```

## 🗄️ 데이터베이스

### 로컬 개발 (SQLite)
Mock 모드에서는 SQLite를 사용합니다.

### 프로덕션 (PostgreSQL + pgvector)
```sql
-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;
```

## 🧪 테스트

```bash
# 로컬 테스트 실행
pytest tests/

# 커버리지 포함 테스트
pytest --cov=app tests/
```

## 📁 프로젝트 구조

```
momentir-cx-llm/
├── app/                      # 메인 애플리케이션
│   ├── main.py              # FastAPI 앱 진입점
│   ├── database.py          # 데이터베이스 연결
│   ├── models.py            # Pydantic 모델
│   ├── db_models.py         # SQLAlchemy 모델
│   ├── routers/             # API 라우터
│   └── services/            # 비즈니스 로직
├── aws/                     # AWS 인프라 스크립트
│   ├── setup-infrastructure-v3.sh
│   ├── cleanup-infrastructure.sh
│   ├── check-infrastructure.sh
│   ├── task-definition.json
│   └── service-definition.json
├── .github/workflows/       # GitHub Actions CI/CD
├── alembic/                # 데이터베이스 마이그레이션
├── tests/                  # 테스트 코드
├── Dockerfile              # 컨테이너 이미지
├── docker-compose.yml      # 로컬 개발 환경
├── requirements.txt        # Python 의존성
└── DEPLOYMENT.md          # 상세 배포 가이드
```

## 🔧 개발 도구

### 환경 변수 관리
```bash
# 필수 환경 변수
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=postgresql://user:pass@host:5432/db
LANGSMITH_API_KEY=optional-langsmith-key
```

### 데이터베이스 마이그레이션
```bash
# 새 마이그레이션 생성
alembic revision --autogenerate -m "migration description"

# 마이그레이션 적용
alembic upgrade head
```

## 🔒 보안 고려사항

- 모든 민감한 정보는 환경 변수로 관리
- AWS Secrets Manager를 통한 프로덕션 시크릿 관리
- API 키는 절대 코드에 하드코딩하지 않음

## 📊 모니터링

- **AWS CloudWatch**: 애플리케이션 로그 및 메트릭
- **Health Check**: `/health` 엔드포인트
- **ALB Health Check**: ECS 서비스 상태 모니터링

## 🤝 기여 가이드

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.

## 🆘 문제 해결

### 일반적인 문제들

1. **Docker 빌드 실패**
   - Docker Desktop이 실행 중인지 확인
   - `docker system prune` 으로 캐시 정리

2. **데이터베이스 연결 실패**
   - PostgreSQL 서비스 상태 확인
   - 환경 변수 설정 확인

3. **AWS 배포 실패**
   - AWS 자격 증명 확인
   - VPC 및 서브넷 설정 확인

더 자세한 문제 해결은 [DEPLOYMENT.md](DEPLOYMENT.md)를 참조하세요.