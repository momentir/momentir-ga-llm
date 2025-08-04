#!/bin/bash

# 빠른 인프라 삭제 스크립트 (확인 없이 실행)
# 개발/테스트용 - 사용법: ./quick-cleanup.sh ap-northeast-2

set -e

REGION=${1:-ap-northeast-2}
PROJECT_NAME="momentir-cx-llm"

echo "🚀 빠른 삭제 시작... (확인 없이 진행)"
echo "Region: $REGION"
echo "Project: $PROJECT_NAME"

# 병렬로 삭제 가능한 것들을 먼저 삭제
echo "1️⃣ ECS 서비스 중지..."
aws ecs update-service --cluster $PROJECT_NAME-cluster --service $PROJECT_NAME-service --desired-count 0 --region $REGION 2>/dev/null || echo "ECS 서비스 없음"

echo "2️⃣ RDS 인스턴스 삭제 시작..."
aws rds delete-db-instance --db-instance-identifier $PROJECT_NAME-db --skip-final-snapshot --delete-automated-backups --region $REGION 2>/dev/null || echo "RDS 없음"

echo "3️⃣ ALB 삭제..."
ALB_ARN=$(aws elbv2 describe-load-balancers --names $PROJECT_NAME-alb --region $REGION --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || echo "")
if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
    aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $REGION 2>/dev/null || echo "ALB 삭제 실패"
fi

echo "4️⃣ ECS 서비스 삭제..."
sleep 30  # 서비스 중지 대기
aws ecs delete-service --cluster $PROJECT_NAME-cluster --service $PROJECT_NAME-service --region $REGION 2>/dev/null || echo "ECS 서비스 없음"

echo "5️⃣ Target Group 삭제..."
TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups --names $PROJECT_NAME-tg --region $REGION --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || echo "")
if [ -n "$TARGET_GROUP_ARN" ] && [ "$TARGET_GROUP_ARN" != "None" ]; then
    aws elbv2 delete-target-group --target-group-arn $TARGET_GROUP_ARN --region $REGION 2>/dev/null || echo "TG 삭제 실패"
fi

echo "6️⃣ ECS 클러스터 삭제..."
aws ecs delete-cluster --cluster $PROJECT_NAME-cluster --region $REGION 2>/dev/null || echo "ECS 클러스터 없음"

echo "7️⃣ ECR 리포지토리 삭제..."
aws ecr delete-repository --repository-name $PROJECT_NAME --force --region $REGION 2>/dev/null || echo "ECR 없음"

echo "8️⃣ CloudWatch 로그 그룹 삭제..."
aws logs delete-log-group --log-group-name /ecs/$PROJECT_NAME --region $REGION 2>/dev/null || echo "로그 그룹 없음"

echo "9️⃣ Secrets Manager 시크릿 삭제..."
for secret in "database-url" "openai-api-key" "langsmith-api-key"; do
    aws secretsmanager delete-secret --secret-id "$PROJECT_NAME/$secret" --force-delete-without-recovery --region $REGION 2>/dev/null || echo "시크릿 없음: $secret"
done

echo "🔟 보안 그룹 삭제..."
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-sg" --region $REGION --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "")
if [ -n "$SECURITY_GROUP_ID" ] && [ "$SECURITY_GROUP_ID" != "None" ]; then
    sleep 60  # ALB 삭제 대기
    aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID --region $REGION 2>/dev/null || echo "보안 그룹 삭제 실패 (나중에 수동 삭제 필요)"
fi

echo ""
echo "✅ 빠른 삭제 완료!"
echo "⚠️  RDS와 ALB는 백그라운드에서 삭제 중입니다 (5-20분 소요)"
echo "⚠️  일부 리소스는 의존성으로 인해 수동 삭제가 필요할 수 있습니다"