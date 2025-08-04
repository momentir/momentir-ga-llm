#!/bin/bash

# AWS 인프라 설정 스크립트 v3 (명령어와 결과 처리 분리)
# 사용법: ./setup-infrastructure-v3.sh ap-northeast-2 YOUR_AWS_ACCOUNT_ID

set -e

REGION=${1:-ap-northeast-2}
ACCOUNT_ID=${2}
PROJECT_NAME="momentir-cx-llm"

if [ -z "$ACCOUNT_ID" ]; then
    echo "사용법: $0 AWS_REGION AWS_ACCOUNT_ID"
    echo "예: $0 ap-northeast-2 123456789012"
    echo ""
    echo "AWS Account ID를 확인하려면: aws sts get-caller-identity --query Account --output text"
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

# 1. ECR 리포지토리 생성
check_step "ECR 리포지토리 생성" "📦"

# 먼저 ECR 리포지토리가 존재하는지 확인
if aws ecr describe-repositories --repository-names "$PROJECT_NAME" --region "$REGION" &>/dev/null; then
    echo "ℹ️  ECR 리포지토리가 이미 존재합니다: $PROJECT_NAME"
else
    echo "ECR 리포지토리 생성 중..."
    if aws ecr create-repository \
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

echo "기본 VPC 정보 조회 중..."
DEFAULT_VPC=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$REGION")

if [ "$DEFAULT_VPC" = "None" ] || [ -z "$DEFAULT_VPC" ]; then
    echo "❌ Default VPC를 찾을 수 없습니다. VPC를 먼저 생성해주세요."
    exit 1
else
    echo "✅ Default VPC 확인: $DEFAULT_VPC"
fi

echo "서브넷 정보 조회 중..."
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$DEFAULT_VPC" --query 'Subnets[*].SubnetId' --output text --region "$REGION")
SUBNET_ARRAY=($SUBNET_IDS)

if [ ${#SUBNET_ARRAY[@]} -lt 2 ]; then
    echo "❌ ALB 생성을 위해 최소 2개의 서브넷이 필요합니다. 현재: ${#SUBNET_ARRAY[@]}개"
    exit 1
else
    echo "✅ 사용 가능한 서브넷: ${SUBNET_ARRAY[0]}, ${SUBNET_ARRAY[1]} (총 ${#SUBNET_ARRAY[@]}개)"
fi

# 3. 보안 그룹 생성
check_step "보안 그룹 생성" "🔒"

# 보안 그룹이 이미 존재하는지 확인
if aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-sg" "Name=vpc-id,Values=$DEFAULT_VPC" --region "$REGION" &>/dev/null; then
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-sg" "Name=vpc-id,Values=$DEFAULT_VPC" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION")
    echo "ℹ️  보안 그룹이 이미 존재합니다: $SECURITY_GROUP_ID"
else
    echo "보안 그룹 생성 중..."
    if aws ec2 create-security-group \
        --group-name "$PROJECT_NAME-sg" \
        --description "Security group for $PROJECT_NAME API" \
        --vpc-id "$DEFAULT_VPC" \
        --region "$REGION"; then
        SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-sg" "Name=vpc-id,Values=$DEFAULT_VPC" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION")
        echo "✅ 보안 그룹 생성 완료: $SECURITY_GROUP_ID"
    else
        echo "❌ 보안 그룹 생성 실패"
        exit 1
    fi
fi

# 보안 그룹 규칙 추가
echo "보안 그룹 규칙 확인 및 추가 중..."
for port in 80 443 8000 5432; do
    # 해당 포트 규칙이 이미 존재하는지 확인
    if aws ec2 describe-security-groups --group-ids "$SECURITY_GROUP_ID" --region "$REGION" --query "SecurityGroups[0].IpPermissions[?FromPort==\`$port\` && ToPort==\`$port\`]" --output text | grep -q "^"; then
        echo "ℹ️  포트 $port 규칙이 이미 존재합니다"
    else
        echo "포트 $port 규칙 추가 중..."
        if aws ec2 authorize-security-group-ingress \
            --group-id "$SECURITY_GROUP_ID" \
            --protocol tcp \
            --port "$port" \
            --cidr 0.0.0.0/0 \
            --region "$REGION"; then
            echo "✅ 포트 $port 허용 규칙 추가 완료"
        else
            echo "❌ 포트 $port 규칙 추가 실패"
        fi
    fi
done

# 4. ECS 클러스터 생성
check_step "ECS 클러스터 생성" "🏗️"

# ECS 클러스터가 존재하는지 확인
# TODO: ECS 클러스터 존재 여부 체크 필요
# (base) chris@Mac momentir-ga-llm % aws ecs list-clusters --region ap-northeast-2 { "clusterArns": [] }
CLUSTER_NAME="$PROJECT_NAME-cluster"

# 존재 여부 확인 (clusters 배열 길이를 가져옴)
CLUSTER_COUNT=$(aws --no-cli-pager ecs describe-clusters \
    --clusters "$CLUSTER_NAME" \
    --region "$REGION" \
    --query 'length(clusters)' \
    --output text)

if [ "$CLUSTER_COUNT" -gt 0 ]; then
    # 이미 있으면 상태만 조회
    CLUSTER_STATUS=$(aws --no-cli-pager ecs describe-clusters \
        --clusters "$CLUSTER_NAME" \
        --region "$REGION" \
        --query 'clusters[0].status' \
        --output text)
    echo "ℹ️  ECS 클러스터가 이미 존재합니다: $CLUSTER_NAME (상태: $CLUSTER_STATUS)"
else
    echo "ECS 클러스터 생성 중..."
    aws --no-cli-pager ecs create-cluster \
        --cluster-name "$CLUSTER_NAME" \
        --capacity-providers FARGATE \
        --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
        --region "$REGION" \
    && echo "✅ ECS 클러스터 생성 완료: $CLUSTER_NAME" \
    || { echo "❌ ECS 클러스터 생성 실패"; exit 1; }
fi


# 5. CloudWatch 로그 그룹 생성
check_step "CloudWatch 로그 그룹 생성" "📝"

# 로그 그룹이 존재하는지 확인
if aws logs describe-log-groups --log-group-name-prefix "/ecs/$PROJECT_NAME" --region "$REGION" --query 'logGroups[0].logGroupName' --output text | grep -q "/ecs/$PROJECT_NAME"; then
    echo "ℹ️  CloudWatch 로그 그룹이 이미 존재합니다: /ecs/$PROJECT_NAME"
else
    echo "CloudWatch 로그 그룹 생성 중..."
    if aws logs create-log-group \
        --log-group-name "/ecs/$PROJECT_NAME" \
        --region "$REGION"; then
        echo "✅ CloudWatch 로그 그룹 생성 완료: /ecs/$PROJECT_NAME"
    else
        echo "❌ CloudWatch 로그 그룹 생성 실패"
        exit 1
    fi
fi

# 6. Application Load Balancer 생성
check_step "Application Load Balancer 생성" "⚖️"

# ALB가 존재하는지 확인
if aws elbv2 describe-load-balancers --names "$PROJECT_NAME-alb" --region "$REGION" &>/dev/null; then
    ALB_ARN=$(aws elbv2 describe-load-balancers --names "$PROJECT_NAME-alb" --region "$REGION" --query 'LoadBalancers[0].LoadBalancerArn' --output text)
    ALB_STATE=$(aws elbv2 describe-load-balancers --names "$PROJECT_NAME-alb" --region "$REGION" --query 'LoadBalancers[0].State.Code' --output text)
    echo "ℹ️  ALB가 이미 존재합니다: $PROJECT_NAME-alb (상태: $ALB_STATE)"
else
    echo "Application Load Balancer 생성 중..."
    if aws elbv2 create-load-balancer \
        --name "$PROJECT_NAME-alb" \
        --subnets "${SUBNET_ARRAY[0]}" "${SUBNET_ARRAY[1]}" \
        --security-groups "$SECURITY_GROUP_ID" \
        --region "$REGION"; then
        ALB_ARN=$(aws elbv2 describe-load-balancers --names "$PROJECT_NAME-alb" --region "$REGION" --query 'LoadBalancers[0].LoadBalancerArn' --output text)
        echo "✅ ALB 생성 완료: $ALB_ARN"
    else
        echo "❌ ALB 생성 실패"
        exit 1
    fi
fi

# 7. Target Group 생성
check_step "Target Group 생성" "🎯"

# Target Group이 존재하는지 확인
if aws elbv2 describe-target-groups --names "$PROJECT_NAME-tg" --region "$REGION" &>/dev/null; then
    TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups --names "$PROJECT_NAME-tg" --region "$REGION" --query 'TargetGroups[0].TargetGroupArn' --output text)
    echo "ℹ️  Target Group이 이미 존재합니다: $PROJECT_NAME-tg"
else
    echo "Target Group 생성 중..."
    if aws elbv2 create-target-group \
        --name "$PROJECT_NAME-tg" \
        --protocol HTTP \
        --port 8000 \
        --vpc-id "$DEFAULT_VPC" \
        --target-type ip \
        --health-check-path /health \
        --health-check-interval-seconds 30 \
        --health-check-timeout-seconds 5 \
        --healthy-threshold-count 2 \
        --unhealthy-threshold-count 3 \
        --region "$REGION"; then
        TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups --names "$PROJECT_NAME-tg" --region "$REGION" --query 'TargetGroups[0].TargetGroupArn' --output text)
        echo "✅ Target Group 생성 완료: $TARGET_GROUP_ARN"
    else
        echo "❌ Target Group 생성 실패"
        exit 1
    fi
fi

# 8. ALB 리스너 생성
check_step "ALB 리스너 생성" "👂"

# 리스너가 존재하는지 확인
LISTENER_COUNT=$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --region "$REGION" --query 'length(Listeners)' --output text 2>/dev/null || echo "0")

if [ "$LISTENER_COUNT" -gt 0 ]; then
    echo "ℹ️  ALB 리스너가 이미 존재합니다 (${LISTENER_COUNT}개)"
else
    echo "ALB 리스너 생성 중..."
    aws elbv2 create-listener \
        --load-balancer-arn "$ALB_ARN" \
        --protocol HTTP \
        --port 80 \
        --default-actions Type=forward,TargetGroupArn="$TARGET_GROUP_ARN" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo "✅ ALB 리스너 생성 완료"
    else
        echo "❌ ALB 리스너 생성 실패"
        exit 1
    fi
fi

# 9. RDS 서브넷 그룹 생성
check_step "RDS 서브넷 그룹 생성" "🗄️"

# RDS 서브넷 그룹이 존재하는지 확인
if aws rds describe-db-subnet-groups --db-subnet-group-name "$PROJECT_NAME-subnet-group" --region "$REGION" &>/dev/null; then
    echo "ℹ️  RDS 서브넷 그룹이 이미 존재합니다: $PROJECT_NAME-subnet-group"
else
    echo "RDS 서브넷 그룹 생성 중..."
    if aws rds create-db-subnet-group \
        --db-subnet-group-name "$PROJECT_NAME-subnet-group" \
        --db-subnet-group-description "Subnet group for $PROJECT_NAME RDS" \
        --subnet-ids "${SUBNET_ARRAY[0]}" "${SUBNET_ARRAY[1]}" \
        --region "$REGION"; then
        echo "✅ RDS 서브넷 그룹 생성 완료: $PROJECT_NAME-subnet-group"
    else
        echo "❌ RDS 서브넷 그룹 생성 실패"
        exit 1
    fi
fi

# 10. RDS PostgreSQL 인스턴스 생성
check_step "RDS PostgreSQL 생성" "🐘"

# RDS 인스턴스가 존재하는지 확인
if aws rds describe-db-instances --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION" &>/dev/null; then
    RDS_STATUS=$(aws rds describe-db-instances --db-instance-identifier "$PROJECT_NAME-db" --region "$REGION" --query 'DBInstances[0].DBInstanceStatus' --output text)
    echo "ℹ️  RDS 인스턴스가 이미 존재합니다: $PROJECT_NAME-db (상태: $RDS_STATUS)"
else
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-25)
    echo "🔑 생성된 DB 비밀번호: $DB_PASSWORD"
    echo "⚠️  이 비밀번호를 안전한 곳에 저장해두세요!"
    
    echo "RDS PostgreSQL 인스턴스 생성 중... (5-10분 소요)"
    if aws rds create-db-instance \
        --db-instance-identifier "$PROJECT_NAME-db" \
        --db-instance-class db.t3.micro \
        --engine postgres \
        --engine-version 15.13 \
        --master-username postgres \
        --master-user-password "$DB_PASSWORD" \
        --allocated-storage 20 \
        --db-subnet-group-name "$PROJECT_NAME-subnet-group" \
        --vpc-security-group-ids "$SECURITY_GROUP_ID" \
        --backup-retention-period 7 \
        --storage-encrypted \
        --region "$REGION"; then
        echo "✅ RDS 인스턴스 생성 시작 완료: $PROJECT_NAME-db"
        echo "📝 DB 비밀번호를 기록해두세요: $DB_PASSWORD"
    else
        echo "❌ RDS 인스턴스 생성 실패"
        exit 1
    fi
fi

# 11. 설정 파일 업데이트
check_step "설정 파일 업데이트" "📄"

# 스크립트 위치 기준으로 파일 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DEF_FILE="$SCRIPT_DIR/task-definition.json"
SERVICE_DEF_FILE="$SCRIPT_DIR/service-definition.json"

# task-definition.json 업데이트
if [ -f "$TASK_DEF_FILE" ]; then
    echo "task-definition.json 업데이트 중..."
    cp "$TASK_DEF_FILE" "$TASK_DEF_FILE.bak"
    sed -i.tmp "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" "$TASK_DEF_FILE"
    sed -i.tmp "s/YOUR_REGION/$REGION/g" "$TASK_DEF_FILE"
    rm -f "$TASK_DEF_FILE.tmp"
    echo "✅ task-definition.json 업데이트 완료"
else
    echo "⚠️  task-definition.json 파일을 찾을 수 없습니다: $TASK_DEF_FILE"
fi

# service-definition.json 업데이트
if [ -f "$SERVICE_DEF_FILE" ]; then
    echo "service-definition.json 업데이트 중..."
    cp "$SERVICE_DEF_FILE" "$SERVICE_DEF_FILE.bak"
    sed -i.tmp "s/YOUR_SUBNET_ID_1/${SUBNET_ARRAY[0]}/g" "$SERVICE_DEF_FILE"
    sed -i.tmp "s/YOUR_SUBNET_ID_2/${SUBNET_ARRAY[1]}/g" "$SERVICE_DEF_FILE"
    sed -i.tmp "s/YOUR_SECURITY_GROUP_ID/$SECURITY_GROUP_ID/g" "$SERVICE_DEF_FILE"
    sed -i.tmp "s|arn:aws:elasticloadbalancing:YOUR_REGION:YOUR_ACCOUNT_ID:targetgroup/.*|$TARGET_GROUP_ARN|g" "$SERVICE_DEF_FILE"
    rm -f "$SERVICE_DEF_FILE.tmp"
    echo "✅ service-definition.json 업데이트 완료"
else
    echo "⚠️  service-definition.json 파일을 찾을 수 없습니다: $SERVICE_DEF_FILE"
fi

echo ""
echo "🎉 AWS 인프라 설정 완료!"
echo "=========================================="
echo "📋 다음 단계:"
echo "1. GitHub Secrets에 AWS 자격 증명 추가:"
echo "   - AWS_ACCESS_KEY_ID"
echo "   - AWS_SECRET_ACCESS_KEY"
echo ""
echo "2. RDS 인스턴스 완료 대기 (5-10분 소요)"
echo "   확인: aws rds describe-db-instances --db-instance-identifier $PROJECT_NAME-db --region $REGION --query 'DBInstances[0].DBInstanceStatus'"
echo ""
echo "3. 생성된 리소스 확인:"
echo "   ./check-infrastructure.sh $REGION"
echo ""
echo "🌐 주요 리소스 요약:"
echo "   - ECR Repository: $PROJECT_NAME"
echo "   - ECS Cluster: $PROJECT_NAME-cluster"
echo "   - Security Group: $SECURITY_GROUP_ID"
echo "   - Load Balancer: $ALB_ARN"
echo "   - Target Group: $TARGET_GROUP_ARN"
echo "   - RDS Instance: $PROJECT_NAME-db"