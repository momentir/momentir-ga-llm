#!/bin/bash

# 데이터베이스 연결 문제 진단 스크립트
# 사용법: ./debug-db-connection.sh ap-northeast-2

set -e

REGION=${1:-ap-northeast-2}
PROJECT_NAME="momentir-cx-llm"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 데이터베이스 연결 문제 진단 시작..."
echo "Region: $REGION"
echo "Project: $PROJECT_NAME"
echo "=========================================="

# .env 파일에서 정보 로드
source "$PROJECT_ROOT/.env"

# DATABASE_URL 파싱
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo "📋 연결 정보:"
echo "   호스트: $DB_HOST"
echo "   포트: 5432"
echo "   사용자: $DB_USER"
echo "   데이터베이스: $DB_NAME"
echo ""

# 1. RDS 인스턴스 상세 정보 확인
echo "🗄️ RDS 인스턴스 상세 정보:"
aws rds describe-db-instances \
    --db-instance-identifier "$PROJECT_NAME-db" \
    --region "$REGION" \
    --no-cli-pager \
    --query 'DBInstances[0].{Status:DBInstanceStatus,PubliclyAccessible:PubliclyAccessible,Endpoint:Endpoint.Address,Port:Endpoint.Port,VpcSecurityGroups:VpcSecurityGroups[0].VpcSecurityGroupId}' \
    --output table

echo ""

# 2. 보안 그룹 규칙 확인
echo "🔒 보안 그룹 규칙 확인:"
SECURITY_GROUP_ID=$(aws rds describe-db-instances \
    --db-instance-identifier "$PROJECT_NAME-db" \
    --region "$REGION" \
    --no-cli-pager \
    --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' \
    --output text)

echo "보안 그룹 ID: $SECURITY_GROUP_ID"

aws ec2 describe-security-groups \
    --group-ids "$SECURITY_GROUP_ID" \
    --region "$REGION" \
    --no-cli-pager \
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`5432`]' \
    --output table

echo ""

# 3. 현재 공용 IP 확인
echo "🌐 현재 공용 IP 주소:"
MY_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "확인 불가")
echo "   현재 IP: $MY_IP"

# 4. 보안 그룹에서 현재 IP 허용 여부 확인
echo ""
echo "🔍 보안 그룹 5432 포트 규칙 상세:"
ALLOWED_CIDRS=$(aws ec2 describe-security-groups \
    --group-ids "$SECURITY_GROUP_ID" \
    --region "$REGION" \
    --no-cli-pager \
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`5432`].IpRanges[].CidrIp' \
    --output text)

echo "   허용된 CIDR: $ALLOWED_CIDRS"

if echo "$ALLOWED_CIDRS" | grep -q "0.0.0.0/0"; then
    echo "   ✅ 모든 IP에서 접근 허용됨"
else
    echo "   ⚠️  특정 IP만 허용됨. 현재 IP($MY_IP)가 포함되어 있는지 확인 필요"
fi

echo ""

# 5. 네트워크 연결 테스트
echo "🔗 네트워크 연결 테스트:"
echo "   호스트 해석 테스트..."
if nslookup "$DB_HOST" >/dev/null 2>&1; then
    echo "   ✅ DNS 해석 성공"
    
    # IP 주소 확인
    DB_IP=$(nslookup "$DB_HOST" | grep -A1 "Name:" | tail -n1 | awk '{print $2}' 2>/dev/null || echo "확인 불가")
    echo "   DB IP: $DB_IP"
else
    echo "   ❌ DNS 해석 실패"
fi

echo ""
echo "   포트 연결 테스트..."
if command -v nc >/dev/null 2>&1; then
    if timeout 5 nc -z "$DB_HOST" 5432 2>/dev/null; then
        echo "   ✅ 포트 5432 연결 성공"
    else
        echo "   ❌ 포트 5432 연결 실패"
    fi
else
    echo "   ⚠️  nc 명령이 없어 포트 테스트를 할 수 없습니다"
fi

echo ""

# 6. PostgreSQL 연결 시도 (상세 오류 출력)
echo "🐘 PostgreSQL 연결 시도 (상세 오류):"
export PGPASSWORD="$DB_PASSWORD"

echo "   연결 명령: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'SELECT 1;'"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" 2>&1 || true

echo ""

# 7. 문제 해결 제안
echo "🔧 문제 해결 방법:"
echo ""
echo "1. 보안 그룹 확인:"
echo "   현재 IP($MY_IP)가 5432 포트에 허용되어 있는지 확인"
echo ""
echo "2. 현재 IP를 보안 그룹에 추가:"
echo "   aws ec2 authorize-security-group-ingress \\"
echo "       --group-id $SECURITY_GROUP_ID \\"
echo "       --protocol tcp \\"
echo "       --port 5432 \\"
echo "       --cidr \${MY_IP}/32 \\"
echo "       --region $REGION"
echo ""
echo "3. 방화벽/VPN 확인:"
echo "   - 회사 방화벽이 5432 포트를 차단하는지 확인"
echo "   - VPN 사용 시 VPN IP로 접근 시도"
echo ""
echo "4. RDS 서브넷 그룹 확인:"
echo "   - 퍼블릭 서브넷에 위치하는지 확인"
echo "   - 인터넷 게이트웨이 설정 확인"
echo ""

# 환경변수 정리
unset PGPASSWORD