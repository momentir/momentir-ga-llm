# Azure OpenAI 마이그레이션 가이드

## 🎯 개요
OpenAI API에서 Azure OpenAI Service로 마이그레이션이 완료되었습니다. 이 가이드에서는 변경사항과 테스트 방법을 안내합니다.

## 🔧 변경사항

### 1. 환경변수 설정 (.env)
```bash
# Azure OpenAI API 설정
OPENAI_API_KEY=your-azure-openai-api-key
OPENAI_API_TYPE=azure
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-ada-002
```

### 2. 업데이트된 라이브러리
- `openai==1.98.0` (최신 버전, Azure 지원)
- `langchain-openai==0.3.28` (Azure OpenAI 통합)
- 모든 의존성 호환성 최신 버전으로 업데이트

### 3. 코드 변경사항

#### MemoRefinerService 
```python
# Azure OpenAI 클라이언트 자동 설정
if api_type == "azure":
    self.client = openai.AsyncAzureOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    )
    self.chat_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4")
    self.embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-ada-002")
```

#### CustomerService
```python
# 동일한 Azure OpenAI 설정 패턴 적용
# 모든 LLM 호출에서 동적 모델명 사용
```

#### LangSmith 통합
```python
# Azure OpenAI와 LangSmith 자동 연동
# 추적 메타데이터에 Azure 모델 정보 포함
```

## 🚀 Azure 배포 설정

### 1. Azure OpenAI 리소스 생성
```bash
# Azure CLI로 리소스 생성
az cognitiveservices account create \
  --name your-openai-resource \
  --resource-group your-resource-group \
  --kind OpenAI \
  --sku S0 \
  --location eastus
```

### 2. 배포 모델 설정
Azure Portal에서 다음 모델을 배포하세요:
- **GPT-4**: 채팅/분석 작업용
- **text-embedding-ada-002**: 임베딩 생성용

배포명을 환경변수에 맞게 설정:
- `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-ada-002`

## 🧪 테스트 방법

### 1. 의존성 설치
```bash
# 가상환경 활성화
source venv/bin/activate

# 업데이트된 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정 확인
```bash
# Azure 설정 확인
python -c "
import os
print('API Type:', os.getenv('OPENAI_API_TYPE'))
print('Endpoint:', os.getenv('AZURE_OPENAI_ENDPOINT'))
print('Chat Model:', os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME'))
print('Embedding Model:', os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME'))
"
```

### 3. 서버 실행 및 테스트
```bash
# 서버 시작 (Azure 연동 로그 확인)
./scripts/02-start-local.sh

# API 테스트 실행
./scripts/03-test-api.sh
```

### 4. 기능별 테스트

#### A. 메모 정제 (Azure OpenAI Chat)
```bash
curl -X POST "http://127.0.0.1:8000/api/memo/refine" \
  -H "Content-Type: application/json" \
  -d '{
    "memo": "고객이 건강보험 가입을 문의했습니다. 다음 주에 상세 상담 예정입니다."
  }'
```

#### B. 임베딩 생성 (Azure OpenAI Embedding)
```bash
# 메모 저장 시 자동으로 임베딩 생성됨
curl -X POST "http://127.0.0.1:8000/api/memo/quick-save" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "test-customer-id",
    "content": "테스트 메모입니다."
  }'
```

#### C. 엑셀 컬럼 매핑 (Azure OpenAI Chat)
```bash
curl -X POST "http://127.0.0.1:8000/api/customer/column-mapping" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_columns": ["성함", "전화번호", "직장", "성별", "생일"]
  }'
```

## 📊 성능 및 모니터링

### 1. Azure 모니터링
- Azure Portal에서 OpenAI 리소스 사용량 확인
- 요청 수, 토큰 사용량, 응답 시간 모니터링
- 비용 추적 및 알림 설정

### 2. LangSmith 통합
- Azure 모델 호출이 LangSmith에 자동 추적됨
- 메타데이터에 Azure 배포명 포함
- 성능 비교 및 품질 평가 가능

### 3. 로그 모니터링
```bash
# Azure 연동 로그 확인
tail -f logs/app.log | grep -E "(Azure|OpenAI)"
```

## 🔄 OpenAI ↔ Azure 전환

### OpenAI로 되돌리기
```bash
# .env에서 설정 변경
OPENAI_API_TYPE=openai
# AZURE_* 설정들 주석 처리 또는 제거
```

### Azure 설정 활성화
```bash
# .env에서 설정 변경  
OPENAI_API_TYPE=azure
# AZURE_* 설정들 활성화
```

시스템은 `OPENAI_API_TYPE` 값에 따라 자동으로 적절한 클라이언트를 사용합니다.

## 🚨 문제 해결

### 1. 연결 오류
```
Error: Invalid Azure endpoint
```
**해결**: `AZURE_OPENAI_ENDPOINT`가 올바른 형식인지 확인
- 형식: `https://your-resource-name.openai.azure.com/`

### 2. 배포 모델 오류
```
Error: The API deployment for this resource does not exist
```
**해결**: Azure Portal에서 배포 모델명 확인 후 환경변수 수정

### 3. API 버전 오류
```
Error: Unsupported API version
```
**해결**: `AZURE_OPENAI_API_VERSION=2024-02-01` 사용 (최신 안정 버전)

### 4. 권한 오류
```
Error: Access denied
```
**해결**: Azure OpenAI 리소스의 키와 권한 확인

## 💡 최적화 팁

### 1. 성능 최적화
- Azure 리전을 서비스와 가까운 곳으로 설정
- 적절한 SKU (S0, S1) 선택으로 처리량 최적화
- 배포 모델의 할당량 모니터링

### 2. 비용 최적화
- 불필요한 API 호출 최소화
- 배치 처리 활용
- 토큰 사용량 모니터링 및 최적화

### 3. 보안 강화
- Azure Key Vault로 API 키 관리
- 네트워크 보안 그룹으로 액세스 제한
- Azure AD 인증 연동 고려

## 📈 다음 단계

1. **프로덕션 배포**: 프로덕션 환경에 Azure OpenAI 설정
2. **모니터링 강화**: Azure Monitor와 Application Insights 연동
3. **자동화**: CI/CD 파이프라인에 Azure 설정 포함
4. **백업 전략**: 다중 리전 배포 고려

## ✅ 체크리스트

- [ ] Azure OpenAI 리소스 생성 및 배포
- [ ] 환경변수 설정 완료
- [ ] 의존성 업데이트 설치
- [ ] 서버 시작 및 연동 확인
- [ ] API 테스트 모든 기능 정상 작동
- [ ] LangSmith 추적 정상 작동
- [ ] 성능 및 비용 모니터링 설정
- [ ] 문서화 및 팀 공유 완료