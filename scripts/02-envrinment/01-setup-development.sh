#!/bin/bash

# 개발 환경 초기 설정 스크립트
# 프로젝트를 처음 클론했을 때 실행하는 스크립트

set -e

echo "🛠️  보험계약자 메모 정제 시스템 개발 환경 설정"
echo "=================================================="

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Record system python path before any venv changes
time="$(date +%s)"
SYSTEM_PYTHON="$(command -v python3)"

echo "📁 프로젝트 디렉토리: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Python 버전 확인
echo ""
echo "🐍 Python 버전 확인 중..."
"$SYSTEM_PYTHON" --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3이 설치되지 않았습니다."
    echo "   macOS: brew install python3"
    echo "   Ubuntu: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
echo "   ✅ Python 3 설치 확인"

# Git 설정 확인
echo ""
echo "📝 Git 설정 확인 중..."
if [ -d ".git" ]; then
    echo "   ✅ Git 저장소 확인"
    echo "   ➤ 현재 브랜치: $(git branch --show-current)"
    echo "   ➤ 최신 커밋: $(git log -1 --oneline)"
else
    echo "   ⚠️  Git 저장소가 아닙니다."
fi

# 가상환경 생성
echo ""
echo "🔧 Python 가상환경 생성 중..."
if [ -d "venv" ]; then
    echo "   ⚠️  기존 가상환경이 있습니다. 삭제하고 새로 생성하시겠습니까? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        rm -rf venv
        echo "   ➤ 기존 가상환경 삭제"
        deactivate 2>/dev/null || true
    fi
fi

if [ ! -d "venv" ]; then
    "$SYSTEM_PYTHON" -m venv venv
    echo "   ✅ 가상환경 생성 완료"
fi

# 가상환경 활성화
source venv/bin/activate
echo "   ✅ 가상환경 활성화"

# pip 업그레이드
echo ""
echo "📦 pip 업그레이드 중..."
pip_upgrade_cmd="$(which python) -m pip install --upgrade pip"
$pip_upgrade_cmd
echo "   ✅ pip 업그레이드 완료"

# 의존성 설치
echo ""
echo "📦 프로젝트 의존성 설치 중..."
"$(which python)" -m pip install -r requirements.txt
echo "   ✅ 의존성 설치 완료"

# 환경변수 파일 생성
echo ""
echo "⚙️  환경변수 파일 설정 중..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# ===========================================
# 보험계약자 메모 정제 시스템 환경변수 설정
# ===========================================

# PostgreSQL 데이터베이스 설정
DATABASE_URL=postgresql://dbadmin:5JYbqQeiuQI7tYNaDoFAnp0oL@momentir-cx-llm-db.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com:5432/momentir-cx-llm

# OpenAI API 설정
# 실제 OpenAI API 키로 교체하세요
OPENAI_API_KEY=your-openai-api-key-here

# 개발 환경 설정
SQL_ECHO=true
AUTO_CREATE_TABLES=false

# LangSmith 모니터링 (선택사항)
# LANGSMITH_API_KEY=your-langsmith-api-key
# LANGSMITH_PROJECT=insurance-memo-refiner

# AWS 설정 (프로덕션 배포 시 사용)
# AWS_ACCESS_KEY_ID=your-aws-access-key
# AWS_SECRET_ACCESS_KEY=your-aws-secret-key
# AWS_DEFAULT_REGION=ap-northeast-2
EOF
    echo "   ✅ .env 파일 생성 완료"
    echo ""
    echo "   🔑 중요: .env 파일에서 다음 설정을 수정하세요:"
    echo "      • OPENAI_API_KEY: 실제 OpenAI API 키"
    echo "      • 필요시 LangSmith 설정"
else
    echo "   ✅ .env 파일이 이미 존재합니다"
fi

# Git ignore 확인
echo ""
echo "📝 .gitignore 설정 확인 중..."
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'EOF'
# Environment variables
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environment
venv/
env/
ENV/

# Database
*.db
*.sqlite
*.sqlite3
dev_memo.db

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Temporary files
tmp/
temp/
.tmp/
EOF
    echo "   ✅ .gitignore 파일 생성 완료"
else
    echo "   ✅ .gitignore 파일 존재"
fi

# 디렉토리 구조 생성
echo ""
echo "📁 필요한 디렉토리 생성 중..."
mkdir -p logs
mkdir -p temp
mkdir -p scripts
echo "   ✅ 디렉토리 구조 생성 완료"

# 개발 환경 테스트
echo ""
echo "🧪 개발 환경 테스트 중..."

# Python import 테스트
echo "   ➤ Python 모듈 import 테스트..."
python -c "
import sys
print(f'Python 버전: {sys.version}')

try:
    import fastapi
    print('✅ FastAPI import 성공')
except ImportError as e:
    print(f'❌ FastAPI import 실패: {e}')

try:
    import sqlalchemy
    print('✅ SQLAlchemy import 성공')
except ImportError as e:
    print(f'❌ SQLAlchemy import 실패: {e}')

try:
    import pandas
    print('✅ Pandas import 성공')
except ImportError as e:
    print(f'❌ Pandas import 실패: {e}')

try:
    import openai
    print('✅ OpenAI import 성공')
except ImportError as e:
    print(f'❌ OpenAI import 실패: {e}')
"

echo ""
echo "🎉 개발 환경 설정 완료!"
echo "=================================================="
echo ""
echo "📋 다음 단계:"
echo "   1. .env 파일에서 OPENAI_API_KEY 설정"
echo "   2. 로컬 서버 실행: ./scripts/02-envrinment/02-start-local.sh"
echo "   3. API 문서 확인: http://127.0.0.1:8000/docs"
echo ""
echo "🔧 유용한 명령어:"
echo "   • 서버 시작: ./scripts/02-envrinment/02-start-local.sh"
echo "   • 가상환경 활성화: source venv/bin/activate"
echo "   • 의존성 설치: pip install -r requirements.txt"
echo "   • DB 마이그레이션: alembic upgrade head"
echo ""
echo "📖 문서:"
echo "   • 프로젝트 개요: PROJECT_CONTEXT_NEW.md"
echo "   • AWS 배포: aws/README.md"
echo ""