#!/bin/bash

# AWS 인프라 완전 삭제 스크립트
# 사용법: ./cleanup-infrastructure.sh ap-northeast-2 YOUR_AWS_ACCOUNT_ID

set -e

REGION=${1:-ap-northeast-2}
ACCOUNT_ID=${2}
PROJECT_NAME="momentir-ga-llm"

echo "🗑️  AWS 인프라 삭제 시작..."
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "Project: $PROJECT_NAME"
echo "=========================================="
echo "⚠️  경고: 이 스크립트는 모든 관련 리소스를 삭제합니다!"
echo "계속하려면 'yes'를 입력하세요:"
read -r confirmation

if [ "$confirmation" != "yes" ]; then
    echo "❌ 삭제가 취소되었습니다."
    exit 0
fi

# 삭제 단계를 위한 함수
cleanup_step() {
    local step_name="$1"
    local step_emoji="$2"
    echo ""
    echo "$step_emoji $step_name"
    echo "삭제 중..."
}

# 1. ECS 서비스 삭제 (먼저 desired count를 0으로 설정)
cleanup_step "ECS 서비스 중지 및 삭제" "🏗️"
if aws ecs describe-services --cluster $PROJECT_NAME-cluster --services $PROJECT_NAME-service --region $REGION &>/dev/null; then
    echo "ECS 서비스 중지 중..."
    aws ecs update-service \
        --cluster $PROJECT_NAME-cluster \
        --service $PROJECT_NAME-service \
        --desired-count 0 \
        --region $REGION || echo "서비스 중지 실패"
    
    echo "서비스가 완전히 중지될 때까지 대기 중..."
    aws ecs wait services-stable \
        --cluster $PROJECT_NAME-cluster \
        --services $PROJECT_NAME-service \
        --region $REGION || echo "서비스 대기 타임아웃"
    
    echo "ECS 서비스 삭제 중..."
    aws ecs delete-service \
        --cluster $PROJECT_NAME-cluster \
        --service $PROJECT_NAME-service \
        --region $REGION && echo "✅ ECS 서비스 삭제 완료" || echo "❌ ECS 서비스 삭제 실패"
else
    echo "ℹ️  ECS 서비스가 존재하지 않습니다."
fi

# 2. ECS 태스크 정의 해제 (최신 버전만)
cleanup_step "ECS 태스크 정의 해제" "📋"
LATEST_TASK_DEF=$(aws ecs describe-task-definition --task-definition $PROJECT_NAME --region $REGION --query 'taskDefinition.revision' --output text 2>/dev/null || echo "")
if [ -n "$LATEST_TASK_DEF" ] && [ "$LATEST_TASK_DEF" != "None" ]; then
    aws ecs deregister-task-definition \
        --task-definition $PROJECT_NAME:$LATEST_TASK_DEF \
        --region $REGION && echo "✅ 태스크 정의 해제 완료" || echo "❌ 태스크 정의 해제 실패"
else
    echo "ℹ️  활성 태스크 정의가 없습니다."
fi

# 3. ECS 클러스터 삭제
cleanup_step "ECS 클러스터 삭제" "🏗️"
aws ecs delete-cluster \
    --cluster $PROJECT_NAME-cluster \
    --region $REGION && echo "✅ ECS 클러스터 삭제 완료" || echo "ℹ️  ECS 클러스터가 존재하지 않습니다."

# 4. ALB 리스너 삭제
cleanup_step "ALB 리스너 삭제" "👂"
ALB_ARN=$(aws elbv2 describe-load-balancers --names $PROJECT_NAME-alb --region $REGION --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || echo "")
if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
    LISTENER_ARNS=$(aws elbv2 describe-listeners --load-balancer-arn $ALB_ARN --region $REGION --query 'Listeners[*].ListenerArn' --output text 2>/dev/null || echo "")
    for listener_arn in $LISTENER_ARNS; do
        aws elbv2 delete-listener --listener-arn $listener_arn --region $REGION && echo "✅ 리스너 삭제: $listener_arn" || echo "❌ 리스너 삭제 실패"
    done
else
    echo "ℹ️  ALB가 존재하지 않습니다."
fi

# 5. Target Group 삭제
cleanup_step "Target Group 삭제" "🎯"
TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups --names $PROJECT_NAME-tg --region $REGION --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || echo "")
if [ -n "$TARGET_GROUP_ARN" ] && [ "$TARGET_GROUP_ARN" != "None" ]; then
    aws elbv2 delete-target-group \
        --target-group-arn $TARGET_GROUP_ARN \
        --region $REGION && echo "✅ Target Group 삭제 완료" || echo "❌ Target Group 삭제 실패"
else
    echo "ℹ️  Target Group이 존재하지 않습니다."
fi

# 6. Application Load Balancer 삭제
cleanup_step "Application Load Balancer 삭제" "⚖️"
if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
    aws elbv2 delete-load-balancer \
        --load-balancer-arn $ALB_ARN \
        --region $REGION && echo "✅ ALB 삭제 시작 (완료까지 몇 분 소요)" || echo "❌ ALB 삭제 실패"
else
    echo "ℹ️  ALB가 존재하지 않습니다."
fi

# 7. RDS 인스턴스 삭제
cleanup_step "RDS 인스턴스 삭제" "🐘"
if aws rds describe-db-instances --db-instance-identifier $PROJECT_NAME-db --region $REGION &>/dev/null; then
    echo "RDS 인스턴스 삭제 중... (완료까지 10-15분 소요)"
    aws rds delete-db-instance \
        --db-instance-identifier $PROJECT_NAME-db \
        --skip-final-snapshot \
        --delete-automated-backups \
        --region $REGION && echo "✅ RDS 인스턴스 삭제 시작" || echo "❌ RDS 인스턴스 삭제 실패"
else
    echo "ℹ️  RDS 인스턴스가 존재하지 않습니다."
fi

# 8. RDS 서브넷 그룹 삭제 (RDS 인스턴스가 완전히 삭제된 후)
cleanup_step "RDS 서브넷 그룹 삭제 대기" "🗄️"
echo "RDS 인스턴스가 완전히 삭제될 때까지 대기 중... (최대 20분)"
aws rds wait db-instance-deleted --db-instance-identifier $PROJECT_NAME-db --region $REGION 2>/dev/null && {
    aws rds delete-db-subnet-group \
        --db-subnet-group-name $PROJECT_NAME-subnet-group \
        --region $REGION && echo "✅ RDS 서브넷 그룹 삭제 완료" || echo "❌ RDS 서브넷 그룹 삭제 실패"
} || echo "⏳ RDS 삭제 대기 타임아웃 - 수동으로 서브넷 그룹을 삭제해주세요."

# 9. 보안 그룹 삭제
cleanup_step "보안 그룹 삭제" "🔒"
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-sg" --region $REGION --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "")
if [ -n "$SECURITY_GROUP_ID" ] && [ "$SECURITY_GROUP_ID" != "None" ]; then
    # 보안 그룹 규칙 먼저 삭제
    echo "보안 그룹 규칙 삭제 중..."
    aws ec2 describe-security-groups --group-ids $SECURITY_GROUP_ID --region $REGION --query 'SecurityGroups[0].IpPermissions' --output json > /tmp/sg_rules.json 2>/dev/null || echo "{}"
    if [ -s /tmp/sg_rules.json ] && [ "$(cat /tmp/sg_rules.json)" != "[]" ]; then
        aws ec2 revoke-security-group-ingress \
            --group-id $SECURITY_GROUP_ID \
            --ip-permissions file:///tmp/sg_rules.json \
            --region $REGION 2>/dev/null || echo "보안 그룹 규칙 삭제 실패"
    fi
    
    # 보안 그룹 삭제
    sleep 10  # 약간의 대기 시간
    aws ec2 delete-security-group \
        --group-id $SECURITY_GROUP_ID \
        --region $REGION && echo "✅ 보안 그룹 삭제 완료" || echo "❌ 보안 그룹 삭제 실패 (다른 리소스에서 사용 중일 수 있음)"
    
    rm -f /tmp/sg_rules.json
else
    echo "ℹ️  보안 그룹이 존재하지 않습니다."
fi

# 10. CloudWatch 로그 그룹 삭제
cleanup_step "CloudWatch 로그 그룹 삭제" "📝"
aws logs delete-log-group \
    --log-group-name /ecs/$PROJECT_NAME \
    --region $REGION && echo "✅ 로그 그룹 삭제 완료" || echo "ℹ️  로그 그룹이 존재하지 않습니다."

# 11. ECR 리포지토리 삭제
cleanup_step "ECR 리포지토리 삭제" "📦"
if aws ecr describe-repositories --repository-names $PROJECT_NAME --region $REGION &>/dev/null; then
    echo "ECR 이미지 삭제 중..."
    aws ecr list-images --repository-name $PROJECT_NAME --region $REGION --query 'imageIds[*]' --output json > /tmp/images.json 2>/dev/null || echo "[]"
    if [ -s /tmp/images.json ] && [ "$(cat /tmp/images.json)" != "[]" ]; then
        aws ecr batch-delete-image \
            --repository-name $PROJECT_NAME \
            --image-ids file:///tmp/images.json \
            --region $REGION && echo "✅ ECR 이미지 삭제 완료" || echo "ECR 이미지 삭제 실패"
    fi
    
    aws ecr delete-repository \
        --repository-name $PROJECT_NAME \
        --force \
        --region $REGION && echo "✅ ECR 리포지토리 삭제 완료" || echo "❌ ECR 리포지토리 삭제 실패"
    
    rm -f /tmp/images.json
else
    echo "ℹ️  ECR 리포지토리가 존재하지 않습니다."
fi

# 12. Secrets Manager 시크릿 삭제
cleanup_step "Secrets Manager 시크릿 삭제" "🔐"
for secret in "database-url" "openai-api-key" "langsmith-api-key"; do
    SECRET_NAME="$PROJECT_NAME/$secret"
    if aws secretsmanager describe-secret --secret-id $SECRET_NAME --region $REGION &>/dev/null; then
        aws secretsmanager delete-secret \
            --secret-id $SECRET_NAME \
            --force-delete-without-recovery \
            --region $REGION && echo "✅ 시크릿 삭제: $SECRET_NAME" || echo "❌ 시크릿 삭제 실패: $SECRET_NAME"
    else
        echo "ℹ️  시크릿이 존재하지 않음: $SECRET_NAME"
    fi
done

# 13. IAM 역할 삭제 (기본 ECS 역할은 그대로 유지)
cleanup_step "정리 완료 확인" "🧹"
echo ""
echo "🎉 인프라 삭제 완료!"
echo "=========================================="
echo "📊 삭제 요약:"
echo "   ✅ ECS 서비스 및 클러스터"
echo "   ✅ Application Load Balancer 및 Target Group"
echo "   ✅ RDS PostgreSQL 인스턴스 및 서브넷 그룹"
echo "   ✅ 보안 그룹"
echo "   ✅ CloudWatch 로그 그룹"
echo "   ✅ ECR 리포지토리"
echo "   ✅ Secrets Manager 시크릿"
echo ""
echo "⚠️  참고사항:"
echo "   - ALB와 RDS 삭제는 시간이 걸릴 수 있습니다 (5-20분)"
echo "   - 일부 리소스는 의존성으로 인해 수동 삭제가 필요할 수 있습니다"
echo "   - 기본 VPC와 서브넷은 삭제되지 않습니다"
echo ""
echo "최종 확인을 위해 다음 명령어를 실행하세요:"
echo "   ./check-infrastructure.sh $REGION"