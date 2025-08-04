#!/bin/bash

# AWS 인프라 설정 스크립트 v5 (프로젝트명 통일 + --no-cli-pager 추가)
# aws sts get-caller-identity
# 사용법: ./01-aws/01-setup-infrastructure.sh ap-northeast-2 YOUR_AWS_ACCOUNT_ID

set -e

REGION=${1:-ap-northeast-2}
ACCOUNT_ID=${2}
PROJECT_NAME="momentir-cx-llm"

if [ -z "$ACCOUNT_ID" ]; then
    echo "사용법: $0 AWS_REGION AWS_ACCOUNT_ID"
    echo "예: $0 ap-northeast-2 123456789012"
    echo ""
    echo "AWS Account ID를 확인하려면: aws sts get-caller-identity --query Account --output text --no-cli-pager"
    exit 1
fi

echo "🚀 AWS 인프라 설정 시작..."
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "Project: $PROJECT_NAME"
echo "=========================================="

# 진행 상황을 위한 함수
check_step() {
    local step_name="$1"
    local step_emoji="$2"
    echo ""
    echo "$step_emoji $step_name"
    echo "진행 중..."
}

# 1. ECR 리포지토리 확인/생성
check_step "ECR 리포지토리 확인/생성" "📦"
if aws --no-cli-pager ecr describe-repositories --repository-names "$PROJECT_NAME" --region "$REGION" &>/dev/null; then
    echo "ℹ️  ECR 리포지토리가 이미 존재합니다: $PROJECT_NAME"
else
    echo "ECR 리포지토리 생성 중..."
    if aws --no-cli-pager ecr create-repository \
        --repository-name "$PROJECT_NAME" \
        --region "$REGION" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256; then
        echo "✅ ECR 리포지토리 생성 완료: $PROJECT_NAME"
    else
        echo "❌ ECR 리포지토리 생성 실패"
        exit 1
    fi
fi

# 2. VPC 및 서브넷 정보 가져오기
check_step "VPC 및 서브넷 정보 수집" "🌐"

DEFAULT_VPC=$(aws --no-cli-pager ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$REGION")
if [ -z "$DEFAULT_VPC" ] || [ "$DEFAULT_VPC" = "None" ]; then
    echo "❌ Default VPC를 찾을 수 없습니다. VPC를 먼저 생성해주세요."
    exit 1
fi

echo "✅ Default VPC: $DEFAULT_VPC"
SUBNET_IDS=$(aws --no-cli-pager ec2 describe-subnets --filters "Name=vpc-id,Values=$DEFAULT_VPC" --query 'Subnets[*].SubnetId' --output text --region "$REGION")
SUBNET_ARRAY=($SUBNET_IDS)
if [ ${#SUBNET_ARRAY[@]} -lt 2 ]; then
    echo "❌ 최소 2개의 서브넷이 필요합니다. 현재: ${#SUBNET_ARRAY[@]}개"
    exit 1
fi

echo "✅ 사용 서브넷: ${SUBNET_ARRAY[0]}, ${SUBNET_ARRAY[1]}"

# 3. 보안 그룹 생성/규칙 설정
check_step "보안 그룹 생성 및 규칙" "🔒"
SECURITY_GROUP_ID=$(aws --no-cli-pager ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-sg" "Name=vpc-id,Values=$DEFAULT_VPC" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION" 2>/dev/null || echo "")
if [ -z "$SECURITY_GROUP_ID" ] || [ "$SECURITY_GROUP_ID" = "None" ] || [ "$SECURITY_GROUP_ID" = "null" ]; then
    SECURITY_GROUP_ID=$(aws --no-cli-pager ec2 create-security-group \
        --group-name "$PROJECT_NAME-sg" \
        --description "Security group for $PROJECT_NAME" \
        --vpc-id "$DEFAULT_VPC" \
        --region "$REGION" --output text)
    echo "✅ 보안 그룹 생성: $SECURITY_GROUP_ID"
else
    echo "ℹ️  보안 그룹 존재: $SECURITY_GROUP_ID"
fi

for port in 80 443 8000 5432; do
    if aws --no-cli-pager ec2 describe-security-groups --group-ids "$SECURITY_GROUP_ID" --region "$REGION" --query "SecurityGroups[0].IpPermissions[?FromPort==\`$port\` && ToPort==\`$port\`]" --output text | grep -q "^"; then
        echo "ℹ️  포트 $port 규칙 이미 존재"
    else
        aws --no-cli-pager ec2 authorize-security-group-ingress \
            --group-id "$SECURITY_GROUP_ID" \
            --protocol tcp --port "$port" --cidr 0.0.0.0/0 --region "$REGION" &&
        echo "✅ 포트 $port 허용"
    fi
done

# 4. ECS 클러스터 생성
check_step "ECS 클러스터 생성" "🏗️"
if aws --no-cli-pager ecs describe-clusters --clusters "$PROJECT_NAME-cluster" --region "$REGION" &>/dev/null; then
    echo "ℹ️  ECS 클러스터 이미 존재: $PROJECT_NAME-cluster"
else
    aws --no-cli-pager ecs create-cluster \
        --cluster-name "$PROJECT_NAME-cluster" \
        --capacity-providers FARGATE \
        --region "$REGION" &&
    echo "✅ ECS 클러스터 생성"
fi

# 5. CloudWatch 로그 그룹 생성
check_step "CloudWatch 로그 그룹 생성" "📝"
if aws --no-cli-pager logs describe-log-groups --log-group-name-prefix "/ecs/$PROJECT_NAME" --region "$REGION" --query 'logGroups[0].logGroupName' --output text | grep -q "/ecs/$PROJECT_NAME"; then
    echo "ℹ️  로그 그룹 존재: /ecs/$PROJECT_NAME"
else
    aws --no-cli-pager logs create-log-group \
        --log-group-name "/ecs/$PROJECT_NAME" --region "$REGION" &&
    echo "✅ 로그 그룹 생성"
fi

# 6. ALB 생성
check_step "Application Load Balancer 생성" "⚖️"
if aws --no-cli-pager elbv2 describe-load-balancers --names "$PROJECT_NAME-alb" --region "$REGION" &>/dev/null; then
    echo "ℹ️  ALB 존재: $PROJECT_NAME-alb"
    ALB_ARN=$(aws --no-cli-pager elbv2 describe-load-balancers --names "$PROJECT_NAME-alb" --region "$REGION" --query 'LoadBalancers[0].LoadBalancerArn' --output text)
else
    ALB_ARN=$(aws --no-cli-pager elbv2 create-load-balancer \
        --name "$PROJECT_NAME-alb" \
        --subnets "${SUBNET_ARRAY[0]}" "${SUBNET_ARRAY[1]}" \
        --security-groups "$SECURITY_GROUP_ID" \
        --region "$REGION" \
        --query 'LoadBalancers[0].LoadBalancerArn' --output text)
    echo "✅ ALB 생성: $ALB_ARN"
fi

# 7. Target Group 생성
check_step "Target Group 생성" "🎯"
if aws --no-cli-pager elbv2 describe-target-groups --names "$PROJECT_NAME-tg" --region "$REGION" &>/dev/null; then
    TARGET_GROUP_ARN=$(aws --no-cli-pager elbv2 describe-target-groups --names "$PROJECT_NAME-tg" --region "$REGION" --query 'TargetGroups[0].TargetGroupArn' --output text)
    echo "ℹ️  TG 존재: $PROJECT_NAME-tg"
else
    TARGET_GROUP_ARN=$(aws --no-cli-pager elbv2 create-target-group \
        --name "$PROJECT_NAME-tg" --protocol HTTP --port 8000 \
        --vpc-id "$DEFAULT_VPC" --target-type ip \
        --health-check-path /health --region "$REGION" \
        --query 'TargetGroups[0].TargetGroupArn' --output text)
    echo "✅ TG 생성: $TARGET_GROUP_ARN"
fi

# 8. ALB 리스너 생성
check_step "ALB 리스너 생성" "👂"
LISTEN_COUNT=$(aws --no-cli-pager elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --region "$REGION" --query 'length(Listeners)' --output text)
if [ "$LISTEN_COUNT" -gt 0 ]; then
    echo "ℹ️  리스너 이미 존재"
else
    aws --no-cli-pager elbv2 create-listener \
        --load-balancer-arn "$ALB_ARN" --protocol HTTP --port 80 \
        --default-actions Type=forward,TargetGroupArn="$TARGET_GROUP_ARN" \
        --region "$REGION" &&
    echo "✅ 리스너 생성"
fi

# 9. RDS 서브넷 그룹 생성
check_step "RDS 서브넷 그룹 생성" "🗄️"
if aws --no-cli-pager rds describe-db-subnet-groups --db-subnet-group-name "$PROJECT_NAME-subnet-group" --region "$REGION" &>/dev/null; then
    echo "ℹ️  서브넷 그룹 존재: $PROJECT_NAME-subnet-group"
else
    aws --no-cli-pager rds create-db-subnet-group \
        --db-subnet-group-name "$PROJECT_NAME-subnet-group" \
        --db-subnet-group-description "Subnet group for $PROJECT_NAME" \
        --subnet-ids "${SUBNET_ARRAY[0]}" "${SUBNET_ARRAY[1]}" \
        --region "$REGION" &&
    echo "✅ 서브넷 그룹 생성"
fi

# 10. RDS PostgreSQL 생성
check_step "RDS PostgreSQL 생성" "🐘"
if aws --no-cli-pager rds describe-db-instances --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION" &>/dev/null; then
    echo "ℹ️  RDS 존재: $PROJECT_NAME-db"
    STATUS=$(aws --no-cli-pager rds describe-db-instances --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION" --query 'DBInstances[0].DBInstanceStatus' --output text)
    if [ "$STATUS" = "available" ]; then
        ENDPOINT=$(aws --no-cli-pager rds describe-db-instances --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION" --query 'DBInstances[0].Endpoint.Address' --output text)
        echo "📍 DB Endpoint: $ENDPOINT"
    fi
else
    VERSION=$(aws --no-cli-pager rds describe-db-engine-versions --engine postgres --region "$REGION" --query 'DBEngineVersions[-1].EngineVersion' --output text)
    PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-25)
    echo "🔑 DB 비밀번호: $PASSWORD"
    aws --no-cli-pager rds create-db-instance \
        --db-instance-identifier "$PROJECT_NAME-db" \
        --db-instance-class db.t3.micro \
        --engine postgres --engine-version "$VERSION" \
        --master-username dbadmin --master-user-password "$PASSWORD" \
        --allocated-storage 20 --db-subnet-group-name "$PROJECT_NAME-subnet-group" \
        --vpc-security-group-ids "$SECURITY_GROUP_ID" \
        --backup-retention-period 7 --storage-encrypted --publicly-accessible \
        --region "$REGION" &&
    echo "✅ RDS 인스턴스 생성 시작"
    aws --no-cli-pager rds wait db-instance-available --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION"
    ENDPOINT=$(aws --no-cli-pager rds describe-db-instances --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION" --query 'DBInstances[0].Endpoint.Address' --output text)
    echo "📍 DB Endpoint: $ENDPOINT"
fi

# 11. 설정 파일 업데이트
check_step "설정 파일 업데이트" "📄"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DEF="$SCRIPT_DIR/task-definition.json"
SERVICE_DEF="$SCRIPT_DIR/service-definition.json"

if [ -f "$TASK_DEF" ]; then
    cp "$TASK_DEF" "$TASK_DEF.bak"
    sed -i.tmp "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g; s/YOUR_REGION/$REGION/g" "$TASK_DEF"
    rm -f "$TASK_DEF.tmp"
    echo "✅ task-definition.json 업데이트"
fi

if [ -f "$SERVICE_DEF" ]; then
    cp "$SERVICE_DEF" "$SERVICE_DEF.bak"
    sed -i.tmp "s/YOUR_SUBNET_ID_1/${SUBNET_ARRAY[0]}/g; s/YOUR_SUBNET_ID_2/${SUBNET_ARRAY[1]}/g; s/YOUR_SECURITY_GROUP_ID/$SECURITY_GROUP_ID/g; s|arn:aws:elasticloadbalancing:YOUR_REGION:YOUR_ACCOUNT_ID:targetgroup/.*|$TARGET_GROUP_ARN|g" "$SERVICE_DEF"
    rm -f "$SERVICE_DEF.tmp"
    echo "✅ service-definition.json 업데이트"
fi

# 완료 메시지
cat <<EOF

🎉 AWS 인프라 설정 완료!
🌐 프로젝트: $PROJECT_NAME
📋 주요 리소스:
   - ECR: $PROJECT_NAME
   - ECS Cluster: $PROJECT_NAME-cluster
   - SG: $SECURITY_GROUP_ID
   - ALB: $ALB_ARN
   - TG: $TARGET_GROUP_ARN
   - RDS: $PROJECT_NAME-db
   - DB Endpoint: ${ENDPOINT:-N/A}

🔗 pgvector 확장:
   psql -h ${ENDPOINT:-YOUR_ENDPOINT} -U dbadmin -d $PROJECT_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"
EOF
