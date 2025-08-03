#!/bin/bash

# Azure OpenAI 연결 테스트 스크립트

set -e

echo "🔍 Azure OpenAI 연결 테스트"
echo "================================"

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📁 프로젝트 디렉토리: $PROJECT_DIR"
cd "$PROJECT_DIR"

# 가상환경 활성화
echo ""
echo "🔧 가상환경 활성화 중..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "   ✅ 가상환경 활성화 완료"
else
    echo "   ❌ 가상환경을 찾을 수 없습니다."
    exit 1
fi

# 환경변수 로드
echo ""
echo "⚙️  환경변수 로드 중..."
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo "   ✅ .env 파일 로드 완료"
else
    echo "   ⚠️  .env 파일을 찾을 수 없습니다."
fi

# Azure 설정 확인
echo ""
echo "🔍 Azure OpenAI 설정 확인..."
python3 -c "
import os
import sys
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

print('API Type:', os.getenv('OPENAI_API_TYPE', 'NOT_SET'))
print('Chat Endpoint:', os.getenv('AZURE_OPENAI_ENDPOINT', 'NOT_SET'))
print('Chat Model:', os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', 'NOT_SET'))
print()
print('Embedding Endpoint:', os.getenv('AZURE_EMBEDDING_ENDPOINT', 'NOT_SET'))
print('Embedding Model:', os.getenv('AZURE_EMBEDDING_DEPLOYMENT_NAME', 'NOT_SET'))

# 필수 설정 확인
api_type = os.getenv('OPENAI_API_TYPE')
if api_type == 'azure':
    # Chat 필수 변수
    chat_required_vars = [
        'OPENAI_API_KEY',
        'AZURE_OPENAI_ENDPOINT', 
        'AZURE_OPENAI_API_VERSION',
        'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME'
    ]
    
    missing_chat_vars = [var for var in chat_required_vars if not os.getenv(var)]
    
    if missing_chat_vars:
        print(f'❌ Chat 관련 누락된 환경변수: {missing_chat_vars}')
        sys.exit(1)
    
    # 임베딩 설정 확인 (선택사항)
    embedding_vars = [
        'AZURE_EMBEDDING_ENDPOINT',
        'AZURE_EMBEDDING_API_KEY',
        'AZURE_EMBEDDING_DEPLOYMENT_NAME'
    ]
    
    missing_embedding_vars = [var for var in embedding_vars if not os.getenv(var)]
    
    if missing_embedding_vars:
        print(f'⚠️  임베딩 관련 누락된 환경변수: {missing_embedding_vars}')
        print('   (임베딩 없이 계속 진행)')
    else:
        print('✅ 임베딩 전용 리소스 설정 완료')
    
    print('✅ Azure OpenAI 환경변수 설정 완료')
else:
    print('ℹ️  OpenAI 모드로 설정됨')
"

if [ $? -ne 0 ]; then
    echo "   ❌ 환경변수 설정에 문제가 있습니다."
    exit 1
fi

# Azure OpenAI 연결 테스트
echo ""
echo "🌐 Azure OpenAI 연결 테스트..."
python3 -c "
import os
import asyncio
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

async def test_azure_connection():
    try:
        api_type = os.getenv('OPENAI_API_TYPE')
        
        if api_type == 'azure':
            import openai
            
            client = openai.AsyncAzureOpenAI(
                api_key=os.getenv('OPENAI_API_KEY'),
                azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
                api_version=os.getenv('AZURE_OPENAI_API_VERSION')
            )
            
            chat_model = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')
            
            print(f'   ➤ Chat 모델 테스트: {chat_model}')
            
            # Chat 완성 테스트
            response = await client.chat.completions.create(
                model=chat_model,
                messages=[
                    {'role': 'user', 'content': '안녕하세요. 간단한 연결 테스트입니다.'}
                ],
                max_tokens=50
            )
            
            chat_result = response.choices[0].message.content
            print(f'   ✅ Chat 응답: {chat_result[:30]}...')
            
            # 임베딩 전용 리소스 테스트
            embedding_endpoint = os.getenv('AZURE_EMBEDDING_ENDPOINT')
            embedding_api_key = os.getenv('AZURE_EMBEDDING_API_KEY')
            embedding_model = os.getenv('AZURE_EMBEDDING_DEPLOYMENT_NAME')
            
            if embedding_endpoint and embedding_api_key and embedding_model:
                print(f'   ➤ Embedding 모델 테스트 (전용 리소스): {embedding_model}')
                
                try:
                    # 임베딩 전용 클라이언트 생성
                    embedding_client = openai.AsyncAzureOpenAI(
                        api_key=embedding_api_key,
                        azure_endpoint=embedding_endpoint,
                        api_version=os.getenv('AZURE_EMBEDDING_API_VERSION', '2024-02-01')
                    )
                    
                    embedding_response = await embedding_client.embeddings.create(
                        model=embedding_model,
                        input='테스트 텍스트'
                    )
                    
                    embedding = embedding_response.data[0].embedding
                    print(f'   ✅ Embedding 차원: {len(embedding)}')
                except Exception as embedding_error:
                    print(f'   ❌ Embedding 실패: {embedding_error}')
            else:
                print('   ⚠️  임베딩 전용 리소스 설정이 없습니다.')
            
            print('✅ Azure OpenAI 연결 테스트 성공!')
            
        else:
            print('ℹ️  OpenAI 모드 - Azure 테스트 건너뜀')
            
    except Exception as e:
        print(f'❌ Azure OpenAI 연결 실패: {e}')
        return False
    
    return True

# 비동기 함수 실행
success = asyncio.run(test_azure_connection())
if not success:
    exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Azure OpenAI 연결 테스트 실패"
    echo "   ➤ 설정을 확인하고 다시 시도하세요."
    exit 1
fi

# LangSmith 연동 테스트
echo ""
echo "🔍 LangSmith 연동 테스트..."
python3 -c "
from app.utils.langsmith_config import langsmith_manager

if langsmith_manager.enabled:
    print('✅ LangSmith 추적 활성화됨')
    print(f'   프로젝트: {langsmith_manager.project_name}')
    if langsmith_manager.llm_client:
        print('✅ LLM 클라이언트 초기화 완료')
    else:
        print('⚠️  LLM 클라이언트 초기화 실패')
else:
    print('ℹ️  LangSmith 추적 비활성화됨')
"

echo ""
echo "🎉 Azure OpenAI 연결 테스트 완료!"
echo "================================"
echo ""
echo "📋 다음 단계:"
echo "   • 서버 시작: ./scripts/02-start-local.sh"
echo "   • API 테스트: ./scripts/03-test-api.sh"
echo "   • 자세한 가이드: AZURE_OPENAI_MIGRATION_GUIDE.md"
echo ""