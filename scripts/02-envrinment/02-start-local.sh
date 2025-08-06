#!/bin/bash

# 보험계약자 메모 정제 시스템 로컬 실행 스크립트
# PROJECT_CONTEXT_NEW.md Phase 2 완료 버전

set -e  # 에러 발생 시 스크립트 중단

echo "🚀 보험계약자 메모 정제 시스템 로컬 실행 시작"
echo "=================================================="

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "📁 프로젝트 디렉토리: $PROJECT_DIR"
cd "$PROJECT_DIR"

# 가상환경 확인 및 생성
echo ""
echo "🔧 Python 가상환경 설정 중..."
if [ ! -d "venv" ]; then
    echo "   ➤ 가상환경이 없습니다. 새로 생성합니다..."
    python3 -m venv venv
    echo "   ✅ 가상환경 생성 완료"
else
    echo "   ✅ 기존 가상환경 발견"
fi

# 가상환경 활성화
echo "   ➤ 가상환경 활성화 중..."
source venv/bin/activate
echo "   ✅ 가상환경 활성화 완료"

# 의존성 설치
echo ""
echo "📦 의존성 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt
echo "   ✅ 의존성 설치 완료"

# 환경변수 설정 확인
echo ""
echo "⚙️  환경변수 설정 중..."

# .env 파일 생성 (없는 경우)
if [ ! -f ".env" ]; then
    echo "   ➤ .env 파일이 없습니다. 생성합니다..."
    cat > .env << EOF
# PostgreSQL 데이터베이스 설정
DATABASE_URL=postgresql://dbadmin:5JYbqQeiuQI7tYNaDoFAnp0oL@momentir-cx.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com:5432/momentir-cx-llm

# OpenAI API 설정 (실제 키로 교체 필요)
OPENAI_API_KEY=your-openai-api-key-here

# 개발 환경 설정
SQL_ECHO=true
AUTO_CREATE_TABLES=false

# LangSmith (선택사항)
# LANGSMITH_API_KEY=your-langsmith-key
# LANGSMITH_PROJECT=insurance-memo-refiner
EOF
    echo "   ✅ .env 파일 생성 완료"
    echo "   ⚠️  주의: .env 파일에서 OPENAI_API_KEY를 실제 키로 변경하세요!"
else
    echo "   ✅ .env 파일 존재"
fi

# PostgreSQL 환경변수 설정
source .env 2>/dev/null || echo "   ⚠️  .env 파일을 찾을 수 없습니다."

# DATABASE_URL 확인
if [ -z "$DATABASE_URL" ]; then
    echo "   ❌ DATABASE_URL이 설정되지 않았습니다."
    echo "   ➤ .env 파일에서 DATABASE_URL을 설정하세요"
    exit 1
else
    echo "   ✅ PostgreSQL 데이터베이스 URL 설정됨"
fi

# OpenAI API 키 확인
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your-openai-api-key-here" ]; then
    echo "   ⚠️  OpenAI API 키가 설정되지 않았습니다."
    echo "   ➤ 테스트용 임시 키를 사용합니다. (실제 LLM 기능은 동작하지 않음)"
    export OPENAI_API_KEY="test-key-for-local-development"
else
    echo "   ✅ OpenAI API 키 설정됨"
fi

# SQL 로그 활성화 (개발 모드)
export SQL_ECHO=true

echo "   ✅ 환경변수 설정 완료"

# 데이터베이스 연결 테스트
echo ""
echo "🗄️  PostgreSQL 데이터베이스 연결 테스트 중..."
echo "   ➤ 연결 테스트 실행..."

# 연결 테스트 (간단히)
DATABASE_URL="$DATABASE_URL" python3 -c "
import os
import asyncio
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from app.database import db_manager

async def test_connection():
    try:
        from sqlalchemy import text
        async with db_manager.engine.begin() as conn:
            result = await conn.execute(text('SELECT 1'))
        print('   ✅ PostgreSQL 데이터베이스 연결 성공')
        return True
    except Exception as e:
        print(f'   ❌ 데이터베이스 연결 실패: {e}')
        return False

if not asyncio.run(test_connection()):
    exit(1)
" || {
    echo "   ❌ 데이터베이스 연결에 실패했습니다."
    echo "   ➤ DATABASE_URL과 PostgreSQL 서버 상태를 확인하세요"
    exit 1
}

echo "   ✅ 데이터베이스 연결 확인 완료"

# 서버 시작
echo ""
echo "🌟 FastAPI 서버 시작 중..."
echo "=================================================="
echo "📍 서버 주소: http://127.0.0.1:8000"
echo "📖 API 문서: http://127.0.0.1:8000/docs"
echo "🔍 헬스체크: http://127.0.0.1:8000/health"
echo ""
echo "⭐ 주요 기능:"
echo "   • 메모 빠른 저장: POST /api/memo/quick-save"
echo "   • 메모 AI 정제: POST /api/memo/refine" 
echo "   • 조건부 분석: POST /api/memo/analyze"
echo "   • 고객 생성: POST /api/customer/create"
echo "   • 엑셀 업로드: POST /api/customer/excel-upload"
echo "   • 컬럼 매핑: POST /api/customer/column-mapping"
echo ""
echo "🛑 서버 중지: Ctrl+C"
echo "=================================================="

# FastAPI 서버 실행
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000