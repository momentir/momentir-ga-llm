#!/bin/bash

# PostgreSQL 연결 테스트 스크립트

echo "🔍 PostgreSQL 연결 테스트"
echo "=========================="

# 연결 정보
DB_HOST="momentir-cx-llm-db.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com"
DB_PORT="5432"
DB_NAME="momentir-cx-llm"
DB_USER="dbadmin"
DB_PASSWORD="5JYbqQeiuQI7tYNaDoFAnp0oL"

echo "📡 호스트: $DB_HOST"
echo "🔌 포트: $DB_PORT"
echo "🗄️  데이터베이스: $DB_NAME"
echo "👤 사용자: $DB_USER"
echo ""

# 네트워크 연결 테스트
echo "1️⃣  네트워크 연결 테스트..."
if command -v nc >/dev/null 2>&1; then
    if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
        echo "   ✅ 네트워크 연결 성공"
    else
        echo "   ❌ 네트워크 연결 실패"
        echo "   ➤ 보안 그룹 설정을 확인하세요"
        exit 1
    fi
else
    echo "   ⚠️  nc 명령어가 없습니다. telnet으로 테스트하세요:"
    echo "   telnet $DB_HOST $DB_PORT"
fi

# PostgreSQL 클라이언트 설치 확인
echo ""
echo "2️⃣  PostgreSQL 클라이언트 확인..."
if command -v psql >/dev/null 2>&1; then
    echo "   ✅ psql 클라이언트 설치됨"
    
    # 실제 데이터베이스 연결 테스트
    echo ""
    echo "3️⃣  데이터베이스 연결 테스트..."
    export PGPASSWORD="$DB_PASSWORD"
    
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" >/dev/null 2>&1; then
        echo "   ✅ 데이터베이스 연결 성공!"
        
        # 테이블 목록 조회
        echo ""
        echo "4️⃣  테이블 목록 조회..."
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
        "
        
    else
        echo "   ❌ 데이터베이스 연결 실패"
        echo "   ➤ 사용자명, 비밀번호, 데이터베이스명을 확인하세요"
    fi
    
    unset PGPASSWORD
    
else
    echo "   ⚠️  psql 클라이언트가 설치되지 않았습니다"
    echo ""
    echo "   설치 방법:"
    echo "   - macOS: brew install postgresql"
    echo "   - Ubuntu: sudo apt install postgresql-client"
    echo "   - CentOS: sudo yum install postgresql"
fi

echo ""
echo "🔧 DBeaver 연결 정보:"
echo "   Host: $DB_HOST"
echo "   Port: $DB_PORT" 
echo "   Database: $DB_NAME"
echo "   Username: $DB_USER"
echo "   Password: $DB_PASSWORD"
echo "   SSL Mode: require (권장)"
echo ""
echo "📖 추가 도움말:"
echo "   - AWS RDS 보안 그룹에서 5432 포트 허용 확인"
echo "   - 현재 IP 주소가 보안 그룹에 추가되어 있는지 확인"
echo "   - DBeaver에서 SSL 연결 사용 권장"