# ECS 배포 실패 트러블슈팅 가이드

## 문제 상황
- GitHub Workflow에서 ECS 배포가 18분 이상 지속되며 완료되지 않음
- 새로운 Task Definition이 배포되지 않고 서비스가 비정상 상태로 유지

## 근본 원인 분석

### 1. 다중 배포 충돌 문제
**증상**: 여러 개의 배포가 동시에 `IN_PROGRESS` 상태로 진행
**원인**: 이전 배포가 완료되지 않은 상태에서 새로운 배포가 시작되어 충돌 발생

### 2. Task Definition 설정 오류들

#### 2.1 환경변수/시크릿 중복 정의
**오류**: `LANGSMITH_TRACING`이 환경변수와 시크릿 양쪽에 정의됨
```json
{
  "environment": [
    {
      "name": "LANGSMITH_TRACING",
      "value": "true"
    }
  ],
  "secrets": [
    {
      "name": "LANGSMITH_TRACING", 
      "valueFrom": "arn:aws:secretsmanager:..."
    }
  ]
}
```

#### 2.2 헬스체크 경로 불일치
**오류**: ECS Task는 `/health` 체크, ALB는 `/` 체크
- ECS Task Definition: `"python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')..."`
- ALB Target Group: Health check path = `/`

#### 2.3 Docker 이미지 태그 문제
**오류**: `:latest` 태그가 ECR에 존재하지 않음
- Task Definition에서 `image: "...momentir-cx-llm:latest"` 사용
- ECR에는 커밋 해시 태그만 존재 (예: `bfea2cf646ba4eb2b4f0e07661b6de2fef444f75`)

## 진단 방법

### 1. 서비스 상태 확인
```bash
aws ecs describe-services \
  --cluster momentir-cx-llm-cluster \
  --services momentir-cx-llm-service \
  --query 'services[0].{status:status,runningCount:runningCount,desiredCount:desiredCount,pendingCount:pendingCount,deployments:deployments[*].{status:status,taskDefinition:taskDefinition,runningCount:runningCount,rolloutState:rolloutState}}' \
  --output table
```

### 2. 실행 중인 태스크 확인
```bash
aws ecs list-tasks \
  --cluster momentir-cx-llm-cluster \
  --service-name momentir-cx-llm-service
```

### 3. 태스크 상세 정보 확인
```bash
aws ecs describe-tasks \
  --cluster momentir-cx-llm-cluster \
  --tasks <TASK_ARN> \
  --query 'tasks[*].{taskArn:taskArn,lastStatus:lastStatus,healthStatus:healthStatus,stoppedReason:stoppedReason}'
```

### 4. 서비스 이벤트 로그 확인
```bash
aws ecs describe-services \
  --cluster momentir-cx-llm-cluster \
  --services momentir-cx-llm-service \
  --query 'services[0].events[:10]' \
  --output table
```

### 5. ECR 이미지 태그 확인
```bash
aws ecr describe-images \
  --repository-name momentir-cx-llm \
  --query 'imageDetails[*].{tags:imageTags,digest:imageDigest,pushed:imagePushedAt}' \
  --output table
```

## 해결 방법

### 단계 1: 충돌하는 태스크 정리
```bash
# 현재 실행 중인 태스크 ARN 확인
aws ecs list-tasks --cluster momentir-cx-llm-cluster --service-name momentir-cx-llm-service

# 비정상 태스크 강제 종료
aws ecs stop-task \
  --cluster momentir-cx-llm-cluster \
  --task <TASK_ARN> \
  --reason "Stopping unhealthy task to allow clean deployment"
```

### 단계 2: Task Definition 수정

#### 2.1 중복 환경변수 제거
`aws/task-definition.json`에서 환경변수 섹션에서 `LANGSMITH_TRACING` 제거:
```json
{
  "environment": [
    // LANGSMITH_TRACING 제거 (secrets에서만 정의)
    {
      "name": "OPENAI_API_TYPE",
      "value": "azure"
    }
    // ... 다른 환경변수들
  ]
}
```

#### 2.2 헬스체크 경로 통일
ECS Task Definition의 healthCheck를 ALB와 맞춤:
```json
{
  "healthCheck": {
    "command": [
      "CMD-SHELL",
      "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/').getcode() == 200\" || exit 1"
    ],
    "interval": 30,
    "timeout": 5,
    "retries": 3,
    "startPeriod": 60
  }
}
```

#### 2.3 Docker 이미지 태그 수정
ECR에서 실제 존재하는 태그로 변경:
```json
{
  "image": "940482450816.dkr.ecr.ap-northeast-2.amazonaws.com/momentir-cx-llm:bfea2cf646ba4eb2b4f0e07661b6de2fef444f75"
}
```

### 단계 3: 새 Task Definition 등록 및 배포
```bash
# 수정된 Task Definition 등록
aws ecs register-task-definition \
  --cli-input-json file:///path/to/task-definition.json

# 서비스 업데이트 (새 Task Definition으로 강제 배포)
aws ecs update-service \
  --cluster momentir-cx-llm-cluster \
  --service momentir-cx-llm-service \
  --task-definition momentir-cx-llm:<NEW_REVISION> \
  --desired-count 1 \
  --force-new-deployment
```

### 단계 4: 배포 상태 모니터링
```bash
# 배포 진행상황 확인 (30초마다 반복)
watch -n 30 'aws ecs describe-services \
  --cluster momentir-cx-llm-cluster \
  --services momentir-cx-llm-service \
  --query "services[0].{runningCount:runningCount,pendingCount:pendingCount,deployments:deployments[0].rolloutState}"'

# 태스크 헬스 상태 확인
aws ecs describe-tasks \
  --cluster momentir-cx-llm-cluster \
  --tasks <NEW_TASK_ARN> \
  --query 'tasks[0].{lastStatus:lastStatus,healthStatus:healthStatus}'
```

### 단계 5: 애플리케이션 동작 확인
```bash
# ALB DNS 이름 확인
aws elbv2 describe-load-balancers \
  --names momentir-cx-llm-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text

# 헬스체크 테스트 (SSL 검증 무시)
curl https://<ALB_DNS_NAME>/ -k -I --connect-timeout 10
```

## 예방 방법

### 1. CI/CD 파이프라인 개선
- 배포 전 이전 배포 완료 대기 로직 추가
- 배포 타임아웃 설정 (기본 10분 → 15분)
- 헬스체크 실패 시 자동 롤백 설정

### 2. Task Definition 검증
- 배포 전 JSON 스키마 검증
- 환경변수/시크릿 중복 검사
- ECR 이미지 태그 존재 여부 확인

### 3. 모니터링 강화
- ECS 서비스 상태 알람 설정
- 배포 실패 시 Slack/이메일 알림
- 애플리케이션 헬스체크 메트릭 수집

## 체크리스트

배포 문제 발생 시 다음 순서로 확인:

- [ ] 서비스에 여러 `IN_PROGRESS` 배포가 있는가?
- [ ] 실행 중인 태스크가 `UNHEALTHY` 상태인가?
- [ ] Task Definition에 환경변수/시크릿 중복이 있는가?
- [ ] 헬스체크 경로가 ECS와 ALB에서 일치하는가?
- [ ] Docker 이미지 태그가 ECR에 존재하는가?
- [ ] 새 태스크가 컨테이너 이미지를 정상적으로 pull하는가?
- [ ] 애플리케이션이 정상적으로 시작되고 헬스체크에 응답하는가?

## 주요 AWS CLI 명령어 모음

```bash
# 서비스 상태 확인
aws ecs describe-services --cluster <CLUSTER> --services <SERVICE>

# 태스크 목록 확인  
aws ecs list-tasks --cluster <CLUSTER> --service-name <SERVICE>

# 태스크 상세 정보
aws ecs describe-tasks --cluster <CLUSTER> --tasks <TASK_ARN>

# 태스크 강제 종료
aws ecs stop-task --cluster <CLUSTER> --task <TASK_ARN> --reason "<REASON>"

# Task Definition 등록
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 서비스 업데이트
aws ecs update-service --cluster <CLUSTER> --service <SERVICE> --task-definition <TD:REVISION> --force-new-deployment

# ECR 이미지 확인
aws ecr describe-images --repository-name <REPO>

# ALB 상태 확인
aws elbv2 describe-load-balancers --names <ALB_NAME>
aws elbv2 describe-target-groups --target-group-arns <TG_ARN>
```

이 가이드를 통해 유사한 ECS 배포 문제 발생 시 체계적으로 진단하고 해결할 수 있습니다.