#!/bin/bash

# 테스트 실행 스크립트
# Momentir CX LLM 프로젝트 테스트 자동화

set -e  # 에러 발생 시 스크립트 중단

echo "🧪 Momentir CX LLM 테스트 실행 시작"
echo "================================================="

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "📁 프로젝트 디렉토리: $PROJECT_DIR"
cd "$PROJECT_DIR"

# 가상환경 확인
if [ ! -d "venv" ]; then
    echo "❌ 가상환경이 없습니다. ./scripts/02-envrinment/02-start-local.sh를 먼저 실행하세요."
    exit 1
fi

# 가상환경 활성화
echo "🔧 가상환경 활성화 중..."
source venv/bin/activate

# pytest 설치 확인
echo "📦 pytest 설치 확인 중..."
if ! ./venv/bin/python -c "import pytest" 2>/dev/null; then
    echo "   ➤ pytest가 설치되지 않았습니다. 설치 중..."
    ./venv/bin/pip install pytest pytest-asyncio
    echo "   ✅ pytest 설치 완료"
else
    echo "   ✅ pytest 이미 설치됨"
fi

# 환경변수 설정
echo "⚙️  테스트 환경변수 설정 중..."
export TESTING=true
export OPENAI_API_KEY=test-key-for-testing
export DATABASE_URL=sqlite+aiosqlite:///./test_momentir.db
export SQL_ECHO=false
echo "   ✅ 환경변수 설정 완료"

# 테스트 실행 모드 선택
if [ "$1" = "--all" ]; then
    echo ""
    echo "🚀 전체 테스트 실행 중..."
    ./venv/bin/pytest -v
elif [ "$1" = "--sql-validator" ]; then
    echo ""
    echo "🔍 SQL 검증기 테스트 실행 중..."
    ./venv/bin/pytest tests/services/test_sql_validator.py -v
elif [ "$1" = "--security" ]; then
    echo ""
    echo "🔒 보안 관련 테스트 실행 중..."
    ./venv/bin/pytest -k "injection or security or validator" -v
elif [ "$1" = "--quick" ]; then
    echo ""
    echo "⚡ 빠른 테스트 실행 중 (slow 마커 제외)..."
    ./venv/bin/pytest -m "not slow" -v
elif [ "$1" = "--coverage" ]; then
    echo ""
    echo "📊 커버리지 포함 테스트 실행 중..."
    if ./venv/bin/python -c "import pytest_cov" 2>/dev/null; then
        ./venv/bin/pytest --cov=app --cov-report=html -v
        echo "   📈 커버리지 보고서: htmlcov/index.html"
    else
        echo "   ⚠️  pytest-cov가 설치되지 않았습니다. 기본 테스트를 실행합니다."
        ./venv/bin/pytest -v
    fi
else
    echo ""
    echo "📋 사용법:"
    echo "   ./scripts/run-tests.sh [옵션]"
    echo ""
    echo "옵션:"
    echo "   --all              전체 테스트 실행"
    echo "   --sql-validator    SQL 검증기 테스트만 실행"
    echo "   --security         보안 관련 테스트만 실행"
    echo "   --quick            빠른 테스트 (slow 제외)"
    echo "   --coverage         커버리지 포함 테스트"
    echo "   (옵션 없음)        이 도움말 표시"
    echo ""
    echo "예시:"
    echo "   ./scripts/run-tests.sh --sql-validator"
    echo "   ./scripts/run-tests.sh --security"
    echo "   ./scripts/run-tests.sh --all"
    echo ""
    echo "💡 더 자세한 정보는 documents/guide/testing/TESTING_GUIDE.md를 참조하세요."
fi

echo ""
echo "✅ 테스트 실행 완료"