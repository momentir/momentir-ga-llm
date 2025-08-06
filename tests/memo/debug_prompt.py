#!/usr/bin/env python3
"""
프롬프트 시스템 디버깅 스크립트
"""
import asyncio
import sys
import os
sys.path.append('../..')

from app.models import MemoRefineRequest
from app.services.memo_refiner import MemoRefinerService
from app.database import get_db
from unittest.mock import AsyncMock
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_prompt_system():
    print("🔍 프롬프트 시스템 디버깅 시작")
    
    # 1. 모델 테스트
    print("\n=== 1. MemoRefineRequest 모델 테스트 ===")
    try:
        request = MemoRefineRequest(
            memo="테스트 메모",
            custom_prompt="요약: {memo}"
        )
        print(f"✅ 모델 생성 성공")
        print(f"   memo: {request.memo}")
        print(f"   custom_prompt: {request.custom_prompt}")
        print(f"   has custom_prompt attr: {hasattr(request, 'custom_prompt')}")
        print(f"   getattr result: {getattr(request, 'custom_prompt', 'NOT_FOUND')}")
    except Exception as e:
        print(f"❌ 모델 생성 실패: {e}")
        return
    
    # 2. 서비스 테스트
    print("\n=== 2. MemoRefinerService 테스트 ===")
    service = MemoRefinerService()
    print(f"   use_dynamic_prompts: {service.use_dynamic_prompts}")
    
    # 3. refine_memo 메서드 직접 테스트
    print("\n=== 3. refine_memo 메서드 직접 테스트 ===")
    
    # Mock LLM client
    class MockResponse:
        def __init__(self, content):
            self.content = content
    
    # Mock the ainvoke method
    original_ainvoke = service.llm_client.ainvoke
    
    def mock_ainvoke(prompt):
        print(f"🚀 LLM에 전달된 프롬프트: {prompt}")
        return MockResponse("테스트 요약")
    
    service.llm_client.ainvoke = mock_ainvoke
    
    try:
        # Custom prompt으로 테스트
        result = await service.refine_memo(
            memo="테스트 메모",
            custom_prompt="간단 요약: {memo}"
        )
        print(f"✅ refine_memo 결과: {result}")
    except Exception as e:
        print(f"❌ refine_memo 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 원래 메서드 복원
        service.llm_client.ainvoke = original_ainvoke

if __name__ == "__main__":
    asyncio.run(debug_prompt_system())