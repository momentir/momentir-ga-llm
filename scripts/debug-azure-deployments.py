#!/usr/bin/env python3
"""
Azure OpenAI 배포 모델 디버깅 스크립트
배포된 모델들을 확인하고 연결을 테스트합니다.
"""

import os
import asyncio
import sys
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

async def debug_azure_deployments():
    """Azure OpenAI 배포 모델들을 디버깅합니다."""
    
    try:
        import openai
    except ImportError:
        print("❌ openai 라이브러리가 설치되지 않았습니다.")
        print("   pip install openai 를 실행하세요.")
        return False
    
    # 환경변수 확인
    api_key = os.getenv("OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    
    # 임베딩 전용 리소스 설정
    embedding_endpoint = os.getenv("AZURE_EMBEDDING_ENDPOINT")
    embedding_api_key = os.getenv("AZURE_EMBEDDING_API_KEY")
    embedding_api_version = os.getenv("AZURE_EMBEDDING_API_VERSION", "2024-02-01")
    embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME")
    
    print("🔍 Azure OpenAI 설정 정보:")
    print(f"   Chat Endpoint: {endpoint}")
    print(f"   Chat API Version: {api_version}")
    print(f"   Chat Deployment: {chat_deployment}")
    print()
    print("🔍 Azure 임베딩 전용 리소스 설정:")
    print(f"   Embedding Endpoint: {embedding_endpoint}")
    print(f"   Embedding API Version: {embedding_api_version}")
    print(f"   Embedding Deployment: {embedding_deployment}")
    print()
    
    if not all([api_key, endpoint, chat_deployment]):
        print("❌ 필수 환경변수가 설정되지 않았습니다.")
        return False
    
    # Azure OpenAI 클라이언트 생성
    try:
        client = openai.AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
        print("✅ Azure OpenAI 클라이언트 생성 성공")
    except Exception as e:
        print(f"❌ Azure OpenAI 클라이언트 생성 실패: {e}")
        return False
    
    # 배포된 모델 목록 조회 시도
    print()
    print("📋 배포된 모델 목록 조회 시도:")
    try:
        # Azure REST API를 통해 배포 목록 조회
        import httpx
        
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        
        # 배포 목록 조회 URL
        deployments_url = f"{endpoint.rstrip('/')}/openai/deployments?api-version={api_version}"
        
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(deployments_url, headers=headers)
            
            if response.status_code == 200:
                deployments = response.json()
                if deployments.get("data"):
                    print("   ✅ 배포된 모델들:")
                    for deployment in deployments["data"]:
                        model_name = deployment.get("model", "unknown")
                        deployment_name = deployment.get("id", "unknown")
                        status = deployment.get("status", "unknown")
                        print(f"      • {deployment_name} ({model_name}) - {status}")
                else:
                    print("   ⚠️  배포된 모델이 없습니다.")
            else:
                print(f"   ❌ 배포 목록 조회 실패: {response.status_code}")
                
    except Exception as e:
        print(f"   ⚠️  배포 목록 조회 중 오류: {e}")
    
    print()
    
    # 일반적인 배포명들을 시도해봅니다
    common_chat_deployments = [
        chat_deployment,  # 설정된 배포명
        "gpt-4",
        "gpt-4-turbo", 
        "gpt-4o",
        "gpt-35-turbo",
        "gpt-3.5-turbo"
    ]
    
    print("🧪 Chat 모델 배포 테스트:")
    working_chat_deployment = None
    
    for deployment in common_chat_deployments:
        if not deployment:
            continue
            
        try:
            print(f"   ➤ 테스트 중: {deployment}")
            response = await client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "user", "content": "안녕하세요"}
                ],
                max_tokens=10
            )
            
            result = response.choices[0].message.content
            print(f"   ✅ 성공: {deployment} - 응답: {result}")
            working_chat_deployment = deployment
            break
            
        except Exception as e:
            print(f"   ❌ 실패: {deployment} - {str(e)}")
    
    print()
    
    # 임베딩 모델 테스트 (전용 리소스 사용)
    print("🧪 Embedding 모델 배포 테스트 (전용 리소스):")
    working_embedding_deployment = None
    
    if embedding_endpoint and embedding_api_key and embedding_deployment:
        try:
            # 임베딩 전용 클라이언트 생성
            embedding_client = openai.AsyncAzureOpenAI(
                api_key=embedding_api_key,
                azure_endpoint=embedding_endpoint,
                api_version=embedding_api_version
            )
            
            print(f"   ➤ 테스트 중: {embedding_deployment}")
            response = await embedding_client.embeddings.create(
                model=embedding_deployment,
                input="테스트"
            )
            
            embedding = response.data[0].embedding
            print(f"   ✅ 성공: {embedding_deployment} - 차원: {len(embedding)}")
            working_embedding_deployment = embedding_deployment
            
        except Exception as e:
            print(f"   ❌ 실패: {embedding_deployment} - {str(e)}")
    else:
        print("   ⚠️  임베딩 전용 리소스 설정이 없습니다.")
    
    print()
    
    # 결과 요약
    if working_chat_deployment or working_embedding_deployment:
        print("🎉 작동하는 배포를 찾았습니다!")
        
        if working_chat_deployment:
            print(f"   Chat 모델: {working_chat_deployment}")
            
        if working_embedding_deployment:
            print(f"   Embedding 모델: {working_embedding_deployment}")
        
        print()
        print("💡 .env 파일을 다음과 같이 수정하세요:")
        
        if working_chat_deployment and working_chat_deployment != chat_deployment:
            print(f"   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME={working_chat_deployment}")
            
        if working_embedding_deployment and working_embedding_deployment != embedding_deployment:
            print(f"   AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME={working_embedding_deployment}")
        
        return True
    else:
        print("❌ 작동하는 배포를 찾지 못했습니다.")
        print()
        print("🔧 문제 해결 방법:")
        print("   1. Azure Portal에서 OpenAI 리소스 확인")
        print("   2. 모델 배포 상태 확인")
        print("   3. API 키 및 엔드포인트 확인")
        print("   4. 배포명이 정확한지 확인")
        
        return False

if __name__ == "__main__":
    print("🔍 Azure OpenAI 배포 디버깅")
    print("=" * 40)
    print()
    
    success = asyncio.run(debug_azure_deployments())
    
    if not success:
        sys.exit(1)
    
    print()
    print("✅ 디버깅 완료!")