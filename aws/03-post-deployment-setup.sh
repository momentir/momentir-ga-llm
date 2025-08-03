#!/bin/bash

# AWS 인프라 배포 후 설정 스크립트 v1 (PROJECT_CONTEXT_NEW.md 지침 적용)
# 사용법: ./03-post-deployment-setup.sh ap-northeast-2
# 전제조건: 01-setup-infrastructure.sh가 성공적으로 완료되어야 함

set -e

REGION=${1:-ap-northeast-2}
PROJECT_NAME="momentir-cx-llm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 배포 후 설정 시작..."
echo "Region: $REGION"
echo "Project: $PROJECT_NAME"
echo "Working Directory: $PROJECT_ROOT"
echo "=========================================="

# 진행 상황을 위한 함수
check_step() {
    local step_name="$1"
    local step_emoji="$2"
    echo ""
    echo "$step_emoji $step_name"
    echo "진행 중..."
}

# 에러 처리 함수
handle_error() {
    local step_name="$1"
    local error_message="$2"
    echo "❌ $step_name 실패: $error_message"
    exit 1
}

# 1. 환경 변수 로드 및 확인
check_step "환경 변수 확인" "🔍"

# .env 파일 존재 확인
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    handle_error "환경 설정" ".env 파일이 존재하지 않습니다. 먼저 01-setup-infrastructure.sh를 실행하세요."
fi

# .env 파일에서 DATABASE_URL 추출
source "$PROJECT_ROOT/.env"

if [ -z "$DATABASE_URL" ]; then
    handle_error "환경 설정" "DATABASE_URL이 설정되지 않았습니다."
fi

# DATABASE_URL 파싱
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo "✅ 데이터베이스 정보 확인:"
echo "   호스트: $DB_HOST"
echo "   사용자: $DB_USER"
echo "   데이터베이스: $DB_NAME"

# 2. RDS 인스턴스 상태 확인
check_step "RDS 인스턴스 상태 확인" "🗄️"

echo "RDS 인스턴스 상태 조회 중..."
RDS_STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier "$PROJECT_NAME-db" \
    --region "$REGION" \
    --no-cli-pager \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text 2>/dev/null || echo "not-found")

if [ "$RDS_STATUS" = "available" ]; then
    echo "✅ RDS 인스턴스가 사용 가능합니다: $PROJECT_NAME-db"
elif [ "$RDS_STATUS" = "not-found" ]; then
    handle_error "RDS 확인" "RDS 인스턴스를 찾을 수 없습니다. 먼저 01-setup-infrastructure.sh를 실행하세요."
else
    echo "⏳ RDS 인스턴스 상태: $RDS_STATUS"
    echo "RDS 인스턴스가 사용 가능해질 때까지 대기 중..."
    aws rds wait db-instance-available \
        --db-instance-identifier "$PROJECT_NAME-db" \
        --region "$REGION" \
        --no-cli-pager
    echo "✅ RDS 인스턴스가 사용 가능해졌습니다"
fi

# 3. PostgreSQL 클라이언트 설치 확인
check_step "PostgreSQL 클라이언트 확인" "🔧"

if command -v psql >/dev/null 2>&1; then
    PSQL_VERSION=$(psql --version | head -n1)
    echo "✅ PostgreSQL 클라이언트 설치됨: $PSQL_VERSION"
else
    echo "⚠️  PostgreSQL 클라이언트가 설치되지 않았습니다."
    echo "설치 방법:"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "   macOS: brew install postgresql"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "   Ubuntu/Debian: sudo apt-get install postgresql-client"
        echo "   CentOS/RHEL: sudo yum install postgresql"
    fi
    
    read -p "PostgreSQL 클라이언트를 설치하고 Enter를 눌러주세요... "
    
    if ! command -v psql >/dev/null 2>&1; then
        handle_error "PostgreSQL 클라이언트" "psql 명령을 찾을 수 없습니다."
    fi
fi

# 4. 데이터베이스 연결 테스트 및 생성
check_step "데이터베이스 연결 테스트" "🔗"

echo "데이터베이스 연결 테스트 중..."
# 비밀번호를 환경변수로 설정하여 프롬프트 없이 연결
export PGPASSWORD="$DB_PASSWORD"

# 먼저 기본 postgres 데이터베이스에 연결 테스트
if psql -h "$DB_HOST" -U "$DB_USER" -d "postgres" -c "SELECT version();" >/dev/null 2>&1; then
    echo "✅ RDS 연결 성공"
    
    # PostgreSQL 버전 확인
    PG_VERSION=$(psql -h "$DB_HOST" -U "$DB_USER" -d "postgres" -t -c "SELECT version();" 2>/dev/null | head -n1 | xargs)
    echo "   버전: $PG_VERSION"
    
    # 대상 데이터베이스 존재 확인
    DB_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d "postgres" -t -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" 2>/dev/null | xargs || echo "")
    
    if [ "$DB_EXISTS" = "1" ]; then
        echo "✅ 데이터베이스 '$DB_NAME'이 이미 존재합니다"
    else
        echo "📝 데이터베이스 '$DB_NAME' 생성 중..."
        if psql -h "$DB_HOST" -U "$DB_USER" -d "postgres" -c "CREATE DATABASE \"$DB_NAME\";" >/dev/null 2>&1; then
            echo "✅ 데이터베이스 '$DB_NAME' 생성 완료"
        else
            handle_error "데이터베이스 생성" "데이터베이스 '$DB_NAME' 생성에 실패했습니다."
        fi
    fi
    
    # 최종 대상 데이터베이스 연결 테스트
    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT current_database();" >/dev/null 2>&1; then
        echo "✅ 데이터베이스 '$DB_NAME' 연결 성공"
    else
        handle_error "데이터베이스 연결" "데이터베이스 '$DB_NAME'에 연결할 수 없습니다."
    fi
else
    handle_error "데이터베이스 연결" "RDS에 연결할 수 없습니다. 보안 그룹과 네트워크 설정을 확인하세요."
fi

# 5. pgvector 확장 설치
check_step "pgvector 확장 설치" "🧩"

echo "pgvector 확장 설치 중..."

# pgvector 확장이 이미 설치되어 있는지 확인
VECTOR_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT 1 FROM pg_extension WHERE extname='vector';" 2>/dev/null | xargs || echo "")

if [ "$VECTOR_EXISTS" = "1" ]; then
    echo "ℹ️  pgvector 확장이 이미 설치되어 있습니다"
else
    echo "pgvector 확장 설치 시도 중..."
    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null 2>&1; then
        echo "✅ pgvector 확장 설치 완료"
    else
        echo "⚠️  pgvector 확장 설치 실패 - RDS에서 지원하지 않을 수 있습니다"
        echo "   PostgreSQL 15+ 버전에서는 대부분 지원됩니다"
        
        # 설치 가능한 확장 목록 확인
        echo "설치 가능한 확장 목록 확인 중..."
        psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT name FROM pg_available_extensions WHERE name LIKE '%vector%';" 2>/dev/null || true
    fi
fi

# 6. Python 의존성 설치 확인
check_step "Python 의존성 확인" "🐍"

cd "$PROJECT_ROOT"

# 가상환경 활성화 상태 확인
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  가상환경이 활성화되지 않았습니다."
    echo "다음 명령을 실행하여 가상환경을 활성화하세요:"
    echo "   source venv/bin/activate  # Linux/macOS"
    echo "   venv\\Scripts\\activate     # Windows"
    
    read -p "가상환경을 활성화하고 Enter를 눌러주세요... "
fi

# requirements.txt 존재 확인
if [ ! -f "requirements.txt" ]; then
    handle_error "의존성 확인" "requirements.txt 파일이 존재하지 않습니다."
fi

echo "Python 의존성 설치 중..."
if pip install -r requirements.txt >/dev/null 2>&1; then
    echo "✅ Python 의존성 설치 완료"
else
    handle_error "의존성 설치" "Python 의존성 설치에 실패했습니다."
fi

# 7. Alembic 마이그레이션 실행
check_step "Alembic 마이그레이션 실행" "🔄"

# Alembic 설정 확인
if [ ! -f "alembic.ini" ]; then
    handle_error "Alembic 설정" "alembic.ini 파일이 존재하지 않습니다."
fi

# Mock 모드 비활성화
export USE_MOCK_MODE=false

echo "데이터베이스 마이그레이션 실행 중..."
if alembic upgrade head; then
    echo "✅ 데이터베이스 마이그레이션 완료"
else
    handle_error "마이그레이션" "Alembic 마이그레이션에 실패했습니다."
fi

# 8. 테이블 생성 확인
check_step "테이블 생성 확인" "📋"

echo "생성된 테이블 확인 중..."
TABLES=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT tablename FROM pg_tables WHERE schemaname='public';" 2>/dev/null | xargs)

if [ -n "$TABLES" ]; then
    echo "✅ 생성된 테이블: $TABLES"
else
    echo "⚠️  테이블이 생성되지 않았습니다. 마이그레이션을 확인하세요."
fi

# 9. 애플리케이션 시작 준비
check_step "애플리케이션 시작 준비" "🚀"

echo "FastAPI 서버 시작 준비 중..."

# 환경변수 내보내기
export USE_MOCK_MODE=false
export DATABASE_URL="$DATABASE_URL"

echo "✅ 환경변수 설정 완료"
echo "   USE_MOCK_MODE: $USE_MOCK_MODE"
echo "   DATABASE_URL: postgresql://***:***@$DB_HOST:5432/$DB_NAME"

# 10. 선택적 애플리케이션 테스트
echo ""
echo "📋 배포 후 설정 완료!"
echo "=========================================="
echo "🎉 모든 설정이 완료되었습니다!"
echo ""
echo "📋 다음 단계:"
echo "1. 애플리케이션 시작:"
echo "   cd $PROJECT_ROOT"
echo "   export USE_MOCK_MODE=false"
echo "   uvicorn app.main:app --reload --port 8000"
echo ""
echo "2. API 테스트:"
echo "   curl http://localhost:8000/"
echo "   curl http://localhost:8000/health"
echo ""
echo "3. API 문서 확인:"
echo "   http://localhost:8000/docs"
echo ""
echo "4. 인프라 상태 확인:"
echo "   ./aws/02-check-infrastructure.sh $REGION"
echo ""

# 선택적 서버 시작
read -p "지금 FastAPI 서버를 시작하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 FastAPI 서버를 시작합니다..."
    echo "서버를 중지하려면 Ctrl+C를 누르세요."
    echo ""
    
    # 서버 시작
    cd "$PROJECT_ROOT"
    uvicorn app.main:app --reload --port 8000
else
    echo "✅ 설정 완료. 수동으로 서버를 시작하세요."
fi

# 환경변수 정리
unset PGPASSWORD