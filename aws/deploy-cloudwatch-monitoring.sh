#!/bin/bash

# CloudWatch 모니터링이 포함된 ECS Fargate 배포 스크립트
# 사용법: ./deploy-cloudwatch-monitoring.sh

set -e

echo "🚀 CloudWatch 모니터링 포함 ECS Fargate 배포 시작"

# 환경 변수 확인
CLUSTER_NAME="momentir-cx-llm-cluster"
SERVICE_NAME="momentir-cx-llm-service"
TASK_DEFINITION_FAMILY="momentir-cx-llm"
AWS_REGION="ap-northeast-2"

echo "📋 배포 정보:"
echo "   클러스터: $CLUSTER_NAME"
echo "   서비스: $SERVICE_NAME"
echo "   태스크 정의: $TASK_DEFINITION_FAMILY"
echo "   리전: $AWS_REGION"

# 1. ECS Task Role에 CloudWatch 권한 추가
echo ""
echo "🔐 1. ECS Task Role CloudWatch 권한 확인"
TASK_ROLE_NAME="momentir-cx-llm-task-role"

# Task Role 정책 확인
if aws iam get-role --role-name $TASK_ROLE_NAME > /dev/null 2>&1; then
    echo "   ✅ Task Role 존재: $TASK_ROLE_NAME"
    
    # CloudWatch 정책 첨부
    echo "   📝 CloudWatch 로그 정책 첨부 중..."
    aws iam attach-role-policy \
        --role-name $TASK_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess \
        --no-cli-pager || echo "   ⚠️  정책이 이미 첨부되었을 수 있습니다"
    
    # 커스텀 CloudWatch 메트릭 정책 생성 및 첨부
    CUSTOM_POLICY_NAME="MomentirCloudWatchMetrics"
    if ! aws iam get-policy --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$CUSTOM_POLICY_NAME" > /dev/null 2>&1; then
        echo "   📝 커스텀 CloudWatch 메트릭 정책 생성 중..."
        aws iam create-policy \
            --policy-name $CUSTOM_POLICY_NAME \
            --policy-document file://aws/ecs-task-role-policy.json \
            --description "CloudWatch metrics access for Momentir app" \
            --no-cli-pager
    fi
    
    aws iam attach-role-policy \
        --role-name $TASK_ROLE_NAME \
        --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$CUSTOM_POLICY_NAME" \
        --no-cli-pager || echo "   ⚠️  정책이 이미 첨부되었을 수 있습니다"
        
else
    echo "   ❌ Task Role이 존재하지 않습니다: $TASK_ROLE_NAME"
    echo "   먼저 ECS Task Role을 생성해주세요"
    exit 1
fi

# 2. AWS Secrets Manager에 환경 변수 저장
echo ""
echo "🔑 2. Secrets Manager 환경 변수 설정"

# 환경 설정
aws secretsmanager update-secret \
    --secret-id "momentir-cx-llm/environment" \
    --secret-string "production" \
    --description "Environment setting for CloudWatch monitoring" \
    --no-cli-pager || aws secretsmanager create-secret \
    --name "momentir-cx-llm/environment" \
    --secret-string "production" \
    --description "Environment setting for CloudWatch monitoring" \
    --no-cli-pager

# CloudWatch 로깅 활성화
aws secretsmanager update-secret \
    --secret-id "momentir-cx-llm/ecs-enable-logging" \
    --secret-string "true" \
    --description "CloudWatch logging enabled flag" \
    --no-cli-pager || aws secretsmanager create-secret \
    --name "momentir-cx-llm/ecs-enable-logging" \
    --secret-string "true" \
    --description "CloudWatch logging enabled flag" \
    --no-cli-pager

echo "   ✅ Secrets Manager 설정 완료"

# 3. 새 Task Definition 생성 (CloudWatch 설정 포함)
echo ""
echo "📄 3. Task Definition 업데이트"

# 현재 Task Definition 가져오기
CURRENT_REVISION=$(aws ecs describe-task-definition \
    --task-definition $TASK_DEFINITION_FAMILY \
    --query 'taskDefinition.revision' \
    --output text)

echo "   현재 리비전: $CURRENT_REVISION"

# 새 Task Definition 생성 (JSON 템플릿 기반)
cat > task-definition-cloudwatch.json << 'EOF'
{
    "family": "momentir-cx-llm",
    "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/momentir-cx-llm-task-role",
    "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/momentir-cx-llm-execution-role",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "containerDefinitions": [
        {
            "name": "momentir-cx-llm",
            "image": "ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com/momentir-cx-llm:latest",
            "portMappings": [
                {
                    "containerPort": 8000,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {
                    "name": "AWS_DEFAULT_REGION",
                    "value": "ap-northeast-2"
                }
            ],
            "secrets": [
                {
                    "name": "ENVIRONMENT",
                    "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:momentir-cx-llm/environment"
                },
                {
                    "name": "ECS_ENABLE_LOGGING", 
                    "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:momentir-cx-llm/ecs-enable-logging"
                },
                {
                    "name": "DATABASE_URL",
                    "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:momentir-cx-llm/database-url"
                },
                {
                    "name": "LANGSMITH_API_KEY",
                    "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:momentir-cx-llm/langsmith-api-key"
                },
                {
                    "name": "LANGSMITH_TRACING",
                    "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:momentir-cx-llm/langsmith-tracing"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/momentir-cx-llm",
                    "awslogs-region": "ap-northeast-2",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}
EOF

# Account ID 치환
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i.bak "s/ACCOUNT_ID/$ACCOUNT_ID/g" task-definition-cloudwatch.json

echo "   📝 CloudWatch 설정이 포함된 Task Definition 등록 중..."
NEW_REVISION=$(aws ecs register-task-definition \
    --cli-input-json file://task-definition-cloudwatch.json \
    --query 'taskDefinition.revision' \
    --output text \
    --no-cli-pager)

echo "   ✅ 새 Task Definition 등록 완료: 리비전 $NEW_REVISION"

# 4. 서비스 업데이트
echo ""
echo "⚙️  4. ECS 서비스 업데이트"

echo "   🔄 서비스 업데이트 중..."
aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $SERVICE_NAME \
    --task-definition $TASK_DEFINITION_FAMILY:$NEW_REVISION \
    --desired-count 1 \
    --force-new-deployment \
    --no-cli-pager > /dev/null

echo "   ✅ 서비스 업데이트 시작됨"

# 5. 배포 상태 모니터링
echo ""
echo "📊 5. 배포 상태 모니터링"

echo "   ⏳ 배포 완료 대기 중..."
MAX_WAIT=600  # 10분
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    DEPLOYMENT_STATUS=$(aws ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --query 'services[0].deployments[?status==`PENDING`|| status==`RUNNING`][0].status' \
        --output text)
    
    RUNNING_COUNT=$(aws ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --query 'services[0].runningCount' \
        --output text)
        
    DESIRED_COUNT=$(aws ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --query 'services[0].desiredCount' \
        --output text)
    
    echo "   상태: $DEPLOYMENT_STATUS, 실행 중: $RUNNING_COUNT/$DESIRED_COUNT"
    
    if [ "$RUNNING_COUNT" = "$DESIRED_COUNT" ] && [ "$DEPLOYMENT_STATUS" != "PENDING" ]; then
        echo "   ✅ 배포 완료!"
        break
    fi
    
    sleep 30
    WAIT_TIME=$((WAIT_TIME + 30))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "   ⚠️  배포 시간 초과. 수동으로 확인해주세요."
fi

# 6. CloudWatch 로그 그룹 확인
echo ""
echo "📋 6. CloudWatch 설정 확인"

# 로그 그룹 존재 확인
LOG_GROUP="/ecs/momentir-cx-llm"
if aws logs describe-log-groups --log-group-name-prefix $LOG_GROUP > /dev/null 2>&1; then
    echo "   ✅ CloudWatch 로그 그룹 존재: $LOG_GROUP"
else
    echo "   📝 CloudWatch 로그 그룹 생성 중: $LOG_GROUP"
    aws logs create-log-group \
        --log-group-name $LOG_GROUP \
        --no-cli-pager
fi

# 로그 보존 기간 설정 (30일)
aws logs put-retention-policy \
    --log-group-name $LOG_GROUP \
    --retention-in-days 30 \
    --no-cli-pager || echo "   ⚠️  보존 정책이 이미 설정되었을 수 있습니다"

echo "   ✅ CloudWatch 로그 그룹 설정 완료"

# 7. 배포 완료 테스트
echo ""
echo "🧪 7. 배포 테스트"

# ALB URL 가져오기
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --names momentir-cx-llm-alb \
    --query 'LoadBalancers[0].DNSName' \
    --output text 2>/dev/null || echo "")

if [ -n "$ALB_DNS" ]; then
    echo "   🌐 ALB DNS: $ALB_DNS"
    echo "   🧪 헬스체크 테스트 중..."
    
    sleep 60  # 서비스 시작 대기
    
    if curl -s -f https://$ALB_DNS/health > /dev/null; then
        echo "   ✅ 헬스체크 성공!"
    else
        echo "   ❌ 헬스체크 실패. 로그를 확인해주세요."
    fi
else
    echo "   ⚠️  ALB DNS를 찾을 수 없습니다. 수동으로 테스트해주세요."
fi

# 8. 정리
echo ""
echo "🧹 8. 임시 파일 정리"
rm -f task-definition-cloudwatch.json task-definition-cloudwatch.json.bak

echo ""
echo "🎉 CloudWatch 모니터링 배포 완료!"
echo ""
echo "📊 CloudWatch 대시보드 및 로그 확인:"
echo "   - 로그: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups/log-group/%2Fecs%2Fmomentir-cx-llm"
echo "   - 메트릭: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#metricsV2:graph=~();namespace=MomentirApp/Search"
echo "   - Insights: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:logs-insights"
echo ""
echo "🔍 모니터링 쿼리는 다음 파일을 참조하세요:"
echo "   - aws/cloudwatch-insights-queries.md"
echo ""
echo "✨ 배포가 완료되었습니다!"