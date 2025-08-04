# AWS 인프라 배포 스크립트

이 디렉토리에는 momentir-cx-llm 프로젝트의 AWS 인프라를 배포하고 관리하는 스크립트들이 포함되어 있습니다.

## 📋 스크립트 실행 순서

### 1️⃣ 인프라 배포
```bash
./01-setup-infrastructure.sh ap-northeast-2 YOUR_AWS_ACCOUNT_ID
```
**기능**: AWS 인프라 전체 배포
- ECR 리포지토리
- VPC, 보안 그룹, 서브넷
- ECS 클러스터
- Application Load Balancer (ALB)
- RDS PostgreSQL 인스턴스 (퍼블릭 액세스)
- CloudWatch 로그 그룹

**출력**: 생성된 DATABASE_URL과 DB 비밀번호

### 2️⃣ 인프라 상태 확인
```bash
./02-check-infrastructure.sh ap-northeast-2
```
**기능**: 배포된 리소스 상태 확인
- 모든 AWS 리소스의 현재 상태 표시
- 문제가 있는 리소스 식별

### 3️⃣ 배포 후 설정
```bash
./03-post-deployment-setup.sh ap-northeast-2
```
**기능**: 애플리케이션 실행 준비
- RDS 연결 테스트
- pgvector 확장 설치
- Python 의존성 설치
- Alembic 마이그레이션 실행
- FastAPI 서버 시작 (선택사항)

### 4️⃣ 인프라 정리 (선택사항)
```bash
./04-cleanup-infrastructure.sh ap-northeast-2
```
**기능**: 생성된 AWS 리소스 완전 삭제
- 모든 생성된 리소스 삭제
- 비용 절약을 위한 정리

## 🔧 사전 요구사항

### AWS CLI 설정
```bash
aws configure
# 또는
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=ap-northeast-2
```

### Account ID 확인
```bash
aws sts get-caller-identity --query Account --output text
```

### PostgreSQL 클라이언트 설치
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# CentOS/RHEL
sudo yum install postgresql
```

## 📊 생성되는 리소스

| 리소스 | 이름 | 설명 |
|--------|------|------|
| ECR Repository | `momentir-cx-llm` | Docker 이미지 저장소 |
| ECS Cluster | `momentir-cx-llm-cluster` | 컨테이너 오케스트레이션 |
| RDS Instance | `momentir-cx-llm-db` | PostgreSQL 17.5 데이터베이스 |
| Security Group | `momentir-cx-llm-sg` | 네트워크 보안 규칙 |
| ALB | `momentir-cx-llm-alb` | 로드 밸런서 |
| Target Group | `momentir-cx-llm-tg` | ALB 타겟 그룹 |

## 🔒 보안 설정

- **RDS**: 퍼블릭 액세스 활성화 (개발용)
- **보안 그룹**: 포트 80, 443, 8000, 5432 허용
- **DB 사용자**: `dbadmin` (PostgreSQL 예약어 회피)
- **DB 비밀번호**: 자동 생성 (25자 랜덤)

## 🌍 환경변수

스크립트 완료 후 다음 환경변수가 설정됩니다:

```bash
DATABASE_URL=postgresql://dbadmin:PASSWORD@ENDPOINT:5432/momentir-cx-llm
USE_MOCK_MODE=false
AWS_DEFAULT_REGION=ap-northeast-2
```

## 🚨 문제 해결

### 일반적인 오류

1. **보안 그룹 ID가 None**: 
   - 올바른 Account ID 사용 확인
   - VPC 존재 여부 확인

2. **RDS 생성 실패**:
   - 사용자명 예약어 충돌 (`admin` → `dbadmin`)
   - 서브넷 그룹 설정 확인

3. **pgvector 설치 실패**:
   - PostgreSQL 15+ 버전 확인
   - RDS 확장 지원 여부 확인

### 로그 확인
```bash
# CloudWatch 로그
aws logs describe-log-groups --region ap-northeast-2

# RDS 로그
aws rds describe-db-log-files --db-instance-identifier momentir-cx-llm-db --region ap-northeast-2
```

## 💰 비용 관리

- **프리티어 사용**: 모든 리소스는 AWS 프리티어 내에서 구성
- **자동 백업**: 7일 보존 (최소값)
- **스토리지**: 20GB (최소값)
- **인스턴스**: db.t3.micro (프리티어)

## 📝 참고사항

- 스크립트는 PROJECT_CONTEXT_NEW.md 요구사항을 완전히 준수
- 모든 AWS CLI 명령에 `--no-cli-pager` 옵션 적용
- 각 단계마다 성공/실패 분기 처리
- 기존 리소스 존재 시 재사용