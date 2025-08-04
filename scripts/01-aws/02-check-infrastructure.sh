#!/bin/bash

# AWS 인프라 상태 확인 스크립트
# 사용법: ./check-infrastructure.sh ap-northeast-2

set -e

REGION=${1:-ap-northeast-2}
PROJECT_NAME="momentir-cx-llm"  # 변경된 프로젝트 이름

echo "🔍 AWS 인프라 상태 확인 중..."
echo "Region: $REGION"
echo "Project: $PROJECT_NAME"
echo "=========================================="

# 1. ECR 리포지토리 확인 (기존 momentir-ga-llm도 확인)
echo "📦 ECR 리포지토리 상태:"
OLD_PROJECT_NAME="momentir-ga-llm"

if aws ecr describe-repositories --repository-names $PROJECT_NAME --region $REGION --no-cli-pager &>/dev/null; then
    aws ecr describe-repositories \
        --repository-names $PROJECT_NAME \
        --region $REGION \
        --query 'repositories[0].{Name:repositoryName,URI:repositoryUri,Created:createdAt}' \
        --output table \
        --no-cli-pager
elif aws ecr describe-repositories --repository-names $OLD_PROJECT_NAME --region $REGION --no-cli-pager &>/dev/null; then
    echo "ℹ️  기존 ECR 리포지토리 사용 중: $OLD_PROJECT_NAME"
    aws ecr describe-repositories \
        --repository-names $OLD_PROJECT_NAME \
        --region $REGION \
        --query 'repositories[0].{Name:repositoryName,URI:repositoryUri,Created:createdAt}' \
        --output table \
        --no-cli-pager
else
    echo "❌ ECR 리포지토리가 존재하지 않습니다."
fi

echo ""

# 2. VPC 및 서브넷 정보
echo "🌐 VPC 및 서브넷 정보:"
DEFAULT_VPC=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region $REGION 2>/dev/null || echo "None")
if [ "$DEFAULT_VPC" != "None" ]; then
    echo "✅ Default VPC: $DEFAULT_VPC"
    SUBNET_COUNT=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$DEFAULT_VPC" --query 'length(Subnets)' --output text --region $REGION)
    echo "✅ 사용 가능한 서브넷 수: $SUBNET_COUNT"
    
    if [ "$SUBNET_COUNT" -lt 2 ]; then
        echo "⚠️  경고: 최소 2개의 서브넷이 필요합니다. (ALB 요구사항)"
    fi
else
    echo "❌ Default VPC를 찾을 수 없습니다."
fi

echo ""

# 3. 보안 그룹 확인
echo "🔒 보안 그룹 상태:"
aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$PROJECT_NAME-sg" \
    --query 'SecurityGroups[0].{GroupId:GroupId,GroupName:GroupName,VpcId:VpcId}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ 보안 그룹이 존재하지 않습니다."

echo ""

# 4. ECS 클러스터 확인
echo "🏗️ ECS 클러스터 상태:"
aws ecs describe-clusters \
    --clusters $PROJECT_NAME-cluster \
    --query 'clusters[0].{Name:clusterName,Status:status,ActiveServices:activeServicesCount,RunningTasks:runningTasksCount}' \
    --output table \
    --region $REGION \
    --no-cli-pager 2>/dev/null || echo "❌ ECS 클러스터가 존재하지 않습니다."

echo ""

# 5. CloudWatch 로그 그룹 확인
echo "📝 CloudWatch 로그 그룹 상태:"
aws logs describe-log-groups \
    --log-group-name-prefix "/ecs/$PROJECT_NAME" \
    --query 'logGroups[0].{LogGroupName:logGroupName,CreationTime:creationTime}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ 로그 그룹이 존재하지 않습니다."

echo ""

# 6. Application Load Balancer 확인
echo "⚖️ Application Load Balancer 상태:"
aws elbv2 describe-load-balancers \
    --names $PROJECT_NAME-alb \
    --query 'LoadBalancers[0].{Name:LoadBalancerName,State:State.Code,DNSName:DNSName}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ ALB가 존재하지 않습니다."

echo ""

# 7. Target Group 확인
echo "🎯 Target Group 상태:"
aws elbv2 describe-target-groups \
    --names $PROJECT_NAME-tg \
    --query 'TargetGroups[0].{Name:TargetGroupName,Protocol:Protocol,Port:Port,HealthyThreshold:HealthyThresholdCount}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ Target Group이 존재하지 않습니다."

echo ""

# 8. RDS 인스턴스 확인
echo "🐘 RDS 인스턴스 상태:"
aws rds describe-db-instances \
    --db-instance-identifier $PROJECT_NAME-db \
    --query 'DBInstances[0].{Identifier:DBInstanceIdentifier,Status:DBInstanceStatus,Engine:Engine,Class:DBInstanceClass,Endpoint:Endpoint.Address}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ RDS 인스턴스가 존재하지 않습니다."

echo ""

# 9. Secrets Manager 확인
echo "🔐 Secrets Manager 상태:"
echo "Database URL:"
aws secretsmanager describe-secret \
    --secret-id "$PROJECT_NAME/database-url" \
    --query '{Name:Name,CreatedDate:CreatedDate}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ database-url 시크릿이 존재하지 않습니다."

echo "OpenAI API Key:"
aws secretsmanager describe-secret \
    --secret-id "$PROJECT_NAME/openai-api-key" \
    --query '{Name:Name,CreatedDate:CreatedDate}' \
    --output table \
    --region $REGION 2>/dev/null || echo "❌ openai-api-key 시크릿이 존재하지 않습니다."

echo ""
echo "=========================================="
echo "🏁 인프라 상태 확인 완료"