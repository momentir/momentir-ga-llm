# Momentir GA LLM - 보험계약자 메모 정제 API

보험계약자의 고객 메모를 LLM을 통해 정제하고 분석하는 FastAPI 기반 시스템입니다.

## ✨ 주요 기능

- **메모 정제**: 고객 메모를 구조화된 형태로 정제
- **메모 분석**: 정제된 메모에서 핵심 정보 추출
- **벡터 검색**: pgvector를 활용한 의미 기반 메모 검색
- **PostgreSQL 통합**: 완전한 데이터 영속성

## 🛠️ 기술 스택

- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL + pgvector
- **LLM**: OpenAI GPT (LangChain 통합)
- **Container**: Docker, Docker Compose
- **Cloud**: AWS ECS Fargate + RDS
- **CI/CD**: GitHub Actions

## 🚀 로컬 개발 환경 설정

### 1. 저장소 클론 및 환경 설정

```bash
git clone <repository-url>
cd momentir-ga-llm

# 환경 변수 파일 생성
cp .env.example .env
# .env 파일에 실제 API 키 입력
```

### 2. Docker Compose로 로컬 실행

```bash
# 컨테이너 빌드 및 실행
docker-compose up --build

# 백그라운드 실행
docker-compose up -d --build
```

### 3. API 테스트

- **API 문서**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

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

## 📡 API 엔드포인트

### 메인 엔드포인트
- `GET /` - API 정보 및 엔드포인트 목록
- `GET /health` - 헬스 체크

### 메모 관리
- `POST /api/memo/refine` - 메모 정제
- `POST /api/memo/analyze` - 메모 분석
- `GET /api/memo/memo/{memo_id}` - 메모 조회

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
momentir-ga-llm/
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